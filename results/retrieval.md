# Retrieval evaluation

Best by MRR: **clause/hybrid+rerank**

## 1. Overall

| config | hit@1 | hit@3 | hit@5 | MRR | recall@5 (all) | avg ms |
|---|---|---|---|---|---|---|
| recursive/dense | 0.750 | 0.889 | 0.889 | 0.830 | 1.000 | 28 |
| clause/dense | 0.806 | 0.917 | 0.944 | 0.868 | 1.000 | 40 |
| recursive/bm25 | 0.778 | 0.889 | 0.944 | 0.847 | 1.000 | 0 |
| clause/bm25 | 0.778 | 0.889 | 0.944 | 0.844 | 1.000 | 0 |
| recursive/hybrid | 0.806 | 0.972 | 0.972 | 0.884 | 1.000 | 29 |
| clause/hybrid | 0.833 | 0.944 | 0.972 | 0.895 | 1.000 | 29 |
| recursive/hybrid+rerank | 0.861 | 0.944 | 1.000 | 0.917 | 1.000 | 493 |
| clause/hybrid+rerank | 0.861 | 1.000 | 1.000 | 0.926 | 1.000 | 384 |
| recursive/hybrid+rerank+hyde | 0.861 | 0.944 | 1.000 | 0.917 | 1.000 | 4833 |
| clause/hybrid+rerank+hyde | 0.861 | 1.000 | 1.000 | 0.926 | 1.000 | 452 |
| recursive/hybrid+rerank+multiquery | 0.861 | 0.944 | 1.000 | 0.917 | 1.000 | 4852 |
| clause/hybrid+rerank+multiquery | 0.861 | 1.000 | 1.000 | 0.926 | 1.000 | 506 |

hit@k and MRR over 'any' questions (n=36); recall@5 over 'all' questions (n=5).

## 2. hit@5 per category

| config | exact_id | paraphrase | detail | exception | cross_reference | near_duplicate | amendment |
|---|---|---|---|---|---|---|---|
| recursive/dense | 0.57 | 0.88 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| clause/dense | 0.71 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| recursive/bm25 | 1.00 | 0.88 | 0.86 | 1.00 | 1.00 | 1.00 | 1.00 |
| clause/bm25 | 1.00 | 0.88 | 0.86 | 1.00 | 1.00 | 1.00 | 1.00 |
| recursive/hybrid | 1.00 | 0.88 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| clause/hybrid | 0.86 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| recursive/hybrid+rerank | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| clause/hybrid+rerank | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| recursive/hybrid+rerank+hyde | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| clause/hybrid+rerank+hyde | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| recursive/hybrid+rerank+multiquery | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| clause/hybrid+rerank+multiquery | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

'all' questions count as a hit only when every expected source is in the top 5.

## 3. Refusal threshold: top scores, out-of-scope vs in-scope

| config | score | out_of_scope (each) | in-scope min | in-scope p10 | in-scope median | separable? |
|---|---|---|---|---|---|---|
| recursive/dense | final | 0.599, 0.609, 0.612 | 0.511 | 0.590 | 0.711 | no |
| recursive/dense | dense cos | 0.599, 0.609, 0.612 | 0.511 | 0.590 | 0.711 | no |
| clause/dense | final | 0.597, 0.622, 0.623 | 0.538 | 0.619 | 0.730 | no |
| clause/dense | dense cos | 0.597, 0.622, 0.623 | 0.538 | 0.619 | 0.730 | no |
| recursive/bm25 | final | 2.562, 3.348, 6.164 | 2.814 | 3.407 | 7.411 | no |
| clause/bm25 | final | 4.216, 3.984, 9.047 | 3.563 | 4.212 | 8.630 | no |
| recursive/hybrid | final | 0.033, 0.033, 0.033 | 0.031 | 0.032 | 0.033 | no |
| recursive/hybrid | dense cos | 0.599, 0.609, 0.612 | 0.511 | 0.590 | 0.711 | no |
| clause/hybrid | final | 0.032, 0.031, 0.033 | 0.031 | 0.032 | 0.033 | no |
| clause/hybrid | dense cos | 0.597, 0.622, 0.623 | 0.538 | 0.619 | 0.730 | no |
| recursive/hybrid+rerank | final | -8.267, -9.619, -0.105 | -8.450 | -4.525 | 4.109 | no |
| recursive/hybrid+rerank | dense cos | 0.599, 0.609, 0.612 | 0.511 | 0.590 | 0.711 | no |
| recursive/hybrid+rerank | rerank | -8.267, -9.619, -0.105 | -8.450 | -4.525 | 4.109 | no |
| clause/hybrid+rerank | final | -7.091, -9.759, 1.602 | -8.815 | -4.399 | 5.177 | no |
| clause/hybrid+rerank | dense cos | 0.597, 0.622, 0.623 | 0.538 | 0.619 | 0.730 | no |
| clause/hybrid+rerank | rerank | -7.091, -9.759, 1.602 | -8.815 | -4.399 | 5.177 | no |
| recursive/hybrid+rerank+hyde | final | -8.267, -9.619, -0.105 | -8.450 | -4.525 | 4.109 | no |
| recursive/hybrid+rerank+hyde | dense cos | 0.655, 0.621, 0.634 | 0.605 | 0.680 | 0.762 | no |
| recursive/hybrid+rerank+hyde | rerank | -8.267, -9.619, -0.105 | -8.450 | -4.525 | 4.109 | no |
| clause/hybrid+rerank+hyde | final | -7.091, -9.759, 1.602 | -8.815 | -4.399 | 5.177 | no |
| clause/hybrid+rerank+hyde | dense cos | 0.671, 0.644, 0.673 | 0.635 | 0.701 | 0.782 | no |
| clause/hybrid+rerank+hyde | rerank | -7.091, -9.759, 1.602 | -8.815 | -4.399 | 5.177 | no |
| recursive/hybrid+rerank+multiquery | final | -8.267, -9.619, -0.105 | -8.450 | -4.525 | 4.109 | no |
| recursive/hybrid+rerank+multiquery | dense cos | 0.599, 0.609, 0.612 | 0.511 | 0.590 | 0.711 | no |
| recursive/hybrid+rerank+multiquery | rerank | -8.267, -9.619, -0.105 | -8.450 | -4.525 | 4.109 | no |
| clause/hybrid+rerank+multiquery | final | -7.091, -9.759, 1.602 | -8.815 | -4.399 | 5.177 | no |
| clause/hybrid+rerank+multiquery | dense cos | 0.597, 0.622, 0.623 | 0.538 | 0.619 | 0.730 | no |
| clause/hybrid+rerank+multiquery | rerank | -7.091, -9.759, 1.602 | -8.815 | -4.399 | 5.177 | no |

## 4. Questions every config failed (no full hit in top 5)

None
