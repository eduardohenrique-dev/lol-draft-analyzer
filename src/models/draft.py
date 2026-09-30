"""
Modelos de domínio (dataclasses) que representam um draft de uma partida.

Estes objetos são a "moeda comum" entre o back-end (que os constrói a partir
da Leaguepedia ou do banco) e o front-end (que os renderiza). Manter o modelo
desacoplado das APIs e da UI facilita trocar a fonte de dados depois.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import config


@dataclass
class TeamInfo:
    """Metadados de uma equipe, lado-agnósticos."""
    name: str
    short: str                       # ex.: "G2", "T1", "LOUD"
    logo_path: Optional[str] = None  # caminho local do logo em cache (ou None)


@dataclass
class DraftAction:
    """
    Uma única ação do draft (um ban ou um pick), já posicionada na timeline.

    `global_order` é a posição cronológica DENTRO do seu tipo (1..10 para picks,
    1..10 para bans). É exatamente a chave usada para olhar os pesos em
    PICK_PRIORITY_WEIGHT / BAN_PRIORITY_WEIGHT no cálculo do Prio Score.
    """
    phase: str                       # 'ban1' | 'pick1' | 'ban2' | 'pick2'
    action_type: str                 # 'ban' | 'pick'
    side: str                        # 'blue' | 'red'
    slot: int                        # 1..5 (slot do time para aquele tipo)
    global_order: int                # 1..10 ordem cronológica do tipo
    champion: str                    # nome do campeão (display name)
    role: Optional[str] = None       # rota (apenas para picks)
    player: Optional[str] = None     # nick do jogador (apenas para picks)

    @property
    def is_ban(self) -> bool:
        return self.action_type == "ban"


@dataclass
class GameDraft:
    """Um jogo completo: metadados + a lista cronológica de ações do draft."""
    game_id: str
    league: str
    patch: str
    match_date: date
    blue: TeamInfo
    red: TeamInfo
    winner: str                      # 'blue' | 'red'
    actions: list[DraftAction] = field(default_factory=list)

    # -- conveniências para a UI ------------------------------------------- #
    def actions_in_phase(self, phase: str) -> list[DraftAction]:
        return [a for a in self.actions if a.phase == phase]

    @property
    def blue_won(self) -> bool:
        return self.winner == "blue"

    @property
    def ordered_phases(self) -> list[str]:
        """Fases na ordem cronológica em que aparecem na sequência do draft."""
        seen: list[str] = []
        for step in config.DRAFT_SEQUENCE:
            if step["phase"] not in seen:
                seen.append(step["phase"])
        return seen
