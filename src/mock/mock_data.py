"""
Dados de exemplo (FICTÍCIOS) para ver a interface funcionando sem depender de rede.

Times, jogadores e partidas são inventados: nada aqui representa uma equipe ou um
jogador real. Os campeões são reais (é o conteúdo do jogo), e cada draft segue a
sequência oficial de `config.DRAFT_SEQUENCE`, com 10 banimentos e 10 escolhas sem
repetir campeão.

As partidas são geradas de forma determinística (semente fixa), então o banco de
exemplo sai sempre igual, e o Prio Score de um campeão pode ser conferido à mão.

`build_mock_games()` devolve os drafts; `seed_database(db)` grava no SQLite.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import config
from src.backend.database import Database
from src.models.draft import DraftAction, GameDraft, TeamInfo

# --------------------------------------------------------------------------- #
# Times fictícios: (nome, sigla, [top, jungle, mid, bot, support])
# --------------------------------------------------------------------------- #
TEAMS = {
    "AUR": ("Aurora Esports", ["Rocha", "Cipó", "Lume", "Faísca", "Âncora"]),
    "BRU": ("Bruma Gaming", ["Neblina", "Pardal", "Tamoio", "Vento", "Zéfiro"]),
    "CIP": ("Cerrado Club", ["Jabuti", "Curió", "Sabiá", "Tucano", "Gralha"]),
    "DUN": ("Duna Team", ["Areia", "Miragem", "Oásis", "Salina", "Duneiro"]),
    "ECL": ("Eclipse", ["Umbra", "Penumbra", "Corvo", "Astral", "Zênite"]),
    "FAG": ("Fagulha", ["Brasa", "Centelha", "Ígneo", "Pólvora", "Ardor"]),
    "GAR": ("Garoa Gaming", ["Chuvisco", "Orvalho", "Trovão", "Relâmpago", "Nimbo"]),
    "HOR": ("Horizonte", ["Alvorada", "Poente", "Meridiano", "Rumo", "Farol"]),
    "ILH": ("Ilha Verde", ["Coral", "Maré", "Recife", "Jangada", "Restinga"]),
    "JAC": ("Jacarandá", ["Ipê", "Cedro", "Aroeira", "Jatobá", "Pequi"]),
}

# Confrontos: (liga, sigla azul, sigla vermelho). As ligas são as de config.LEAGUES.
CONFRONTOS = [
    ("LEC", "AUR", "BRU"),
    ("LEC", "BRU", "AUR"),
    ("LCK", "CIP", "DUN"),
    ("LCK", "DUN", "CIP"),
    ("LPL", "ECL", "FAG"),
    ("LPL", "FAG", "ECL"),
    ("LTA_N", "GAR", "HOR"),
    ("LTA_N", "HOR", "GAR"),
    ("LTA_S", "ILH", "JAC"),
    ("LTA_S", "JAC", "ILH"),
    ("LEC", "AUR", "BRU"),
    ("LCK", "DUN", "CIP"),
]

# Campeões por rota, dos mais aos menos disputados (a ordem vira o peso do sorteio).
POOL = {
    "Top": ["Jax", "Aatrox", "K'Sante", "Gnar", "Camille", "Ornn", "Renekton", "Sett", "Gwen"],
    "Jungle": ["Sejuani", "Vi", "Lee Sin", "Maokai", "Viego", "Xin Zhao", "Nidalee", "Rek'Sai", "Jarvan IV"],
    "Mid": ["Ahri", "Azir", "Orianna", "Aurelion Sol", "Syndra", "Viktor", "Taliyah", "Corki", "Sylas"],
    "Bot": ["Varus", "Zeri", "Kalista", "Aphelios", "Jinx", "Ashe", "Ezreal", "Lucian", "Kai'Sa"],
    "Support": ["Nautilus", "Rell", "Rakan", "Renata Glasc", "Senna", "Leona", "Alistar", "Braum", "Lulu"],
}
PAPEIS = config.ROLES  # Top, Jungle, Mid, Bot, Support


def _sortear(rng: random.Random, opcoes: list[str], usados: set[str]) -> str:
    """Escolhe uma opção ainda não usada, favorecendo as primeiras da lista."""
    livres = [c for c in opcoes if c not in usados]
    pesos = [len(livres) - i for i in range(len(livres))]
    escolhido = rng.choices(livres, weights=pesos, k=1)[0]
    usados.add(escolhido)
    return escolhido


def _build_game(
    game_id: str, league: str, patch: str, match_date: date,
    blue: tuple[str, str], red: tuple[str, str], winner: str,
    blue_bans: list[str], red_bans: list[str],
    blue_picks: list[tuple[str, str, str]],   # (campeão, rota, jogador) em ORDEM DE PICK
    red_picks: list[tuple[str, str, str]],
) -> GameDraft:
    """Monta um GameDraft percorrendo a sequência oficial do draft."""
    blue_team = TeamInfo(name=blue[0], short=blue[1])
    red_team = TeamInfo(name=red[0], short=red[1])

    pools = {
        ("blue", "ban"): blue_bans,
        ("red", "ban"): red_bans,
        ("blue", "pick"): blue_picks,
        ("red", "pick"): red_picks,
    }
    order_counter = {"ban": 0, "pick": 0}
    actions: list[DraftAction] = []

    for step in config.DRAFT_SEQUENCE:
        pool = pools[(step["side"], step["type"])]
        idx = step["slot"] - 1
        if idx >= len(pool):
            continue
        order_counter[step["type"]] += 1
        if step["type"] == "ban":
            champ, role, player = pool[idx], None, None
        else:
            champ, role, player = pool[idx]
        actions.append(DraftAction(
            phase=step["phase"], action_type=step["type"], side=step["side"],
            slot=step["slot"], global_order=order_counter[step["type"]],
            champion=champ, role=role, player=player,
        ))

    return GameDraft(
        game_id=game_id, league=league, patch=patch, match_date=match_date,
        blue=blue_team, red=red_team, winner=winner, actions=actions,
    )


def build_mock_games() -> list[GameDraft]:
    rng = random.Random(2026)
    inicio = max(config.DATA_SINCE, date(2026, 3, 2))
    jogos: list[GameDraft] = []

    for n, (liga, azul, vermelho) in enumerate(CONFRONTOS, start=1):
        usados: set[str] = set()

        # Banimentos: os campeões mais disputados de cada rota entram primeiro.
        cobicados = [c for papel in PAPEIS for c in POOL[papel][:3]]
        bans = [_sortear(rng, cobicados, usados) for _ in range(10)]
        bans_azul, bans_vermelho = bans[:5], bans[5:]

        def picks_do_time(sigla: str) -> list[tuple[str, str, str]]:
            jogadores = TEAMS[sigla][1]
            escolhas = [(_sortear(rng, POOL[p], usados), p, jogadores[i]) for i, p in enumerate(PAPEIS)]
            rng.shuffle(escolhas)  # a ordem em que cada rota foi escolhida varia
            return escolhas

        jogos.append(_build_game(
            game_id=f"{liga}-2026-{n:03d}",
            league=liga,
            patch="16.4" if n > 6 else "16.3",
            match_date=inicio + timedelta(days=n * 2),
            blue=(TEAMS[azul][0], azul),
            red=(TEAMS[vermelho][0], vermelho),
            winner="blue" if rng.random() < 0.5 else "red",
            blue_bans=bans_azul,
            red_bans=bans_vermelho,
            blue_picks=picks_do_time(azul),
            red_picks=picks_do_time(vermelho),
        ))
    return jogos


def seed_database(db: Database) -> int:
    """Grava os exemplos no banco se ainda não houver jogos. Retorna o nº gravado."""
    if db.count_games() > 0:
        return 0
    return db.save_games(build_mock_games())
