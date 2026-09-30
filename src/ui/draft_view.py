"""
Tela de Visualização de Draft.

Reproduz a tela de picks & bans com LEITURA VERTICAL (de cima para baixo),
intercalando os lados em ordem cronológica real do draft:

    [ HEADER: Equipe Azul   vs   Equipe Vermelha  + resultado ]
    ----------------------------------------------------------
    FASE 1 — BANIMENTOS
        B-ban1                              (azul à esquerda)
                                  R-ban1    (vermelho à direita)
        ...
    FASE 1 — ESCOLHAS
        B1 (first pick)
                                  R1
                                  R2
        B2
        ...
    (e assim por diante para fase 2)

Cada AÇÃO é uma linha própria, alinhada ao seu lado, com o número cronológico
no centro — então a coluna que "anda" para a esquerda/direita revela o zig-zag
do draft. O vencedor recebe selo dourado e leve brilho no nome.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

import config
from src.backend.asset_manager import AssetManager
from src.models.draft import DraftAction, GameDraft
from src.ui import theme
from src.ui.widgets.champion_slot import ChampionSlot


class DraftView(QWidget):
    def __init__(self, assets: AssetManager, parent=None):
        super().__init__(parent)
        self.assets = assets
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)
        self._content_holder = QVBoxLayout()
        self._root.addLayout(self._content_holder)

    # ------------------------------------------------------------- API
    def show_empty(self, message: str) -> None:
        """Estado vazio (ex.: banco sem jogos -> sugerir sincronizar)."""
        self._clear(self._content_holder)
        lbl = QLabel(message)
        lbl.setObjectName("Muted")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 15px; padding: 60px;")
        self._content_holder.addWidget(lbl)

    def show_draft(self, game: GameDraft) -> None:
        """Renderiza um GameDraft, limpando o conteúdo anterior."""
        self._clear(self._content_holder)
        self._content_holder.addWidget(self._build_header(game))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 8, 16, 16)
        body_layout.setSpacing(4)

        for phase in game.ordered_phases:
            body_layout.addWidget(self._phase_header(config.PHASE_LABELS[phase]))
            for action in game.actions_in_phase(phase):
                body_layout.addWidget(self._action_row(action))

        body_layout.addStretch(1)
        scroll.setWidget(body)
        self._content_holder.addWidget(scroll)

    # ------------------------------------------------------------- header
    def _build_header(self, game: GameDraft) -> QWidget:
        header = QFrame()
        header.setObjectName("Panel")
        lay = QHBoxLayout(header)
        lay.setContentsMargins(20, 16, 20, 16)

        lay.addWidget(self._team_block(game.blue, "blue", game.blue_won), 1)

        center = QVBoxLayout()
        center.setAlignment(Qt.AlignCenter)
        vs = QLabel("VS")
        vs.setObjectName("H1")
        vs.setAlignment(Qt.AlignCenter)
        meta = QLabel(f"{game.league}  ·  Patch {game.patch}  ·  {game.match_date.isoformat()}")
        meta.setObjectName("Muted")
        meta.setAlignment(Qt.AlignCenter)
        center.addWidget(vs)
        center.addWidget(meta)
        lay.addLayout(center)

        lay.addWidget(self._team_block(game.red, "red", not game.blue_won), 1)
        return header

    def _team_block(self, team, side: str, won: bool) -> QWidget:
        color = theme.SIDE_COLORS[side]
        align = Qt.AlignLeft if side == "blue" else Qt.AlignRight

        # Bloco de texto (rótulo do lado, nome, resultado).
        box = QVBoxLayout()
        box.setAlignment(align)
        side_label = QLabel("LADO AZUL" if side == "blue" else "LADO VERMELHO")
        side_label.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: 800; letter-spacing: 2px;"
        )
        side_label.setAlignment(align)

        name = QLabel(team.name)
        name.setObjectName("H1")
        name.setAlignment(align)
        if won:
            name.setStyleSheet(f"color: {theme.GOLD};")

        result = QLabel("VITÓRIA" if won else "DERROTA")
        result.setAlignment(align)
        result.setStyleSheet(
            f"color: {theme.GOLD if won else theme.TEXT_MUTED}; "
            f"font-weight: 800; letter-spacing: 2px; font-size: 12px;"
        )
        box.addWidget(side_label)
        box.addWidget(name)
        box.addWidget(result)

        # Logo do time (real ou placeholder com a sigla).
        logo = QLabel()
        logo.setPixmap(self.assets.team_pixmap(team.name, team.short, size=64))
        logo.setFixedSize(64, 64)

        wrapper = QWidget()
        h = QHBoxLayout(wrapper)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(14)
        if side == "blue":
            h.addWidget(logo)
            h.addLayout(box)
            h.addStretch(1)
        else:
            h.addStretch(1)
            h.addLayout(box)
            h.addWidget(logo)
        return wrapper

    # ------------------------------------------------------------- body
    def _phase_header(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setObjectName("PhaseHeader")
        return lbl

    def _action_row(self, action: DraftAction) -> QWidget:
        """
        Uma linha = uma ação. O slot fica do lado do time; o outro lado fica
        vazio; o centro mostra o número cronológico (1..n do tipo).
        """
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        slot = ChampionSlot(action, self.assets)
        slot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        order_badge = QLabel(f"{action.global_order:02d}")
        order_badge.setFixedWidth(34)
        order_badge.setAlignment(Qt.AlignCenter)
        order_badge.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-weight: 800; font-size: 12px;"
        )

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        if action.side == "blue":
            lay.addWidget(slot, 1)
            lay.addWidget(order_badge)
            lay.addWidget(spacer, 1)
        else:
            lay.addWidget(spacer, 1)
            lay.addWidget(order_badge)
            lay.addWidget(slot, 1)
        return row

    # ------------------------------------------------------------- util
    def _clear(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                self._clear(item.layout())
