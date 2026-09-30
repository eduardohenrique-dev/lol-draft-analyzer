"""
Camada de persistência (SQLite).

Estratégia de cache: a aplicação NUNCA deve bater na API para dados antigos a
cada abertura. O fluxo é:
    1. Ao abrir, lê tudo do SQLite (instantâneo).
    2. Um "sync" sob demanda busca apenas partidas novas na Leaguepedia e faz
       upsert aqui.
    3. As estatísticas/draft são sempre lidas do banco.

O esquema é normalizado o suficiente para consultas rápidas, mas simples:
    - leagues / teams : dimensões
    - games           : uma linha por jogo (com vencedor, patch, data)
    - draft_actions   : uma linha por AÇÃO do draft (20 por jogo) -- esta é a
                        tabela que alimenta tanto a tela de draft quanto o
                        motor estatístico.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import Iterable, Iterator, Optional

import config
from src.models.draft import DraftAction, GameDraft, TeamInfo

SCHEMA = """
CREATE TABLE IF NOT EXISTS leagues (
    key   TEXT PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teams (
    name      TEXT PRIMARY KEY,
    short     TEXT,
    logo_path TEXT
);

CREATE TABLE IF NOT EXISTS games (
    game_id    TEXT PRIMARY KEY,
    league     TEXT NOT NULL,
    patch      TEXT,
    match_date TEXT,                 -- ISO 8601 (YYYY-MM-DD)
    blue_team  TEXT NOT NULL,
    red_team   TEXT NOT NULL,
    winner     TEXT NOT NULL,        -- 'blue' | 'red'
    FOREIGN KEY (league)    REFERENCES leagues(key),
    FOREIGN KEY (blue_team) REFERENCES teams(name),
    FOREIGN KEY (red_team)  REFERENCES teams(name)
);

CREATE TABLE IF NOT EXISTS draft_actions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id      TEXT NOT NULL,
    phase        TEXT NOT NULL,      -- ban1 | pick1 | ban2 | pick2
    action_type  TEXT NOT NULL,      -- ban | pick
    side         TEXT NOT NULL,      -- blue | red
    slot         INTEGER NOT NULL,   -- 1..5
    global_order INTEGER NOT NULL,   -- 1..10 (cronológico dentro do tipo)
    champion     TEXT NOT NULL,
    role         TEXT,
    player       TEXT,
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
);

