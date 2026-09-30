"""
Ponto de entrada do LoL Draft Analyzer.

Lê os dados do cache local (SQLite), que é populado com partidas REAIS de 2026
em diante via Leaguepedia. O app abre instantaneamente; o sync é feito sob
demanda (botão "Sincronizar" na UI, ou pela linha de comando).

Uso:
    pip install -r requirements.txt
    python main.py                 # abre o app (lê do cache)
    python main.py --sync          # sincroniza dados de 2026 e depois abre
    python main.py --assets        # baixa todos os ícones de campeões

Flags:
    --sync     puxa dados reais de 2026 da Leaguepedia (com logos) antes de abrir.
    --assets   baixa/atualiza todos os ícones de campeão do Data Dragon.
    --online   permite ao AssetManager baixar ícone que falte sob demanda.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

import config
from src.backend.asset_manager import AssetManager
from src.backend.database import Database
from src.ui import theme
from src.ui.main_window import MainWindow


def main() -> int:
    online = "--online" in sys.argv

    db = Database()

    if "--assets" in sys.argv:
        from src.backend.asset_sync import download_all_champion_icons
        print(download_all_champion_icons(progress=print))

    if "--sync" in sys.argv:
        from src.backend.leaguepedia_client import LeaguepediaClient
        from src.backend.asset_sync import download_team_logos
        client = LeaguepediaClient()
        db.clear_all_games()
        teams: set[str] = set()
        for lg in config.LEAGUES:
            print(f"== {lg['label']} ==")
            games = client.fetch_recent_games(lg["key"], progress=print)
            db.save_games(games)
            for g in games:
                teams.update([g.blue.name, g.red.name])
        download_team_logos(teams, progress=print)

    app = QApplication(sys.argv)
    app.setStyleSheet(theme.stylesheet())

    assets = AssetManager(allow_network=online)
    window = MainWindow(db, assets)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
