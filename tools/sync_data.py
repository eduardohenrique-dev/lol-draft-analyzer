"""
Sincroniza dados REAIS de 2026 da Leaguepedia para o banco local.

Faz UMA única requisição combinando todas as ligas (minimiza o rate limit) e
salva no SQLite. Como o resultado fica em cache, roda só de vez em quando.

Uso (a partir da raiz do projeto):
    python tools/sync_data.py                 # puxa 2026 (1 request), limpa antes
    python tools/sync_data.py --logos         # também baixa logos dos times
    python tools/sync_data.py --wait 90       # espera Ns antes (rate limit frio)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from src.backend.database import Database
from src.backend.leaguepedia_client import LeaguepediaClient


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    wait = 0
    if "--wait" in sys.argv:
        wait = int(sys.argv[sys.argv.index("--wait") + 1])
    if wait:
        log(f"Aguardando {wait}s para o rate limit esfriar…")
        time.sleep(wait)

    db = Database()
    # Backoff inicial LONGO: a janela de rate limit parece deslizante, então
    # retentar rápido só reinicia o cooldown. Esperamos de verdade entre tentativas.
    client = LeaguepediaClient(min_gap=8.0, max_retries=4, initial_backoff=150.0)

    try:
        games = client.fetch_all_2026(since=config.DATA_SINCE, progress=log)
    except Exception as e:
        log(f"FALHA no sync: {e}")
        return 1

    if not games:
        log("Nenhum jogo de 2026 retornado (verifique os prefixos das ligas).")
        return 1

    db.clear_all_games()
    saved = db.save_games(games)

    # Resumo por liga.
    by_league: dict[str, int] = {}
    teams: set[str] = set()
    for g in games:
        by_league[g.league] = by_league.get(g.league, 0) + 1
        teams.update([g.blue.name, g.red.name])
    log(f"\nSalvos {saved} jogos de 2026:")
    for k, v in sorted(by_league.items()):
        log(f"   {k}: {v}")
    log(f"Patches: {db.distinct_patches()}")

    if "--logos" in sys.argv and teams:
        from src.backend.asset_sync import download_team_logos
        log(f"\nBaixando logos de {len(teams)} times…")
        log(str(download_team_logos(teams, progress=log)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
