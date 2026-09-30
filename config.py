"""
Configuração central e constantes de domínio do LoL Draft Analyzer.

Aqui mora o "conhecimento de regras" do draft competitivo (tournament draft),
usado tanto pelo back-end (parsing das APIs e cálculo de estatísticas) quanto
pelo front-end (renderização cronológica da tela de picks & bans).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

# Data de corte: a aplicação só considera partidas a partir desta data.
DATA_SINCE = date(2026, 1, 1)

# --------------------------------------------------------------------------- #
# Caminhos
# --------------------------------------------------------------------------- #
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "draft_analyzer.sqlite3"
ASSET_CACHE_DIR = DATA_DIR / "assets"
CHAMPION_ICON_DIR = ASSET_CACHE_DIR / "champions"
TEAM_LOGO_DIR = ASSET_CACHE_DIR / "teams"

for _d in (DATA_DIR, ASSET_CACHE_DIR, CHAMPION_ICON_DIR, TEAM_LOGO_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Ligas monitoradas
#   key      -> identificador interno usado no banco e nos filtros
#   label    -> nome exibido na UI
#   region   -> filtro "Region/League" usado na Cargo API da Leaguepedia
# --------------------------------------------------------------------------- #
# 'prefixes' = possíveis inícios do campo OverviewPage na Leaguepedia. Em 2026 a
# Riot fundiu as Américas na LTA, então LCS -> "LTA North" e CBLOL -> "LTA South";
# mantemos os nomes antigos como fallback caso ainda existam páginas legadas.
LEAGUES = [
    {"key": "LEC", "label": "LEC (Europa)", "prefixes": ["LEC"]},
    {"key": "LCK", "label": "LCK (Coreia)", "prefixes": ["LCK"]},
    {"key": "LPL", "label": "LPL (China)", "prefixes": ["LPL"]},
    {"key": "LTA_N", "label": "LTA North (ex-LCS)", "prefixes": ["LTA North", "LTA/North", "LCS"]},
    {"key": "LTA_S", "label": "LTA South (ex-CBLOL)", "prefixes": ["LTA South", "LTA/South", "CBLOL"]},
]
LEAGUE_KEYS = [lg["key"] for lg in LEAGUES]
LEAGUE_BY_KEY = {lg["key"]: lg for lg in LEAGUES}

# --------------------------------------------------------------------------- #
# Sequência do draft competitivo (tournament/pro draft).
#
# Cada entrada descreve UMA ação na ordem cronológica real em que acontece.
#   phase  : fase do draft ('ban1', 'pick1', 'ban2', 'pick2')
#   type   : 'ban' ou 'pick'
#   side   : 'blue' ou 'red'
#   slot   : índice 1..5 do slot DAQUELE time para esse tipo (ban1..5 / pick1..5),
#            usado para casar com as colunas da Leaguepedia (Team1Ban1, etc.)
#
# A ordem da lista É a ordem cronológica de tela (de cima para baixo).
# Referência (lado azul = Team1 / lado vermelho = Team2):
#   Ban  fase 1 : B>R>B>R>B>R  (3 cada)
#   Pick fase 1 : B  R R  B B  R          (B1, R1-R2, B2-B3, R3)
#   Ban  fase 2 : R>B>R>B      (2 cada, vermelho começa)
#   Pick fase 2 : R  B B  R                (R4, B4-B5, R5)
# --------------------------------------------------------------------------- #
DRAFT_SEQUENCE = [
    # --- Fase 1: Banimentos (6) ---
    {"phase": "ban1", "type": "ban", "side": "blue", "slot": 1},
    {"phase": "ban1", "type": "ban", "side": "red", "slot": 1},
    {"phase": "ban1", "type": "ban", "side": "blue", "slot": 2},
    {"phase": "ban1", "type": "ban", "side": "red", "slot": 2},
    {"phase": "ban1", "type": "ban", "side": "blue", "slot": 3},
    {"phase": "ban1", "type": "ban", "side": "red", "slot": 3},
    # --- Fase 1: Escolhas (6) ---
    {"phase": "pick1", "type": "pick", "side": "blue", "slot": 1},  # B1 (first pick)
    {"phase": "pick1", "type": "pick", "side": "red", "slot": 1},   # R1
    {"phase": "pick1", "type": "pick", "side": "red", "slot": 2},   # R2
    {"phase": "pick1", "type": "pick", "side": "blue", "slot": 2},  # B2
    {"phase": "pick1", "type": "pick", "side": "blue", "slot": 3},  # B3
    {"phase": "pick1", "type": "pick", "side": "red", "slot": 3},   # R3
    # --- Fase 2: Banimentos (4) ---
    {"phase": "ban2", "type": "ban", "side": "red", "slot": 4},
    {"phase": "ban2", "type": "ban", "side": "blue", "slot": 4},
    {"phase": "ban2", "type": "ban", "side": "red", "slot": 5},
    {"phase": "ban2", "type": "ban", "side": "blue", "slot": 5},
    # --- Fase 2: Escolhas (4) ---
    {"phase": "pick2", "type": "pick", "side": "red", "slot": 4},   # R4
    {"phase": "pick2", "type": "pick", "side": "blue", "slot": 4},  # B4
    {"phase": "pick2", "type": "pick", "side": "blue", "slot": 5},  # B5
    {"phase": "pick2", "type": "pick", "side": "red", "slot": 5},   # R5
]

PHASE_LABELS = {
    "ban1": "Fase 1 — Banimentos",
    "pick1": "Fase 1 — Escolhas",
    "ban2": "Fase 2 — Banimentos",
    "pick2": "Fase 2 — Escolhas",
}

# Ordem padrão de exibição dos papéis (rotas) numa composição.
ROLES = ["Top", "Jungle", "Mid", "Bot", "Support"]

# --------------------------------------------------------------------------- #
# PESOS DE PRIORIDADE PARA O "PRIO SCORE"
#
# A intuição: quanto MAIS CEDO um campeão é removido do pool (ban de fase 1)
# ou garantido (pick de primeira rotação), MAIOR é a prioridade que os times
# atribuem a ele -- é sinal de que o consideram forte/contestado.
#
# Atribuímos um peso a cada POSIÇÃO GLOBAL do draft (1 = primeiríssima ação do
# tipo, 10 = última). Picks decaem linearmente (B1 first pick = topo). Bans de
# fase 1 valem quase tanto quanto os melhores picks (você bane o que respeita);
# bans de fase 2 valem bem menos (frequentemente são denials situacionais).
#
# O detalhamento matemático completo está em backend/stats_engine.py.
# --------------------------------------------------------------------------- #
PICK_PRIORITY_WEIGHT = {1: 1.00, 2: 0.90, 3: 0.80, 4: 0.70, 5: 0.60,
                        6: 0.50, 7: 0.40, 8: 0.30, 9: 0.20, 10: 0.10}

BAN_PRIORITY_WEIGHT = {1: 0.90, 2: 0.85, 3: 0.80, 4: 0.75, 5: 0.70,
                       6: 0.65, 7: 0.45, 8: 0.40, 9: 0.35, 10: 0.30}

# --------------------------------------------------------------------------- #
# Riot Data Dragon (assets de campeões)
# --------------------------------------------------------------------------- #
DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
DDRAGON_CDN = "https://ddragon.leagueoflegends.com/cdn"
DDRAGON_LOCALE = "en_US"

# --------------------------------------------------------------------------- #
# Leaguepedia (MediaWiki / Cargo API)
# --------------------------------------------------------------------------- #
LEAGUEPEDIA_API = "https://lol.fandom.com/api.php"
HTTP_USER_AGENT = "LoLDraftAnalyzer/0.1 (desktop research tool)"
HTTP_TIMEOUT = 20
