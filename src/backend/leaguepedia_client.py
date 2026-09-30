"""
Cliente da Leaguepedia (MediaWiki + Cargo API) — robusto a rate limit.

A API anônima da Leaguepedia (Fandom) é AGRESSIVAMENTE limitada e queries amplas
(sem WHERE seletivo) lançam MWException no servidor. Por isso este cliente:

  * Sempre usa um WHERE seletivo (prefixo de OverviewPage + data >= corte), que
    é barato e indexado.
  * Faz throttle de no mínimo `min_gap` segundos entre requisições.
  * Em caso de "rate limit" ou MWException, espera (backoff) e tenta de novo.

Como o resultado é cacheado no SQLite, este sync só precisa rodar UMA vez (ou
periodicamente para pegar jogos novos) — então vale a pena ser paciente.

Mapeamento de colunas (PicksAndBansS7): Team1 = AZUL, Team2 = VERMELHO.
"""

from __future__ import annotations

import time
from datetime import date, datetime
from typing import Callable, Optional

import requests

import config
from src.models.draft import DraftAction, GameDraft, TeamInfo

ProgressFn = Callable[[str], None]

_BAN_FIELDS = [f"Team{t}Ban{i}" for t in (1, 2) for i in range(1, 6)]
_PICK_FIELDS = [f"Team{t}Pick{i}" for t in (1, 2) for i in range(1, 6)]
_ROLE_FIELDS = [f"Team{t}Role{i}" for t in (1, 2) for i in range(1, 6)]
_META_FIELDS = ["OverviewPage", "Team1", "Team2", "Winner", "Patch", "DateTime_UTC", "GameId"]
_ALL_FIELDS = _META_FIELDS + _BAN_FIELDS + _PICK_FIELDS + _ROLE_FIELDS


def _noop(_: str) -> None:
    pass


class RateLimited(Exception):
    pass


