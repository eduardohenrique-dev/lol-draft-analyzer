"""
Gerenciador de assets visuais (ícones de campeão) para a UI.

Objetivos:
    * Carregamento INSTANTÂNEO: serve do cache em disco; só baixa se faltar.
    * Funciona OFFLINE: se não houver ícone (ex.: modo mock sem rede), gera um
      placeholder determinístico (cor derivada do nome + iniciais).
    * Estilo de BAN embutido: dessatura o ícone e desenha um traço diagonal,
      como nas transmissões oficiais.

Mantém um cache em memória de QPixmap para não reprocessar a cada repintura.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import (QColor, QFont, QImage, QLinearGradient, QPainter,
                           QPen, QPixmap)

import config
from src.backend.asset_sync import load_champion_index, _safe
from src.backend.datadragon_client import DataDragonClient, normalize_champion_id

# Paleta de cores para placeholders (escolhida por hash do nome do campeão).
_PLACEHOLDER_COLORS = [
    "#6C5CE7", "#00B894", "#0984E3", "#E17055", "#E84393",
    "#FDCB6E", "#00CEC9", "#D63031", "#A29BFE", "#55EFC4",
]


class AssetManager:
    def __init__(self, ddragon: Optional[DataDragonClient] = None, allow_network: bool = False):
        # allow_network=False por padrão -> ideal para validar a UI com mocks.
        self.ddragon = ddragon or DataDragonClient()
        self.allow_network = allow_network
        self._cache: dict[tuple, QPixmap] = {}
        # Índice nome->id do Data Dragon (resolve Wukong->MonkeyKing, etc.).
        self._champ_index = load_champion_index()

    # --------------------------------------------------------------- public
    def champion_pixmap(self, display_name: str, size: int = 64, banned: bool = False) -> QPixmap:
        key = (display_name, size, banned)
        if key in self._cache:
            return self._cache[key]

        pix = self._load_from_disk(display_name, size)
        if pix is None and self.allow_network:
            pix = self._download_and_cache(display_name, size)
        if pix is None:
            pix = self._placeholder(display_name, size)

        if banned:
            pix = self._apply_ban_style(pix)

        self._cache[key] = pix
        return pix

    def team_pixmap(self, team_name: str, short: str = "", size: int = 48) -> QPixmap:
        """Logo do time (cache em disco) ou placeholder com a sigla."""
        key = ("team", team_name, size)
        if key in self._cache:
            return self._cache[key]
        path = config.TEAM_LOGO_DIR / f"{_safe(team_name)}.png"
        pix: Optional[QPixmap] = None
        if path.exists():
            loaded = QPixmap(str(path))
            if not loaded.isNull():
                pix = loaded.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if pix is None:
            pix = self._placeholder(short or team_name, size)
        self._cache[key] = pix
        return pix

    # --------------------------------------------------------------- helpers
    def _resolve_champion_id(self, display_name: str) -> str:
        """Resolve o id do Data Dragon: 1º pelo índice, depois pela heurística."""
        if self._champ_index:
            hit = self._champ_index.get(display_name.lower())
            if hit:
                return hit
        return normalize_champion_id(display_name)

    def _icon_path(self, display_name: str):
        champ_id = self._resolve_champion_id(display_name)
        return config.CHAMPION_ICON_DIR / f"{champ_id}.png"

    def _load_from_disk(self, display_name: str, size: int) -> Optional[QPixmap]:
        path = self._icon_path(display_name)
        if path.exists():
            pix = QPixmap(str(path))
            if not pix.isNull():
                return pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return None

    def _download_and_cache(self, display_name: str, size: int) -> Optional[QPixmap]:
        data = self.ddragon.download_icon(display_name)
        if not data:
            return None
        path = self._icon_path(display_name)
        path.write_bytes(data)
        pix = QPixmap(str(path))
        if pix.isNull():
            return None
        return pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _placeholder(self, display_name: str, size: int) -> QPixmap:
        """Tile colorido com as iniciais do campeão — determinístico por nome."""
        color = QColor(_PLACEHOLDER_COLORS[hash(display_name) % len(_PLACEHOLDER_COLORS)])
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, 0, size)
        grad.setColorAt(0, color.lighter(120))
        grad.setColorAt(1, color.darker(135))
        painter.setBrush(grad)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, size, size, size * 0.12, size * 0.12)

        initials = "".join(w[0] for w in display_name.split()[:2]).upper() or display_name[:2].upper()
        painter.setPen(QPen(QColor("#FFFFFF")))
        font = QFont("Segoe UI", int(size * 0.34), QFont.Bold)
        painter.setFont(font)
        painter.drawText(pix.rect(), Qt.AlignCenter, initials)
        painter.end()
        return pix

    def _apply_ban_style(self, pix: QPixmap) -> QPixmap:
        """Dessatura (grayscale) e desenha o traço diagonal de banimento."""
        img = pix.toImage().convertToFormat(QImage.Format_Grayscale8)
        styled = QPixmap.fromImage(img.convertToFormat(QImage.Format_ARGB32))

        painter = QPainter(styled)
        painter.setRenderHint(QPainter.Antialiasing)
        # Escurece um pouco.
        painter.fillRect(styled.rect(), QColor(0, 0, 0, 90))
        # Traço diagonal vermelho.
        pen = QPen(QColor("#FF4655"))
        pen.setWidth(max(2, styled.width() // 16))
        painter.setPen(pen)
        w, h = styled.width(), styled.height()
        painter.drawLine(QPointF(w * 0.12, h * 0.12), QPointF(w * 0.88, h * 0.88))
        painter.end()
        return styled
