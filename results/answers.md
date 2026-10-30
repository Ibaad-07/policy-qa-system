# Answer evaluation

Config: **clause/hybrid+rerank**, LLM: **llama3.2:3b**

## Pass rate per category

| category | n | pass rate | retrieval misses | generation errors |
|---|---|---|---|---|
| exact_id | 7 | 0.86 | 0 | 1 |
| paraphrase | 8 | 1.00 | 0 | 0 |
| detail | 7 | 0.86 | 0 | 1 |
| exception | 6 | 0.83 | 0 | 1 |
| cross_reference | 4 | 0.50 | 0 | 2 |
| near_duplicate | 5 | 1.00 | 0 | 0 |
| amendment | 4 | 1.00 | 0 | 0 |
| out_of_scope | 3 | 0.67 | 0 | 1 |
| ALL | 44 | 0.86 | 0 | 6 |

## Citations

Citation recall (share of expected clauses cited): 0.91  
Citations not present in the context (invented): 3

## Failures

- **q05** [exact_id] *generation error* (sources in context 1/1): missing ['exit clearance']  
  Q: What is Form HR-15?  
  A: Form HR-15 is a document used by employees to complete before the final settlement is processed, signed by IT, Finance, and their Line Manager. (KA-POL-01, clause 6.5)
- **q16** [detail] *generation error* (sources in context 1/1): missing ['18,000']  
  Q: What is the maximum hotel rate per night in Lahore?  
  A: The maximum hotel rate per night in Lahore is PKR 12,000 (KA-POL-05, cl. 4.1).
- **q23** [exception] *generation error* (sources in context 1/1): missing ['31 December']  
  Q: Can I carry forward my unused annual leave?  
  A: Up to ten (10) days of unused annual leave may be carried forward into the next leave year, (KA-POL-02, clause 3.4).
- **q30** [cross_reference] *generation error* (sources in context 1/1): cited [('KA-POL-03', '6.4')], expected one of [('KA-POL-01', '6.4')]  
  Q: If I am dismissed for gross misconduct, am I entitled to a notice period?  
  A: No, the Company may dismiss an employee without notice (summary dismissal) for gross misconduct, as defined in Section 5.2 of the Code of Conduct and Disciplinary Procedure (KA-POL-03, clause 6.4).
- **q32** [cross_reference] *generation error* (sources in context 2/2): missing ['2']  
  Q: I worked on a public holiday. What do I get?  
  A: You receive one compensatory day off, to be taken within thirty (30) days, (KA-POL-02, clause 10.2). Non-managerial employees may choose overtime pay under clause 4.4 of the Employment Policy (KA-POL-01, clause 4.4).
- **q44** [out_of_scope] *generation error* (sources in context 0/0): did not refuse  
  Q: Who is the CEO of Kestrel Analytics?  
  A: The CEO is the person to whom appeals are made if the Head of HR was involved in the original decision, (KA-POL-03, clause 7.1). The CEO is also the person required to approve international travel and unpaid leave of more than ten days, (KA-POL-05, clause 2.2 and KA-POL-02, clause 9.1). The CEO's identity is not specified in the provided policy documents, (no citation).

## LLM-as-judge (3B judge: unreliable, see README)

- q01: judge **FAITHFUL**, deterministic PASS (agrees)
- q08: judge **UNFAITHFUL**, deterministic PASS (DISAGREES)
- q16: judge **FAITHFUL**, deterministic FAIL (DISAGREES)
- q23: judge **UNFAITHFUL**, deterministic FAIL (agrees)
- q29: judge **UNFAITHFUL**, deterministic PASS (DISAGREES)
- q33: judge **UNFAITHFUL**, deterministic PASS (DISAGREES)
- q38: judge **FAITHFUL**, deterministic PASS (agrees)
- q42: judge **FAITHFUL**, deterministic PASS (agrees)
- q02: judge **FAITHFUL**, deterministic PASS (agrees)
- q09: judge **FAITHFUL**, deterministic PASS (agrees)
