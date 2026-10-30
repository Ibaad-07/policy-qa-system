# Retrieval evaluation

Best by MRR: **clause/hybrid+rerank**

## 1. Overall

| config | hit@1 | hit@3 | hit@5 | MRR | recall@5 (all) | avg ms |
|---|---|---|---|---|---|---|
| recursive/hybrid+rerank | 0.889 | 0.944 | 0.972 | 0.926 | 1.000 | 4440 |
| clause/hybrid+rerank | 0.944 | 0.972 | 0.972 | 0.956 | 1.000 | 2114 |

hit@k and MRR over 'any' questions (n=36); recall@5 over 'all' questions (n=5).

## 2. hit@5 per category

| config | exact_id | paraphrase | detail | exception | cross_reference | near_duplicate | amendment |
|---|---|---|---|---|---|---|---|
| recursive/hybrid+rerank | 0.86 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| clause/hybrid+rerank | 0.86 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

'all' questions count as a hit only when every expected source is in the top 5.

## 3. Refusal threshold: top scores, out-of-scope vs in-scope

| config | score | out_of_scope (each) | in-scope min | in-scope p10 | in-scope median | separable? |
|---|---|---|---|---|---|---|
| recursive/hybrid+rerank | final | 0.019, 0.041, 0.017 | 0.002 | 0.063 | 0.896 | no |
| recursive/hybrid+rerank | dense cos | 0.599, 0.609, 0.612 | 0.511 | 0.590 | 0.711 | no |
| recursive/hybrid+rerank | rerank | 0.019, 0.041, 0.017 | 0.002 | 0.063 | 0.896 | no |
| clause/hybrid+rerank | final | 0.008, 0.029, 0.008 | 0.002 | 0.017 | 0.914 | no |
| clause/hybrid+rerank | dense cos | 0.597, 0.622, 0.623 | 0.538 | 0.619 | 0.730 | no |
| clause/hybrid+rerank | rerank | 0.008, 0.029, 0.008 | 0.002 | 0.017 | 0.914 | no |

## 4. Questions every config failed (no full hit in top 5)

- q04 [exact_id] What is extension 4357 used for?
