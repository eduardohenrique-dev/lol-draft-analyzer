# Banco de dados

O banco é um arquivo SQLite em `data/draft_analyzer.sqlite3`, criado na primeira execução. O código está em [`src/backend/database.py`](../src/backend/database.py).

## Esquema

```
leagues ◄──── games ────► teams (azul)
                │   └────► teams (vermelho)
                │
                └──── draft_actions   (20 linhas por jogo)
```

### `leagues`

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `key` | texto, chave primária | identificador interno (`LEC`, `LCK`, `LPL`, `LTA_N`, `LTA_S`) |
| `label` | texto | nome exibido na interface |

É preenchida com as ligas de `config.LEAGUES` toda vez que o banco é aberto (`INSERT OR IGNORE`).

### `teams`

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `name` | texto, chave primária | nome do time |
| `short` | texto | sigla |
| `logo_path` | texto | caminho local do logo em cache |

### `games`

Uma linha por jogo.

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `game_id` | texto, chave primária | identificador da partida |
| `league` | texto | chave da liga |
| `patch` | texto | versão do jogo, por exemplo `16.3` |
| `match_date` | texto | data em ISO 8601 (`AAAA-MM-DD`) |
| `blue_team` | texto | time do lado azul |
| `red_team` | texto | time do lado vermelho |
| `winner` | texto | `blue` ou `red` |

### `draft_actions`

Uma linha por **ação** do draft, 20 por jogo. É a tabela que alimenta a tela de draft e o motor estatístico.

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id` | inteiro, autoincremento | |
| `game_id` | texto | jogo a que a ação pertence (apagada junto com o jogo) |
| `phase` | texto | `ban1`, `pick1`, `ban2` ou `pick2` |
| `action_type` | texto | `ban` ou `pick` |
| `side` | texto | `blue` ou `red` |
| `slot` | inteiro | posição do time naquele tipo de ação, de 1 a 5 |
| `global_order` | inteiro | ordem cronológica dentro do tipo, de 1 a 10 |
| `champion` | texto | nome do campeão |
| `role` | texto | rota (só nos picks) |
| `player` | texto | jogador (só nos picks, quando a fonte informa) |

### Índices

| Índice | Colunas | Para quê |
| --- | --- | --- |
| `idx_games_filters` | `games(league, patch, match_date)` | acelerar os filtros do painel de estatísticas |
| `idx_actions_game` | `draft_actions(game_id)` | juntar ações e jogos |
| `idx_actions_champ` | `draft_actions(champion)` | agregar por campeão |

## Comportamentos importantes

- **Chaves estrangeiras ligadas.** Cada conexão executa `PRAGMA foreign_keys = ON`, então um jogo só é gravado se a liga existir em `leagues`. Ao acrescentar uma liga, coloque-a em `config.LEAGUES`.
- **Gravação idempotente.** Gravar um jogo que já existe atualiza os metadados e **reescreve** as ações dele. Rodar o sync duas vezes não duplica nada.
- **Times em `upsert`.** O logo já baixado é preservado (`COALESCE`) quando uma nova gravação chega sem logo.
- **Corte de data.** O banco em si aceita qualquer data. O recorte de 2026 em diante (`config.DATA_SINCE`) vem da sincronização, que só busca a partir dessa data, e dos seletores de data da tela de estatísticas.
