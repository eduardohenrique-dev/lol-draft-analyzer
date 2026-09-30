"""
Sincronização de assets visuais (executar uma vez / sob demanda).

- Campeões: baixa TODOS os ícones do Riot Data Dragon e constrói um índice
  display-name -> id (champion_index.json). Esse índice resolve automaticamente
  todas as discrepâncias de nome (Wukong->MonkeyKing, Nunu & Willump->Nunu...)
  lendo o campo "name" do champion.json, sem depender de aliases manuais.

- Times: baixa os logos via Leaguepedia (Special:FilePath) a partir do campo
  Image da tabela Teams.

Tudo é idempotente: arquivos já existentes não são rebaixados.
"""

from __future__ import annotations

import json
import time
from typing import Callable, Iterable, Optional

import requests

import config

ProgressFn = Callable[[str], None]

CHAMPION_INDEX_PATH = config.ASSET_CACHE_DIR / "champion_index.json"


def _noop(_: str) -> None:
    pass


# --------------------------------------------------------------------------- #
# Campeões (Data Dragon)
# --------------------------------------------------------------------------- #
def download_all_champion_icons(progress: ProgressFn = _noop) -> dict:
    """
    Baixa todos os ícones de campeão e grava o índice nome->id.
    Retorna um resumo {version, total, baixados, ja_existiam}.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": config.HTTP_USER_AGENT})

    version = session.get(config.DDRAGON_VERSIONS_URL, timeout=config.HTTP_TIMEOUT).json()[0]
    progress(f"Data Dragon versão {version}")

    champ_json = session.get(
        f"{config.DDRAGON_CDN}/{version}/data/{config.DDRAGON_LOCALE}/champion.json",
        timeout=config.HTTP_TIMEOUT,
    ).json()["data"]

    # Índice: tanto o display name ("name") quanto o id apontam para o id/arquivo.
    index: dict[str, str] = {}
    for champ_id, info in champ_json.items():
        index[info["name"].lower()] = champ_id     # "wukong" -> "MonkeyKing"
        index[champ_id.lower()] = champ_id          # "monkeyking" -> "MonkeyKing"
    CHAMPION_INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2),
                                   encoding="utf-8")

    total = len(champ_json)
    downloaded = existed = 0
    for i, (champ_id, info) in enumerate(sorted(champ_json.items()), 1):
        dest = config.CHAMPION_ICON_DIR / f"{champ_id}.png"
        if dest.exists():
            existed += 1
            continue
        img_name = info["image"]["full"]  # ex.: "MonkeyKing.png"
        url = f"{config.DDRAGON_CDN}/{version}/img/champion/{img_name}"
        try:
            resp = session.get(url, timeout=config.HTTP_TIMEOUT)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            downloaded += 1
        except requests.RequestException as e:
            progress(f"  falha em {champ_id}: {e}")
        if i % 25 == 0:
            progress(f"  campeões: {i}/{total}")

    progress(f"Campeões OK: {downloaded} baixados, {existed} já existiam (de {total}).")
    return {"version": version, "total": total, "downloaded": downloaded, "existed": existed}


def load_champion_index() -> dict[str, str]:
    """Carrega o índice nome->id (vazio se ainda não foi baixado)."""
    if CHAMPION_INDEX_PATH.exists():
        try:
            return json.loads(CHAMPION_INDEX_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


# --------------------------------------------------------------------------- #
# Logos de times (Leaguepedia)
# --------------------------------------------------------------------------- #
def download_team_logos(team_names: Iterable[str], progress: ProgressFn = _noop,
                        gap: float = 5.0) -> dict:
    """
    Baixa logos dos times informados via Leaguepedia.

    1 requisição à tabela Teams (em lote) para descobrir o arquivo de imagem,
    depois baixa cada logo por Special:FilePath. Idempotente.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": config.HTTP_USER_AGENT})

    names = sorted({n for n in team_names if n})
    if not names:
        return {"downloaded": 0, "existed": 0}

    # Lote: WHERE Name IN ('a','b',...)
    quoted = ",".join("'" + n.replace("'", "''") + "'" for n in names)
    params = {
        "action": "cargoquery", "format": "json", "tables": "Teams",
        "fields": "Name,Image", "where": f"Teams.Name IN ({quoted})",
        "limit": str(len(names)),
    }
    resp = session.get(config.LEAGUEPEDIA_API, params=params,
                       timeout=config.HTTP_TIMEOUT)
    data = resp.json()
    image_by_team = {}
    for it in data.get("cargoquery", []):
        t = it["title"]
        if t.get("Image"):
            image_by_team[t["Name"]] = t["Image"]

    downloaded = existed = 0
    for name in names:
        dest = config.TEAM_LOGO_DIR / f"{_safe(name)}.png"
        if dest.exists():
            existed += 1
            continue
        image = image_by_team.get(name)
        if not image:
            continue
        url = f"https://lol.fandom.com/wiki/Special:FilePath/{image.replace(' ', '_')}"
        try:
            time.sleep(gap)
            r = session.get(url, timeout=config.HTTP_TIMEOUT)
            r.raise_for_status()
            dest.write_bytes(r.content)
            downloaded += 1
            progress(f"  logo: {name}")
        except requests.RequestException as e:
            progress(f"  falha logo {name}: {e}")

    progress(f"Logos OK: {downloaded} baixados, {existed} já existiam.")
    return {"downloaded": downloaded, "existed": existed}


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name)
