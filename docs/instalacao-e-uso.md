# Instalação e uso

## Requisitos

- Python 3.11 ou mais novo
- As dependências de [`requirements.txt`](../requirements.txt): PySide6 (interface Qt), pandas (estatísticas) e requests (HTTP)

O app foi desenvolvido e testado no Windows.

## Instalando

```bash
git clone https://github.com/eduardohenrique-dev/lol-draft-analyzer.git
cd lol-draft-analyzer

python -m venv .venv
.venv\Scripts\activate          # no Linux e no macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## Primeira execução

O banco de dados nasce vazio. Sem partidas, a aba Draft mostra a mensagem "Nenhuma partida no banco". Há dois caminhos para preenchê-lo.

### Dados de exemplo (fictícios)

```bash
python tools/seed_demo.py
python main.py
```

`tools/seed_demo.py` grava 12 partidas inventadas, com times e jogadores fictícios, nas cinco ligas monitoradas. Se o banco já tiver partidas, o script não grava nada. Para trocar o conteúdo pelos exemplos, use `--limpar`, que apaga as partidas atuais antes de gravar.

### Dados reais (Leaguepedia)

```bash
python main.py --sync
```

Baixa as partidas de 2026 das cinco ligas e abre o app. Atenção: **`--sync` apaga as partidas que já estão no banco** antes de baixar as novas. A Leaguepedia limita bastante as requisições anônimas, então o sync pode levar minutos ou falhar. Veja [fontes de dados](fontes-de-dados.md).

## Opções de linha de comando

| Comando | O que faz |
| --- | --- |
| `python main.py` | abre o app lendo o banco local |
| `python main.py --sync` | baixa as partidas de 2026 da Leaguepedia (uma requisição por liga), baixa os logos dos times e abre o app |
| `python main.py --assets` | baixa os ícones de todos os campeões do Data Dragon antes de abrir |
| `python main.py --online` | deixa o app baixar na hora o ícone de um campeão que esteja faltando |

Ferramentas avulsas, que não abrem a interface:

| Comando | O que faz |
| --- | --- |
| `python tools/seed_demo.py [--limpar]` | grava as partidas fictícias |
| `python tools/sync_data.py [--logos] [--wait N]` | sincroniza 2026 com uma **única** requisição combinando todas as ligas; `--logos` baixa também os logos dos times, e `--wait N` espera N segundos antes, para o limite de requisições esfriar |
| `python tools/sync_assets.py` | baixa os ícones dos campeões |

## Usando o app

### Aba Draft

Escolha uma partida no seletor no topo (o rótulo traz liga, os dois times e a data). O cabeçalho mostra o lado azul, o lado vermelho, o resultado e o patch. Abaixo, cada ação do draft aparece numa linha própria, na ordem em que aconteceu, alinhada ao lado que a fez. Bans têm o ícone dessaturado e riscado. Nos picks aparecem a rota e o jogador, quando a fonte informa.

### Aba Estatísticas

Uma linha por campeão, com presença, picks, bans, Prio Score, vitórias, derrotas e win rate. Clique no cabeçalho de uma coluna para ordenar (a ordenação é numérica). Os filtros de liga, patch e datas só valem depois de **Aplicar filtros**, e o intervalo de datas fica limitado a 2026 em diante.

## Onde ficam os arquivos

Tudo o que o app baixa ou grava fica em `data/`, que o Git ignora:

```
data/
├─ draft_analyzer.sqlite3     banco de dados
└─ assets/
   ├─ champion_index.json     índice nome → id do Data Dragon
   ├─ champions/              ícones dos campeões
   └─ teams/                  logos dos times
```