-- Índices que aceleram os filtros do dashboard (liga/patch/data) e os joins.
CREATE INDEX IF NOT EXISTS idx_games_filters ON games(league, patch, match_date);
CREATE INDEX IF NOT EXISTS idx_actions_game  ON draft_actions(game_id);
CREATE INDEX IF NOT EXISTS idx_actions_champ ON draft_actions(champion);
"""


class Database:
    """Wrapper fino sobre sqlite3 com DAO específico do domínio."""

    def __init__(self, db_path=config.DB_PATH):
        self.db_path = str(db_path)
        self.init_schema()

    # ----------------------------------------------------------------- conn
    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            # Semeia as ligas conhecidas (idempotente).
            conn.executemany(
                "INSERT OR IGNORE INTO leagues(key, label) VALUES (?, ?)",
                [(lg["key"], lg["label"]) for lg in config.LEAGUES],
            )

    # -------------------------------------------------------------- writes
    def upsert_team(self, team: TeamInfo) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO teams(name, short, logo_path) VALUES (?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                       short=excluded.short,
                       logo_path=COALESCE(excluded.logo_path, teams.logo_path)""",
                (team.name, team.short, team.logo_path),
            )

    def save_game(self, game: GameDraft) -> None:
        """Upsert de um jogo + reescrita das suas ações de draft (idempotente)."""
        self.upsert_team(game.blue)
        self.upsert_team(game.red)
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO games(game_id, league, patch, match_date,
                                     blue_team, red_team, winner)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(game_id) DO UPDATE SET
                       league=excluded.league, patch=excluded.patch,
                       match_date=excluded.match_date, blue_team=excluded.blue_team,
                       red_team=excluded.red_team, winner=excluded.winner""",
                (game.game_id, game.league, game.patch, game.match_date.isoformat(),
                 game.blue.name, game.red.name, game.winner),
            )
            # Substitui as ações para garantir consistência em re-sync.
            conn.execute("DELETE FROM draft_actions WHERE game_id = ?", (game.game_id,))
            conn.executemany(
                """INSERT INTO draft_actions(game_id, phase, action_type, side,
                       slot, global_order, champion, role, player)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(game.game_id, a.phase, a.action_type, a.side, a.slot,
                  a.global_order, a.champion, a.role, a.player)
                 for a in game.actions],
            )

    def save_games(self, games: Iterable[GameDraft]) -> int:
        count = 0
        for g in games:
            self.save_game(g)
            count += 1
        return count

    # --------------------------------------------------------------- reads
    def list_games(
        self,
        leagues: Optional[list[str]] = None,
        patch: Optional[str] = None,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> list[GameDraft]:
        """Lista jogos (sem as ações) aplicando os filtros do dashboard."""
        sql = "SELECT * FROM games WHERE 1=1"
        params: list = []
        if leagues:
            sql += f" AND league IN ({','.join('?' * len(leagues))})"
            params += leagues
        if patch:
            sql += " AND patch = ?"
            params.append(patch)
        if start:
            sql += " AND match_date >= ?"
            params.append(start.isoformat())
        if end:
            sql += " AND match_date <= ?"
            params.append(end.isoformat())
        sql += " ORDER BY match_date DESC, game_id DESC"

        with self._connect() as conn:
            teams = {r["name"]: r for r in conn.execute("SELECT * FROM teams")}
            rows = conn.execute(sql, params).fetchall()

        def team(name: str) -> TeamInfo:
            r = teams.get(name)
            if r is None:
                return TeamInfo(name=name, short=name[:3].upper())
            return TeamInfo(name=r["name"], short=r["short"], logo_path=r["logo_path"])

        return [
            GameDraft(
                game_id=r["game_id"], league=r["league"], patch=r["patch"],
                match_date=date.fromisoformat(r["match_date"]),
                blue=team(r["blue_team"]), red=team(r["red_team"]),
                winner=r["winner"], actions=[],
            )
            for r in rows
        ]

    def load_draft(self, game_id: str) -> Optional[GameDraft]:
        """Carrega um jogo COM todas as ações do draft, pronto para a tela."""
        games = {g.game_id: g for g in self.list_games()}
        game = games.get(game_id)
        if game is None:
            return None
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM draft_actions WHERE game_id = ? ORDER BY id",
                (game_id,),
            ).fetchall()
        game.actions = [
            DraftAction(
                phase=r["phase"], action_type=r["action_type"], side=r["side"],
                slot=r["slot"], global_order=r["global_order"],
                champion=r["champion"], role=r["role"], player=r["player"],
            )
            for r in rows
        ]
        return game

    def fetch_actions_dataframe_rows(
        self,
        leagues: Optional[list[str]] = None,
        patch: Optional[str] = None,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> list[dict]:
        """
        Retorna ações de draft já cruzadas com o resultado do jogo, em formato
        plano (lista de dicts) -> consumido diretamente pelo StatsEngine/Pandas.

        Cada linha sabe se o lado daquela ação venceu (`won`), o que permite ao
        motor calcular vitórias/derrotas por campeão sem outro join.
        """
        sql = """
            SELECT da.champion, da.action_type, da.side, da.global_order,
                   g.winner, g.league, g.patch, g.match_date, g.game_id
            FROM draft_actions da
            JOIN games g ON g.game_id = da.game_id
            WHERE 1=1
        """
        params: list = []
        if leagues:
            sql += f" AND g.league IN ({','.join('?' * len(leagues))})"
            params += leagues
        if patch:
            sql += " AND g.patch = ?"
            params.append(patch)
        if start:
            sql += " AND g.match_date >= ?"
            params.append(start.isoformat())
        if end:
            sql += " AND g.match_date <= ?"
            params.append(end.isoformat())

        with self._connect() as conn:
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        for r in rows:
            r["won"] = (r["side"] == r["winner"])
        return rows

    def distinct_patches(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT patch FROM games WHERE patch IS NOT NULL "
                "ORDER BY patch DESC"
            ).fetchall()
        return [r["patch"] for r in rows]

    def count_games(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) AS c FROM games").fetchone()["c"]

    def clear_all_games(self) -> None:
        """Remove todos os jogos e ações (ex.: antes de um sync limpo)."""
        with self._connect() as conn:
            conn.execute("DELETE FROM draft_actions")
            conn.execute("DELETE FROM games")
