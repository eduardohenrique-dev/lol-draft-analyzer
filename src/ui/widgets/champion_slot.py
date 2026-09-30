"""
Widget de um slot de draft (um ban ou um pick), com estilo de transmissão.

- Pick : ícone "limpo" do campeão + borda na cor do lado + rota/jogador.
- Ban  : ícone dessaturado com traço diagonal + etiqueta "BAN".
O lado (azul/vermelho) define a cor da borda de acento.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                               QLabel, QVBoxLayout, QWidget)

from src.backend.asset_manager import AssetManager
from src.models.draft import DraftAction
from src.ui import theme

ICON_SIZE = 56


class ChampionSlot(QFrame):
    def __init__(self, action: DraftAction, assets: AssetManager,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.action = action
        self.assets = assets
        self._build()

    def _build(self) -> None:
        side_color = theme.SIDE_COLORS[self.action.side]
        soft = theme.SIDE_SOFT[self.action.side]
        is_ban = self.action.is_ban

        self.setObjectName("Slot")
        self.setStyleSheet(
            f"""
            QFrame#Slot {{
                background: {soft if not is_ban else theme.PANEL};
                border: 1px solid {theme.BORDER};
                border-left: 3px solid {side_color};
                border-radius: 8px;
            }}
            """
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 12, 6)
        layout.setSpacing(10)

        # Ícone do campeão (pick limpo / ban estilizado).
        icon = QLabel()
        pix = self.assets.champion_pixmap(self.action.champion, ICON_SIZE, banned=is_ban)
        icon.setPixmap(pix)
        icon.setFixedSize(ICON_SIZE, ICON_SIZE)
        layout.addWidget(icon)

        # Bloco de texto.
        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        name = QLabel(self.action.champion)
        name.setStyleSheet(
            f"font-weight: 700; font-size: 14px; "
            f"color: {theme.TEXT_MUTED if is_ban else theme.TEXT};"
        )
        text_box.addWidget(name)

        if is_ban:
            tag = QLabel("BAN")
            tag.setStyleSheet(
                f"color: {theme.RED}; font-size: 10px; font-weight: 800; letter-spacing: 2px;"
            )
            text_box.addWidget(tag)
        else:
            sub_parts = [p for p in (self.action.role, self.action.player) if p]
            sub = QLabel("  ·  ".join(sub_parts) if sub_parts else "—")
            sub.setObjectName("Muted")
            sub.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
            text_box.addWidget(sub)

        layout.addLayout(text_box)
        layout.addStretch(1)

        if not is_ban:
            self._add_glow(side_color)

    def _add_glow(self, color: str) -> None:
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(18)
        glow.setOffset(0, 0)
        c = QColor(color)
        c.setAlpha(60)
        glow.setColor(c)
        self.setGraphicsEffect(glow)
