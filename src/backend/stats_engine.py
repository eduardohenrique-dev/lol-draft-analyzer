"""
Motor de estatísticas — agregação por campeão usando Pandas.

Recebe as ações de draft já filtradas (liga / patch / intervalo de datas) e
produz a tabela do dashboard: Presença %, Picks, Bans, Prio Score, Vitórias,
Derrotas e Win Rate %.

================================================================================
                          A MATEMÁTICA DO PRIO SCORE
================================================================================

PROBLEMA QUE ELE RESOLVE
------------------------
"Win rate" e "presença" não distinguem um campeão que é SEMPRE o primeiro pick
(prioridade máxima) de um que só aparece como último pick de contra-escolha.
O Prio Score captura QUÃO CEDO um campeão é disputado no draft — ou seja, o
quanto os times o tratam como peça de alta prioridade.

INTUIÇÃO
--------
Quanto mais cedo um campeão é:
   * BANIDO na fase 1  -> "tenho medo/respeito, tiro do pool já"
   * ESCOLHIDO cedo     -> "é tão forte que garanto antes que o adversário pegue"
...maior é a prioridade. Picks e bans tardios (fase 2) carregam pouco sinal de
prioridade (são, em geral, ajustes situacionais / contra-picks).

PASSO 1 — PESO POSICIONAL
-------------------------
A cada AÇÃO atribuímos um peso conforme sua posição cronológica global (1..10),
definidos em config.py:

  PICK_PRIORITY_WEIGHT  -> decai linear: B1(1.00) ... R5(0.10)
  BAN_PRIORITY_WEIGHT   -> fase 1 alta (0.90..0.65), fase 2 baixa (0.45..0.30)

Um campeão aparece no máximo UMA vez por jogo (se foi banido, não pode ser
pickado, e cada campeão é pickado uma vez). Logo, por jogo, ele contribui com
no máximo um peso.

PASSO 2 — AGREGAÇÃO E NORMALIZAÇÃO
----------------------------------
        prio_raw(campeão) = Σ  peso(ação)        (soma sobre todos os jogos)

        PrioScore(campeão) = 100 * prio_raw / N_games_no_filtro

onde N_games_no_filtro é o total de jogos do recorte atual (NÃO o número de
jogos em que o campeão apareceu). Isso faz o Prio Score combinar, num único
número de 0 a 100, DUAS coisas que definem prioridade:

   (a) FREQUÊNCIA  -> aparecer em muitos jogos aumenta a soma;
   (b) PRECOCIDADE -> aparecer cedo dá peso maior por aparição.

INTERPRETAÇÃO DA ESCALA
-----------------------
   * 100  = teoricamente, first pick (B1) em 100% dos jogos do recorte.
   *  ~85 = praticamente permabanido na fase 1 (ban ~0.85 todo jogo).
   *  ~25 = presença mediana e/ou aparições tardias.
   *   ~0 = quase nunca disputado, ou só em picks finais esporádicos.

Por que normalizar por N_games e não por aparições? Porque dividir por
aparições mediria só "quando aparece, é cedo?" e perderia a frequência — um
campeão pickado B1 uma única vez no split inteiro empataria com um first-pick
recorrente. Para prioridade competitiva, frequência importa, então ela entra.
================================================================================
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

import config
from src.backend.database import Database


# Colunas finais expostas para a UI (ordem das colunas do data grid).
STAT_COLUMNS = [
    "champion", "presence_pct", "picks", "bans", "prio_score",
    "wins", "losses", "win_rate_pct",
]

COLUMN_LABELS = {
    "champion": "Campeão",
    "presence_pct": "Presença %",
    "picks": "Picks",
    "bans": "Bans",
    "prio_score": "Prio Score",
    "wins": "Vitórias",
    "losses": "Derrotas",
    "win_rate_pct": "Win Rate %",
}


def _priority_weight(action_type: str, global_order: int) -> float:
    """Peso posicional de uma ação. Ver explicação no topo do módulo."""
    table = config.PICK_PRIORITY_WEIGHT if action_type == "pick" else config.BAN_PRIORITY_WEIGHT
    return table.get(int(global_order), 0.0)


class StatsEngine:
    """Calcula a tabela agregada de campeões a partir do banco."""

    def __init__(self, db: Database):
        self.db = db

    def compute(
        self,
        leagues: Optional[list[str]] = None,
        patch: Optional[str] = None,
        start: Optional[date] = None,
        end: Optional[date] = None,
    ) -> pd.DataFrame:
        rows = self.db.fetch_actions_dataframe_rows(
            leagues=leagues, patch=patch, start=start, end=end
        )
        if not rows:
            return pd.DataFrame(columns=STAT_COLUMNS)

        df = pd.DataFrame(rows)

        # Total de jogos DISTINTOS no recorte (denominador de presença e prio).
        total_games = df["game_id"].nunique()

        # Peso de prioridade por ação (vetorizado).
        df["prio_weight"] = df.apply(
            lambda r: _priority_weight(r["action_type"], r["global_order"]), axis=1
        )

        # Máscaras para separar picks de bans.
        is_pick = df["action_type"] == "pick"
        df["is_pick"] = is_pick
        df["is_ban"] = ~is_pick
        # Vitória/derrota só contam quando o campeão foi PICKADO.
        df["pick_win"] = is_pick & df["won"]
        df["pick_loss"] = is_pick & ~df["won"]

        grouped = df.groupby("champion").agg(
            picks=("is_pick", "sum"),
            bans=("is_ban", "sum"),
            prio_raw=("prio_weight", "sum"),
            wins=("pick_win", "sum"),
            losses=("pick_loss", "sum"),
        ).reset_index()

        # --- Métricas derivadas -------------------------------------------- #
        # Presença = (jogos em que foi pickado OU banido) / total de jogos.
        # Como há no máx. 1 aparição por jogo, picks+bans = nº de jogos com o campeão.
        grouped["presence_pct"] = (
            (grouped["picks"] + grouped["bans"]) / total_games * 100
        ).round(1)

        # Prio Score normalizado (ver doc no topo).
        grouped["prio_score"] = (grouped["prio_raw"] / total_games * 100).round(1)

        # Win rate sobre jogos em que foi efetivamente jogado.
        played = grouped["wins"] + grouped["losses"]
        grouped["win_rate_pct"] = (
            (grouped["wins"] / played.where(played > 0) * 100).round(1)
        ).fillna(0.0)

        # Tipagem inteira para colunas de contagem.
        for col in ("picks", "bans", "wins", "losses"):
            grouped[col] = grouped[col].astype(int)

        result = grouped[STAT_COLUMNS].sort_values(
            "presence_pct", ascending=False, ignore_index=True
        )
        return result
