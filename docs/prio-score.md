# Prio Score

O Prio Score é uma métrica de 0 a 100 que indica **o quanto um campeão é priorizado no draft**. O código está em [`src/backend/stats_engine.py`](../src/backend/stats_engine.py), e os pesos em [`config.py`](../config.py).

## O problema

Win rate e presença não distinguem um campeão que é **sempre** o primeiro pick de outro que só aparece como a última escolha de contra-pick. O Prio Score mede **quão cedo** um campeão é disputado, ou seja, o quanto os times o tratam como uma peça de alta prioridade.

## A intuição

Quanto mais cedo um campeão é:

- **banido** na fase 1, é sinal de respeito: o time o tira do pool logo de início;
- **escolhido**, é sinal de que ele é tão forte que vale garantir antes que o adversário pegue.

Picks e bans tardios (fase 2) carregam pouco sinal de prioridade: costumam ser ajustes situacionais e contra-picks.

## O cálculo

### Passo 1: peso de cada ação

Cada ação recebe um peso pela posição cronológica dentro do seu tipo (`global_order`, de 1 a 10):

| Posição | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Pick** | 1,00 | 0,90 | 0,80 | 0,70 | 0,60 | 0,50 | 0,40 | 0,30 | 0,20 | 0,10 |
| **Ban** | 0,90 | 0,85 | 0,80 | 0,75 | 0,70 | 0,65 | 0,45 | 0,40 | 0,35 | 0,30 |

Os picks decaem em linha reta, do first pick (1,00) à última escolha (0,10). Os bans da fase 1 (posições 1 a 6) valem quase tanto quanto os melhores picks. Os da fase 2 (posições 7 a 10) valem bem menos.

Um campeão aparece no máximo **uma vez por jogo**: se foi banido, não pode ser escolhido, e cada campeão é escolhido uma vez. Por isso ele contribui com no máximo um peso por jogo.

### Passo 2: soma e normalização

```
prio_bruto(campeão)  = Σ peso(ação)                 (soma sobre todos os jogos do recorte)
PrioScore(campeão)   = 100 × prio_bruto / N_jogos   (N_jogos = total de jogos do recorte)
```

O divisor é o **total de jogos do recorte atual** (liga, patch e datas escolhidos), e não o número de jogos em que o campeão apareceu.

### Por que dividir pelo total de jogos

Dividir pelas aparições mediria só "quando aparece, é cedo?", e perderia a frequência. Um campeão escolhido como first pick uma única vez no split inteiro empataria com um first pick recorrente. Para prioridade competitiva a frequência importa, então ela entra na conta. O resultado combina, num número só, as duas coisas que definem prioridade:

- **frequência**: aparecer em muitos jogos aumenta a soma;
- **precocidade**: aparecer cedo dá mais peso por aparição.

## Lendo a escala

| Valor | Significado |
| --- | --- |
| 100 | teoricamente, first pick em 100% dos jogos do recorte |
| cerca de 85 | praticamente banido na fase 1 em todo jogo |
| cerca de 25 | presença mediana ou aparições tardias |
| perto de 0 | quase nunca disputado, ou só em picks finais esporádicos |

## Exemplo

Num recorte de 10 jogos, um campeão foi:

- first pick (posição 1) em 2 jogos: 2 × 1,00 = 2,00
- terceiro ban (posição 3) em 4 jogos: 4 × 0,80 = 3,20
- não apareceu nos outros 4 jogos: 0

```
prio_bruto = 2,00 + 3,20 = 5,20
PrioScore  = 100 × 5,20 / 10 = 52,0
```

## Outras colunas da tabela

| Coluna | Cálculo |
| --- | --- |
| Presença % | (picks + bans) ÷ total de jogos × 100 |
| Picks e Bans | quantas vezes o campeão foi escolhido e banido |
| Vitórias e Derrotas | só contam quando o campeão foi **escolhido** |
| Win Rate % | vitórias ÷ (vitórias + derrotas) × 100, ou 0 se nunca foi escolhido |

Os valores são arredondados em uma casa decimal, e a tabela sai ordenada por presença, do maior para o menor.

## Conferência

Os testes recalculam o Prio Score de todos os campeões à mão, direto das ações dos jogos, e comparam com o resultado do motor (veja [`tests/test_stats_engine.py`](../tests/test_stats_engine.py)).
