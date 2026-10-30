# Answer evaluation

Config: **clause/hybrid+rerank**, LLM: **llama3.2:3b**

## Pass rate per category

| category | n | pass rate | retrieval misses | generation errors |
|---|---|---|---|---|
| amendment | 4 | 1.00 | 0 | 0 |
| out_of_scope | 3 | 0.67 | 0 | 1 |
| ALL | 7 | 0.86 | 0 | 1 |

## Citations

Citation recall (share of expected clauses cited): 0.62  
Citations not present in the context (invented): 0

## Failures

- **q44** [out_of_scope] *generation error* (sources in context 0/0): did not refuse  
  Q: Who is the CEO of Kestrel Analytics?  
  A: The CEO is the person to whom appeals are made if the Head of HR was involved in the original decision, (KA-POL-03, clause 7.1). The CEO is also the person required to approve international travel and unpaid leave of more than ten days, (KA-POL-05, clause 2.2 and KA-POL-02, clause 9.1). The CEO's identity is not specified in the provided policy documents, (no citation).
