"""
Janela principal — organiza as abas (Draft / Estatísticas) e o seletor de jogo.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QTabWidget,
                               QVBoxLayout, QWidget, QMainWindow)

from src.backend.asset_manager import AssetManager
from src.backend.database import Database
from src.backend.stats_engine import StatsEngine
from src.ui import theme
from src.ui.draft_view import DraftView
from src.ui.stats_view import StatsView


class MainWindow(QMainWindow):
    def __init__(self, db: Database, assets: AssetManager):
        super().__init__()
        self.db = db
        self.assets = assets
        self.engine = StatsEngine(db)

        self.setWindowTitle("LoL Draft Analyzer")
        self.resize(1180, 860)

        tabs = QTabWidget()
        tabs.addTab(self._build_draft_tab(), "DRAFT")
        tabs.addTab(StatsView(self.engine, self.assets), "ESTATÍSTICAS")
        self.setCentralWidget(tabs)

        self._populate_games()

    # ------------------------------------------------------------- draft tab
    def _build_draft_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(16, 16, 16, 0)
        lay.setSpacing(12)

        # Barra de seleção de partida.
        bar = QHBoxLayout()
        title = QLabel("Visualização de Draft")
        title.setObjectName("H2")
        bar.addWidget(title)
        bar.addStretch(1)
        bar.addWidget(QLabel("Partida:"))
        self.game_combo = QComboBox()
        self.game_combo.setMinimumWidth(360)
        self.game_combo.currentIndexChanged.connect(self._on_game_changed)
        bar.addWidget(self.game_combo)
        lay.addLayout(bar)

        self.draft_view = DraftView(self.assets)
        lay.addWidget(self.draft_view, 1)
        return page

    def _populate_games(self) -> None:
        self.game_combo.blockSignals(True)
        self.game_combo.clear()
        for g in self.db.list_games():
            label = f"[{g.league}] {g.blue.name} vs {g.red.name}  ·  {g.match_date.isoformat()}"
            self.game_combo.addItem(label, userData=g.game_id)
        self.game_combo.blockSignals(False)
        if self.game_combo.count():
            self._on_game_changed(0)
        else:
            self.draft_view.show_empty(
                "Nenhuma partida no banco.\n\n"
                "Rode  python main.py --sync  para baixar os dados de 2026 da Leaguepedia."
            )

    def _on_game_changed(self, index: int) -> None:
        game_id = self.game_combo.itemData(index)
        if game_id is None:
            return
        game = self.db.load_draft(game_id)
        if game is not None:
            self.draft_view.show_draft(game)
