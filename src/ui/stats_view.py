"""
Dashboard de Estatísticas — data grid interativo + painel de filtros.

- Tabela ordenável por qualquer coluna (clique no cabeçalho). A ordenação é
  NUMÉRICA (não alfabética) graças a um sortRole dedicado que devolve o valor
  bruto da célula.
- Coluna "Campeão" mostra o ícone (Data Dragon ou placeholder) + nome.
- Painel de filtros: Liga (cada uma ou "Todas combinadas"), Patch, intervalo de
  datas. Ao aplicar, o StatsEngine RECALCULA tudo do zero com base no recorte.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QSortFilterProxyModel
from PySide6.QtWidgets import (QComboBox, QDateEdit, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QPushButton, QTableView,
                               QVBoxLayout, QWidget)

import config
from src.backend.asset_manager import AssetManager
from src.backend.stats_engine import COLUMN_LABELS, STAT_COLUMNS, StatsEngine
from src.ui import theme

RAW_VALUE_ROLE = Qt.UserRole + 1     # valor bruto p/ ordenação numérica


class ChampionStatsModel(QAbstractTableModel):
    """Adapta o DataFrame de estatísticas para o QTableView."""

    def __init__(self, assets: AssetManager, parent=None):
        super().__init__(parent)
        self.assets = assets
        self._df = pd.DataFrame(columns=STAT_COLUMNS)

    def set_dataframe(self, df: pd.DataFrame) -> None:
        self.beginResetModel()
        self._df = df.reset_index(drop=True)
        self.endResetModel()

    # -- dimensões --------------------------------------------------------- #
    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(STAT_COLUMNS)

    # -- dados ------------------------------------------------------------- #
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        col = STAT_COLUMNS[index.column()]
        value = self._df.iloc[index.row()][col]

        if role == RAW_VALUE_ROLE:
            # Valor nativo do Python: o Qt não compara tipos do numpy (numpy.float64) e
            # deixaria a ordenação numérica sem efeito.
            return value.item() if hasattr(value, "item") else value
        if role == Qt.DisplayRole:
            if col in ("presence_pct", "win_rate_pct"):
                return f"{value:.1f}%"
            if col == "prio_score":
                return f"{value:.1f}"
            return str(value)
        if role == Qt.DecorationRole and col == "champion":
            return self.assets.champion_pixmap(str(value), size=28)
        if role == Qt.TextAlignmentRole and col != "champion":
            return int(Qt.AlignCenter)
        if role == Qt.ForegroundRole and col == "prio_score":
            from PySide6.QtGui import QColor
            return QColor(theme.GOLD)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return COLUMN_LABELS[STAT_COLUMNS[section]]
        return section + 1


class StatsView(QWidget):
    def __init__(self, engine: StatsEngine, assets: AssetManager, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.assets = assets
        self._build()
        self.reload()

    # ------------------------------------------------------------- UI
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        root.addWidget(self._filter_panel())

        self.model = ChampionStatsModel(self.assets)
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(RAW_VALUE_ROLE)   # ordenação pelo valor bruto

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 200)
        self.table.setIconSize(self.table.iconSize().scaled(28, 28, Qt.KeepAspectRatio))
        root.addWidget(self.table, 1)

    def _filter_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("Panel")
        lay = QHBoxLayout(panel)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(16)

        # Liga
        self.league_combo = QComboBox()
        self.league_combo.addItem("Todas (combinadas)", userData=None)
        for lg in config.LEAGUES:
            self.league_combo.addItem(lg["label"], userData=lg["key"])
        lay.addLayout(self._field("LIGA", self.league_combo))

        # Patch
        self.patch_combo = QComboBox()
        self._refresh_patches()
        lay.addLayout(self._field("PATCH", self.patch_combo))

        # Datas — limitadas ao período coberto pela aplicação (2026 em diante).
        from PySide6.QtCore import QDate
        since = QDate(config.DATA_SINCE.year, config.DATA_SINCE.month, config.DATA_SINCE.day)
        today = QDate.currentDate()

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd/MM/yyyy")
        self.date_from.setDateRange(since, today)   # não deixa escolher fora do range
        self.date_from.setDate(since)
        lay.addLayout(self._field("DE", self.date_from))

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd/MM/yyyy")
        self.date_to.setDateRange(since, today)
        self.date_to.setDate(today)
        lay.addLayout(self._field("ATÉ", self.date_to))

        # "De" nunca pode passar de "Até" e vice-versa.
        self.date_from.dateChanged.connect(
            lambda d: self.date_to.setMinimumDate(d)
        )
        self.date_to.dateChanged.connect(
            lambda d: self.date_from.setMaximumDate(d)
        )

        lay.addStretch(1)
        apply_btn = QPushButton("Aplicar filtros")
        apply_btn.setCursor(Qt.PointingHandCursor)
        apply_btn.setStyleSheet(
            f"QPushButton {{ background: {theme.BLUE}; color: white; font-weight: 700; "
            f"border: none; border-radius: 6px; padding: 8px 18px; }}"
            f"QPushButton:hover {{ background: {theme.GOLD}; color: {theme.BG}; }}"
        )
        apply_btn.clicked.connect(self.reload)
        lay.addWidget(apply_btn, alignment=Qt.AlignBottom)
        return panel

    def _field(self, label: str, widget: QWidget) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(4)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;"
        )
        box.addWidget(lbl)
        box.addWidget(widget)
        return box

    def _refresh_patches(self) -> None:
        self.patch_combo.clear()
        self.patch_combo.addItem("Todos", userData=None)
        for p in self.engine.db.distinct_patches():
            self.patch_combo.addItem(p, userData=p)

    # ------------------------------------------------------------- dados
    def reload(self) -> None:
        league = self.league_combo.currentData()
        leagues = [league] if league else None
        patch = self.patch_combo.currentData()

        start: date = self.date_from.date().toPython()
        end: date = self.date_to.date().toPython()

        df = self.engine.compute(leagues=leagues, patch=patch, start=start, end=end)
        self.model.set_dataframe(df)
        # Ordena por Presença % desc como padrão inicial.
        self.table.sortByColumn(STAT_COLUMNS.index("presence_pct"), Qt.DescendingOrder)
