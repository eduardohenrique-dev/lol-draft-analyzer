# Desenvolvimento

## Preparando o ambiente

```bash
python -m venv .venv
.venv\Scripts\activate          # no Linux e no macOS: source .venv/bin/activate
pip install -r requirements.txt
python tools/seed_demo.py       # dados de exemplo para trabalhar na interface
python main.py
```

## Testes

```bash
python -m unittest
```

Os testes não abrem a interface nem usam a rede.

| Arquivo | O que cobre |
| --- | --- |
| `tests/test_draft.py` | a sequência do draft (20 ações, 5 bans e 5 picks por lado, slots sem repetição), os pesos do Prio Score (10 posições, picks decrescentes) e a consistência dos dados de exemplo (20 campeões distintos por draft, ligas que existem na configuração, ordem igual à sequência oficial) |
| `tests/test_stats_engine.py` | o motor de estatísticas sobre um banco temporário: totais de picks e bans, o Prio Score recalculado à mão para todos os campeões, presença, filtro por liga, win rate e banco vazio |

O banco usado nos testes é um arquivo temporário: o seu `data/` não é tocado.

## Tarefas comuns

### Acrescentar uma liga

1. Coloque um item novo em `LEAGUES`, em [`config.py`](../config.py), com `key`, `label` e `prefixes` (os inícios possíveis do `OverviewPage` na Leaguepedia).
2. Pronto: o banco passa a incluí-la em `leagues` na próxima abertura, e a tela de estatísticas a oferece no filtro.

A chave precisa existir em `config.LEAGUES` antes de gravar jogos dela, por causa das chaves estrangeiras.

### Mudar os pesos do Prio Score

Edite `PICK_PRIORITY_WEIGHT` e `BAN_PRIORITY_WEIGHT` em `config.py`. Cada um precisa cobrir as posições de 1 a 10. Os testes recalculam o score a partir desses mesmos pesos, então continuam passando. Veja a intuição por trás dos valores em [Prio Score](prio-score.md).

### Trocar a fonte de dados

O ponto de encaixe é o back-end: um cliente novo, em `src/backend/`, que devolva `list[GameDraft]`, e um trecho no `main.py` ou numa ferramenta em `tools/` que chame `db.save_games(...)`. A interface e o motor de estatísticas não mudam.

### Mexer no visual

As cores estão em `src/ui/theme.py`, e o estilo geral (QSS) é montado pela função `stylesheet()` do mesmo arquivo. O lado azul, o lado vermelho e o dourado do vencedor são constantes.

## Convenções

- Comentários e mensagens ao usuário em português.
- Tipos nos parâmetros e nos retornos, com `from __future__ import annotations`.
- A interface só lê do banco e do gerenciador de ícones, nunca faz requisição de rede.
