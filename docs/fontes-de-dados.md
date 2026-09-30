# Fontes de dados

## Visão geral

| Fonte | Para quê | Onde no código |
| --- | --- | --- |
| Leaguepedia (Cargo API) | partidas, picks, bans, resultado, patch e logos dos times | `src/backend/leaguepedia_client.py`, `src/backend/asset_sync.py` |
| Riot Data Dragon | ícones dos campeões | `src/backend/datadragon_client.py`, `src/backend/asset_sync.py` |
| Dados de exemplo | ver a interface sem rede | `src/mock/mock_data.py`, `tools/seed_demo.py` |

## Leaguepedia

A partida vem da tabela `PicksAndBansS7` da Cargo API (`lol.fandom.com/api.php`). O mapeamento é: `Team1` é o lado azul, `Team2` é o lado vermelho, e cada pick e ban tem o seu campo (`Team1Ban1`, `Team2Pick3`, e assim por diante), assim como as rotas (`Team1Role1`…).

### Como o cliente se comporta

A API anônima da Leaguepedia limita as requisições de forma agressiva, e consultas amplas, sem filtro seletivo, fazem o servidor lançar erro. Por isso o cliente:

- usa **sempre** um filtro seletivo: prefixo do `OverviewPage` mais data a partir do corte;
- espera **pelo menos 6 segundos** entre requisições;
- quando recebe erro de limite de requisições ou de exceção do servidor, espera e tenta de novo, com espera crescente (começa em 30 segundos, sobe até 180 e faz até 6 tentativas).

### As ligas e os prefixos

Cada liga em `config.LEAGUES` tem uma lista de prefixos possíveis para o início do `OverviewPage`. Em 2026 as Américas foram unificadas na LTA, então LCS virou "LTA North" e CBLOL virou "LTA South". Os nomes antigos ficam como alternativa, caso ainda existam páginas antigas.

### Dois jeitos de sincronizar

| Comando | Requisições | Observação |
| --- | --- | --- |
| `python main.py --sync` | uma por liga | limpa as partidas do banco antes, baixa também os logos e abre o app |
| `python tools/sync_data.py` | **uma só** para todas as ligas | o cliente classifica cada jogo na liga pelo `OverviewPage`; é o caminho que menos pressiona o limite |

### Limites conhecidos

- O sync pode demorar minutos e, sob limite persistente, falha.
- O cliente atual não traz o **nick dos jogadores**, então em partidas reais os picks mostram só a rota.
- Um jogo com dados incompletos ou ilegíveis é descartado em silêncio.

## Riot Data Dragon

O cliente descobre a versão mais recente em `versions.json`, baixa o `champion.json` (em `en_US`) e monta um **índice de nomes**: tanto o nome de exibição quanto o id apontam para o id do arquivo. Isso resolve as diferenças de nome, como Wukong → `MonkeyKing` e Nunu & Willump → `Nunu`, sem depender só de apelidos escritos à mão.

Os ícones são baixados uma vez e guardados em `data/assets/champions/`. Arquivos que já existem não são baixados de novo.

Sem o ícone, o app desenha um marcador determinístico: uma cor derivada do nome e as iniciais do campeão.

## Dados de exemplo

`src/mock/mock_data.py` gera 12 partidas **fictícias**, de forma determinística (semente fixa):

- 10 times inventados, com 5 jogadores inventados cada, distribuídos nas cinco ligas;
- os campeões são reais, sorteados por rota com preferência pelos mais disputados, e os banimentos saem do grupo dos mais cobiçados;
- cada draft segue a sequência oficial, com 10 bans e 10 picks, sem campeão repetido.

Nenhum time, jogador ou resultado ali corresponde a algo real.

## Próximo passo: API da GRID

A fonte deve mudar para a **API da GRID**, que entrega dados oficiais de partidas e não tem o limite agressivo da Leaguepedia anônima. Como o restante do app só conhece os modelos (`GameDraft`, `DraftAction`, `TeamInfo`) e o banco, a troca fica restrita a um novo cliente em `src/backend/`, sem mexer na interface. Isso **ainda não foi feito**.
