# Arquitetura

O app segue um fluxo em uma direção só:

```
   rede                  disco                   tela
 ─────────           ─────────────           ─────────────
 Leaguepedia ─┐
              ├─► sincronização ─► SQLite ─► interface
 Data Dragon ─┘        (cache)     (cache)    (lê só do banco)
```

A interface **nunca depende de rede** para abrir. A sincronização é uma ação à parte, e o resultado fica em cache.

## Estrutura

```
lol-draft-analyzer/
├─ config.py                 regras do domínio e configuração
├─ main.py                   ponto de entrada e flags
├─ requirements.txt
├─ src/
│  ├─ models/draft.py        GameDraft, DraftAction, TeamInfo
│  ├─ backend/
│  │  ├─ database.py         acesso ao SQLite
│  │  ├─ leaguepedia_client.py   Cargo API, com espera e nova tentativa
│  │  ├─ datadragon_client.py    versão e URLs de ícones; normalização de nomes
│  │  ├─ asset_sync.py       baixa ícones de campeões e logos de times
│  │  ├─ asset_manager.py    entrega pixmaps à interface, com cache
│  │  └─ stats_engine.py     agregação por campeão e Prio Score
│  ├─ ui/
│  │  ├─ main_window.py      abas Draft e Estatísticas, seletor de partida
│  │  ├─ draft_view.py       tela de picks e bans
│  │  ├─ stats_view.py       tabela ordenável e filtros
│  │  ├─ theme.py            paleta e QSS
│  │  └─ widgets/champion_slot.py   um ban ou um pick
│  └─ mock/mock_data.py      partidas fictícias
├─ tools/                    sincronização e dados de exemplo
└─ tests/
```

## Camadas

### Modelos (`src/models/draft.py`)

Três dataclasses são a "moeda comum" entre o back-end e a interface:

- `TeamInfo`: nome, sigla e caminho do logo em cache.
- `DraftAction`: uma ação do draft, com fase, tipo (`ban` ou `pick`), lado, posição no lado (`slot`, de 1 a 5), ordem cronológica dentro do tipo (`global_order`, de 1 a 10), campeão, e, nos picks, rota e jogador.
- `GameDraft`: os metadados da partida e a lista cronológica de ações.

Os modelos não conhecem as APIs nem a interface, o que facilita trocar a fonte de dados.

### Configuração (`config.py`)

Concentra o conhecimento de regras do draft competitivo:

- `DRAFT_SEQUENCE`: as 20 ações na ordem oficial (bans da fase 1, picks da fase 1, bans da fase 2, picks da fase 2);
- `LEAGUES`: as ligas monitoradas, com o prefixo da página da Leaguepedia;
- `PICK_PRIORITY_WEIGHT` e `BAN_PRIORITY_WEIGHT`: os pesos do [Prio Score](prio-score.md);
- caminhos, URLs do Data Dragon e da Leaguepedia, e a data de corte (`DATA_SINCE`, 1º de janeiro de 2026).

### Back-end (`src/backend/`)

- **`database.py`** é uma camada fina sobre `sqlite3` com as operações do domínio: gravar jogos, listar, carregar um draft e buscar as ações para as estatísticas. Cada conexão liga `PRAGMA foreign_keys`.
- **`leaguepedia_client.py`** consulta a tabela `PicksAndBansS7` da Cargo API. Usa sempre um filtro seletivo (prefixo da página e data), espera no mínimo 6 segundos entre requisições e, diante de limite de requisições, refaz a chamada com espera crescente.
- **`datadragon_client.py`** e **`asset_sync.py`** descobrem a versão mais recente do Data Dragon, baixam os ícones dos campeões e montam um índice de nomes, que resolve casos como Wukong → `MonkeyKing`. Os logos dos times vêm da Leaguepedia.
- **`asset_manager.py`** entrega `QPixmap` para a interface, com cache em memória e em disco. Sem ícone, desenha um marcador com as iniciais. Para bans, dessatura o ícone e risca uma diagonal.
- **`stats_engine.py`** agrega as ações por campeão com pandas e calcula o Prio Score.

### Interface (`src/ui/`)

Qt (PySide6). `MainWindow` monta as duas abas e o seletor de partida. `DraftView` desenha o draft em leitura vertical. `StatsView` mostra a tabela, com um modelo (`ChampionStatsModel`) sobre o DataFrame e um `QSortFilterProxyModel` para a ordenação numérica. `ChampionSlot` é o widget de uma ação.

## Decisões de projeto

- **Cache em SQLite.** A Leaguepedia limita o acesso e responde devagar. Ler tudo do banco local deixa o app instantâneo e utilizável sem rede.
- **Uma linha por ação de draft.** A tabela `draft_actions` alimenta tanto a tela de draft quanto o motor estatístico, então há uma única fonte.
- **Ordenação numérica.** O modelo entrega ao Qt um valor nativo do Python no papel de ordenação. Tipos do numpy não são comparáveis pelo Qt e deixariam as colunas numéricas sem ordem.
- **Modelos independentes.** Trocar a Leaguepedia por outra fonte mexe só no back-end.