class LeaguepediaClient:
    def __init__(self, session: Optional[requests.Session] = None,
                 min_gap: float = 6.0, max_retries: int = 6,
                 initial_backoff: float = 30.0):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": config.HTTP_USER_AGENT})
        self.min_gap = min_gap
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self._last_call = 0.0

    # ------------------------------------------------------------- requests
    def _cargo_query(self, where: str, limit: int = 500,
                     progress: ProgressFn = _noop) -> list[dict]:
        params = {
            "action": "cargoquery", "format": "json",
            "tables": "PicksAndBansS7", "fields": ",".join(_ALL_FIELDS),
            "where": where, "order_by": "PicksAndBansS7.DateTime_UTC DESC",
            "limit": str(limit),
        }
        backoff = self.initial_backoff
        for attempt in range(1, self.max_retries + 1):
            # throttle entre requisições bem-sucedidas/tentativas
            gap = self.min_gap - (time.time() - self._last_call)
            if gap > 0:
                time.sleep(gap)
            resp = self.session.get(config.LEAGUEPEDIA_API, params=params,
                                    timeout=config.HTTP_TIMEOUT)
            self._last_call = time.time()
            try:
                data = resp.json()
            except ValueError:
                raise RuntimeError(f"Resposta não-JSON (HTTP {resp.status_code})")

            if "error" in data:
                info = data["error"].get("info", "")
                transient = "rate limit" in info.lower() or "MWException" in info
                if transient and attempt < self.max_retries:
                    progress(f"    (tentativa {attempt}: {info[:50]}… aguardando {backoff:.0f}s)")
                    time.sleep(backoff)
                    backoff = min(backoff * 1.6, 180)
                    continue
                raise RuntimeError(info)

            return [item["title"] for item in data.get("cargoquery", [])]
        raise RateLimited("rate limit persistente após várias tentativas")

    # --------------------------------------------------------------- public
    def fetch_recent_games(self, league_key: str,
                           since: date = config.DATA_SINCE,
                           limit: int = 500,
                           progress: ProgressFn = _noop) -> list[GameDraft]:
        """
        Busca jogos de uma liga desde `since`. Tenta cada prefixo-candidato de
        OverviewPage até encontrar resultados (cobre renomeações tipo LCS->LTA).
        """
        league = config.LEAGUE_BY_KEY.get(league_key)
        prefixes = league["prefixes"] if league else [league_key]

        for prefix in prefixes:
            safe_prefix = prefix.replace("'", "''")
            where = (f"PicksAndBansS7.OverviewPage LIKE '{safe_prefix}%' "
                     f"AND PicksAndBansS7.DateTime_UTC >= '{since.isoformat()} 00:00:00'")
            progress(f"  [{league_key}] tentando prefixo '{prefix}'…")
            records = self._cargo_query(where, limit=limit, progress=progress)
            if records:
                progress(f"  [{league_key}] {len(records)} jogos via '{prefix}'.")
                games = [self._record_to_game(r, league_key) for r in records]
                return [g for g in games if g is not None]
        progress(f"  [{league_key}] nenhum jogo encontrado em 2026.")
        return []

    def fetch_all_2026(self, since: date = config.DATA_SINCE,
                       limit: int = 2000, progress: ProgressFn = _noop) -> list[GameDraft]:
        """
        Busca TODAS as ligas monitoradas em UMA ÚNICA requisição (minimiza o
        rate limit), depois classifica cada jogo na sua liga pelo OverviewPage.
        """
        # Monta (OverviewPage LIKE 'A%' OR LIKE 'B%' ...) com todos os prefixos.
        prefixes: list[tuple[str, str]] = []  # (prefixo, league_key)
        for lg in config.LEAGUES:
            for p in lg["prefixes"]:
                prefixes.append((p, lg["key"]))
        like_clause = " OR ".join(
            f"PicksAndBansS7.OverviewPage LIKE '{p.replace(chr(39), chr(39)*2)}%'"
            for p, _ in prefixes
        )
        where = (f"({like_clause}) "
                 f"AND PicksAndBansS7.DateTime_UTC >= '{since.isoformat()} 00:00:00'")

        progress("Buscando todas as ligas em 1 requisição…")
        records = self._cargo_query(where, limit=limit, progress=progress)
        progress(f"{len(records)} jogos retornados; classificando por liga…")

        games: list[GameDraft] = []
        for rec in records:
            page = (rec.get("OverviewPage") or "")
            league_key = self._classify(page, prefixes)
            g = self._record_to_game(rec, league_key)
            if g is not None:
                games.append(g)
        return games

    @staticmethod
    def _classify(overview_page: str, prefixes: list[tuple[str, str]]) -> str:
        """Descobre a league_key pelo início do OverviewPage (mais longo primeiro)."""
        for prefix, key in sorted(prefixes, key=lambda x: -len(x[0])):
            if overview_page.startswith(prefix):
                return key
        return "UNKNOWN"

    # ------------------------------------------------------------- parsing
    def _record_to_game(self, rec: dict, league_key: str) -> Optional[GameDraft]:
        try:
            blue_name = (rec.get("Team1") or "Blue Team").strip()
            red_name = (rec.get("Team2") or "Red Team").strip()
            winner = "blue" if str(rec.get("Winner")) == "1" else "red"
            patch = (rec.get("Patch") or "").strip()
            raw_dt = (rec.get("DateTime UTC") or rec.get("DateTime_UTC") or "").strip()
            match_date = self._parse_date(raw_dt)
            game_id = (rec.get("GameId") or f"{blue_name}-{red_name}-{raw_dt}").strip()

            blue = TeamInfo(name=blue_name, short=_short(blue_name))
            red = TeamInfo(name=red_name, short=_short(red_name))

            def field(name: str) -> Optional[str]:
                val = rec.get(name) or rec.get(name.replace("_", " "))
                val = (val or "").strip()
                return val or None

            order_counter = {"ban": 0, "pick": 0}
            actions: list[DraftAction] = []
            for step in config.DRAFT_SEQUENCE:
                team_idx = 1 if step["side"] == "blue" else 2
                kind = step["type"].capitalize()
                champ = field(f"Team{team_idx}{kind}{step['slot']}")
                if not champ:
                    continue
                order_counter[step["type"]] += 1
                role = field(f"Team{team_idx}Role{step['slot']}") if step["type"] == "pick" else None
                actions.append(DraftAction(
                    phase=step["phase"], action_type=step["type"], side=step["side"],
                    slot=step["slot"], global_order=order_counter[step["type"]],
                    champion=champ, role=role, player=None,
                ))

            return GameDraft(
                game_id=str(game_id), league=league_key, patch=patch,
                match_date=match_date, blue=blue, red=red,
                winner=winner, actions=actions,
            )
        except Exception:
            return None

    @staticmethod
    def _parse_date(raw: str) -> date:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw.strip(), fmt).date()
            except ValueError:
                continue
        return date.today()


def _short(team_name: str) -> str:
    parts = team_name.split()
    if len(parts) >= 2:
        return "".join(p[0] for p in parts[:3]).upper()
    return team_name[:3].upper()
