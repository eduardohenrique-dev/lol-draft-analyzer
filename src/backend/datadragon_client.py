"""
Cliente do Riot Data Dragon — descoberta de versão e URLs de ícones de campeão.

Data Dragon é o CDN público de assets do LoL. Fluxo:
    1. Descobrir a versão mais recente (versions.json).
    2. Baixar champion.json (mapeia nome -> arquivo de imagem).
    3. Montar a URL do ícone de cada campeão.

A normalização de nomes é necessária porque o "display name" da Leaguepedia nem
sempre é o "id" do Data Dragon (ex.: Wukong -> MonkeyKing, Nunu & Willump ->
Nunu, Renata Glasc -> Renata).
"""

from __future__ import annotations

from typing import Optional

import requests

import config

# Apelidos display-name (Leaguepedia/transmissão) -> id do Data Dragon.
NAME_ALIASES = {
    "Wukong": "MonkeyKing",
    "Nunu & Willump": "Nunu",
    "Nunu": "Nunu",
    "Renata Glasc": "Renata",
    "Renata": "Renata",
    "Cho'Gath": "Chogath",
    "Kai'Sa": "Kaisa",
    "Kha'Zix": "Khazix",
    "Kog'Maw": "KogMaw",
    "Vel'Koz": "Velkoz",
    "Rek'Sai": "RekSai",
    "Bel'Veth": "Belveth",
    "K'Sante": "KSante",
    "LeBlanc": "Leblanc",
    "Dr. Mundo": "DrMundo",
    "Tahm Kench": "TahmKench",
    "Twisted Fate": "TwistedFate",
    "Master Yi": "MasterYi",
    "Miss Fortune": "MissFortune",
    "Jarvan IV": "JarvanIV",
    "Lee Sin": "LeeSin",
    "Aurelion Sol": "AurelionSol",
    "Xin Zhao": "XinZhao",
}


def normalize_champion_id(display_name: str) -> str:
    """Converte um nome de exibição no `id` usado pelos arquivos do Data Dragon."""
    if display_name in NAME_ALIASES:
        return NAME_ALIASES[display_name]
    # Regra geral: remove caracteres não-alfanuméricos e capitaliza a 1ª letra.
    cleaned = "".join(ch for ch in display_name if ch.isalnum())
    return cleaned[:1].upper() + cleaned[1:] if cleaned else display_name


class DataDragonClient:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": config.HTTP_USER_AGENT})
        self._version: Optional[str] = None

    def latest_version(self) -> str:
        if self._version is None:
            resp = self.session.get(config.DDRAGON_VERSIONS_URL, timeout=config.HTTP_TIMEOUT)
            resp.raise_for_status()
            self._version = resp.json()[0]
        return self._version

    def champion_icon_url(self, display_name: str, version: Optional[str] = None) -> str:
        version = version or self.latest_version()
        champ_id = normalize_champion_id(display_name)
        return f"{config.DDRAGON_CDN}/{version}/img/champion/{champ_id}.png"

    def download_icon(self, display_name: str) -> Optional[bytes]:
        """Baixa os bytes do ícone de um campeão (ou None se falhar)."""
        try:
            resp = self.session.get(
                self.champion_icon_url(display_name), timeout=config.HTTP_TIMEOUT
            )
            resp.raise_for_status()
            return resp.content
        except requests.RequestException:
            return None
