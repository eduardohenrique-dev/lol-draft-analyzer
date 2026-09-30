"""
Grava partidas FICTÍCIAS no banco local, para ver a interface sem depender de rede.

Uso (a partir da raiz do projeto):
    python tools/seed_demo.py             # grava os exemplos se o banco estiver vazio
    python tools/seed_demo.py --limpar    # apaga as partidas atuais e grava os exemplos
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backend.database import Database
from src.mock.mock_data import build_mock_games


def main() -> int:
    db = Database()
    if "--limpar" in sys.argv:
        db.clear_all_games()
    if db.count_games() > 0:
        print(f"O banco já tem {db.count_games()} partida(s); nada foi gravado. Use --limpar para trocar.")
        return 0
    gravadas = db.save_games(build_mock_games())
    print(f"{gravadas} partida(s) fictícia(s) gravada(s). Rode: python main.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
