"""
Sincroniza assets visuais localmente.

Uso:
    python tools/sync_assets.py            # baixa todos os ícones de campeão
    python tools/sync_assets.py --teams    # também baixa logos dos times do banco

Rodar a partir da raiz do projeto.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backend.asset_sync import download_all_champion_icons, download_team_logos


def main() -> int:
    print("== Baixando ícones de campeões (Data Dragon) ==", flush=True)
    summary = download_all_champion_icons(progress=lambda m: print(m, flush=True))
    print(summary, flush=True)

    if "--teams" in sys.argv:
        from src.backend.database import Database
        db = Database()
        names = set()
        for g in db.list_games():
            names.add(g.blue.name)
            names.add(g.red.name)
        print(f"\n== Baixando logos de {len(names)} times (Leaguepedia) ==", flush=True)
        res = download_team_logos(names, progress=lambda m: print(m, flush=True))
        print(res, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
