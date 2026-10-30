# Level 3 answer key

Six fictional policy documents for **Kestrel Analytics (Pvt) Ltd** (a made-up company) and 44 test questions.
The same data is in `eval_set.json`, which your evaluation scripts read.

## Documents

| File | ID | Title | Pages |
|---|---|---|---|
| employment_policy.pdf | KA-POL-01 | Employment Policy | 2 |
| leave_policy.pdf | KA-POL-02 | Leave Policy | 2 |
| code_of_conduct.pdf | KA-POL-03 | Code of Conduct and Disciplinary Procedure | 2 |
| it_security_policy.pdf | KA-POL-04 | IT and Information Security Policy | 2 |
| travel_expense_policy.pdf | KA-POL-05 | Travel and Expense Reimbursement Policy | 2 |
| amendment_2026_01.pdf | KA-AMD-2026-01 | Policy Amendment Notice No. 1 of 2026 | 1 |

## eval_set.json fields

- `expected_sources`: list of `{file, doc_id, clause, page, snippet}`. `snippet` is the first 8 words of the clause; a retrieved chunk counts as a match if it is from the same file and contains the snippet (after lowercasing and collapsing whitespace).
- `source_match`: `any` = one expected source is enough; `all` = every expected source is needed (use recall); `none` = out of scope.
- `must_include`: facts the answer must contain. `a|b` means either is fine. Numbers should match as whole numbers, ignoring thousands commas.
- `must_not_include`: text that signals a wrong answer.
- `should_refuse`: the answer should say the information isn't in the documents.

## exact_id (7)

The question contains an identifier (form code, section number, extension). Keyword search (BM25) usually wins; dense search often misses.

| ID | Question | Correct answer | Source |
|---|---|---|---|
| q01 | What is Form HR-04 used for? | It is the Probation Review Form, used to record an extension of probation (once, by up to 3 months, with HR approval). | KA-POL-01 cl. 3.2 (p. 1) |
| q02 | What is Form EXP-07? | The Expense Claim form. Claims are due within 30 days, with original receipts for any item above PKR 2,000. | KA-POL-05 cl. 7.1 (p. 2) |
| q03 | What does Section 5.2 of KA-POL-03 cover? | Gross misconduct: theft or fraud, falsifying records or expense claims, sharing credentials or bypassing security, disclosing client data, violence, harassment, alcohol or drugs at work. | KA-POL-03 cl. 5.2 (p. 1) |
| q04 | What is extension 4357 used for? | It is the IT helpdesk extension, used for example to report a lost or stolen device within 2 hours. | KA-POL-04 cl. 4.3 (p. 1) |
| q05 | What is Form HR-15? | The Exit Clearance form, signed by IT, Finance and the Line Manager before the final settlement is processed. | KA-POL-01 cl. 6.5 (p. 2) |
| q06 | What is Form COC-02 used for? | The Conflict of Interest Declaration (within 15 days); it is also used to declare gifts above PKR 5,000 within 7 days. | KA-POL-03 cl. 2.1 (p. 1); KA-POL-03 cl. 2.3 (p. 1) |
| q07 | Which form do I need to get USB access on my laptop? | Form IT-SEC-2 (Removable Media Exception), approved by the Information Security Officer, valid for at most 30 days. | KA-POL-04 cl. 4.2 (p. 1) |

## paraphrase (8)

The question uses everyday words that don't appear in the policy (sacked, new fathers, staying late). Dense search usually wins; BM25 often misses.

| ID | Question | Correct answer | Source |
|---|---|---|---|
| q08 | Can I get sacked for giving my password to a coworker? | Yes. Sharing login credentials is gross misconduct, which can lead to summary dismissal. | KA-POL-04 cl. 3.2 (p. 1); KA-POL-03 cl. 5.2 (p. 1) |
| q09 | How much time off do new fathers get? | Paternity leave of 10 working days on full pay, taken within 3 months of the birth. | KA-POL-02 cl. 6.2 (p. 2) |
| q10 | I lost my work laptop at the airport. What should I do? | Report it to the IT helpdesk (ext. 4357) within 2 hours and submit Form IT-SEC-5 within 24 hours. | KA-POL-04 cl. 4.3 (p. 1) |
| q11 | Do I get paid extra for staying late at work? | Non-managerial staff get overtime at 1.5x the hourly basic rate beyond 45 hours a week, if approved in advance. | KA-POL-01 cl. 4.4 (p. 2) |
| q12 | A close relative of mine passed away. How many days off can I take? | 3 days of paid bereavement leave for an immediate family member; 1 day for a grandparent. | KA-POL-02 cl. 7.1 (p. 2) |
| q13 | What happens if I keep coming in late? | Arriving late more than 3 times in a calendar month is minor misconduct, handled through the disciplinary procedure (starting with a verbal warning). | KA-POL-03 cl. 5.1 (p. 1) |
| q14 | Can I keep client files on my personal phone? | No. Client data must never be stored on personal devices; personal phones may only be used for email and chat through the approved app. | KA-POL-04 cl. 4.1 (p. 1) |
| q15 | Can I do my work from a cafe using their Wi-Fi? | Only while connected to the Company VPN. | KA-POL-04 cl. 6.2 (p. 2) |

## detail (7)

Specific numbers and facts. Tests whether the right clause makes it into the top results.

| ID | Question | Correct answer | Source |
|---|---|---|---|
| q16 | What is the maximum hotel rate per night in Lahore? | PKR 18,000 per night. | KA-POL-05 cl. 4.1 (p. 1) |
| q17 | How many sick days do employees get per year? | 10 days on full pay (a medical certificate is needed for more than 2 consecutive days). | KA-POL-02 cl. 4.1 (p. 1) |
| q18 | What is the minimum password length? | 14 characters; passwords must be changed every 90 days. | KA-POL-04 cl. 3.1 (p. 1) |
| q19 | How many failed login attempts lock an account? | 5 failed attempts. Unlock via an IT helpdesk ticket. | KA-POL-04 cl. 3.4 (p. 1) |
| q20 | How long does a written warning stay valid? | 12 months. | KA-POL-03 cl. 6.2 (p. 2) |
| q21 | What is the hotel limit per night in London? | USD 220 per night (London is a high-cost city). | KA-POL-05 cl. 4.2 (p. 1) |
| q22 | How long is maternity leave? | 16 weeks on full pay, for employees with at least 6 months of continuous service. | KA-POL-02 cl. 6.1 (p. 2) |

## exception (6)

The answer depends on a condition or exception inside the clause. Tests whether the model reads the whole clause, not just the first sentence.

| ID | Question | Correct answer | Source |
|---|---|---|---|
| q23 | Can I carry forward my unused annual leave? | Up to 10 days; the rest lapses on 30 June. Exception: days refused in writing for business needs can be carried in full but must be used by 31 December. | KA-POL-02 cl. 3.4 (p. 1) |
| q24 | Can I take annual leave while on probation? | No. With Line Manager approval you may take up to 2 days of unpaid leave. | KA-POL-02 cl. 3.2 (p. 1) |
| q25 | Can I fly business class on an international trip? | Only on flights longer than 8 hours, and only at Grade 7 or above; otherwise economy. | KA-POL-05 cl. 3.1 (p. 1) |
| q26 | Will the company reimburse a parking fine from a business trip? | No. Traffic and parking fines are not reimbursed. | KA-POL-05 cl. 8.1 (p. 2) |
| q27 | Can unused sick leave be paid out? | No. Unused sick leave cannot be carried forward or encashed. | KA-POL-02 cl. 4.3 (p. 1) |
| q28 | Can I combine casual leave with annual leave? | No. Casual leave cannot be combined with annual leave and is limited to 2 consecutive days. | KA-POL-02 cl. 5.2 (p. 1) |

## cross_reference (4)

The answer needs more than one clause, sometimes from different documents. Source match is 'all' for multi-clause questions.

| ID | Question | Correct answer | Source |
|---|---|---|---|
| q29 | What happens if someone submits a fake expense claim, and how long do they have to respond to the show-cause notice? | It is gross misconduct and can lead to dismissal after an inquiry; the employee has 5 working days to respond to the show-cause notice. | KA-POL-05 cl. 9.1 (p. 2); KA-POL-03 cl. 6.6 (p. 2) **(all)** |
| q30 | If I am dismissed for gross misconduct, am I entitled to a notice period? | No. The Company may dismiss without notice (summary dismissal) for gross misconduct. | KA-POL-01 cl. 6.4 (p. 2) |
| q31 | If the Head of HR was involved in my disciplinary decision, who do I appeal to and by when? | The CEO, within 10 working days of receiving the decision. The appeal decision comes within 15 working days and is final. | KA-POL-03 cl. 7.1 (p. 2) |
| q32 | I worked on a public holiday. What do I get? | A compensatory day off within 30 days; non-managerial staff may instead choose overtime at 2x the hourly basic rate. | KA-POL-02 cl. 10.2 (p. 2); KA-POL-01 cl. 4.4 (p. 2) **(all)** |

## near_duplicate (5)

Several clauses look alike but have different values (7, 15 or 30 days' notice; 10 days carried forward vs 15 days encashed). Reranking helps here.

| ID | Question | Correct answer | Source |
|---|---|---|---|
| q33 | If I resign after my probation, how much notice do I need to give? | 30 days' written notice. | KA-POL-01 cl. 6.1 (p. 2) |
| q34 | What is the notice period during probation? | 7 days' written notice, from either side. | KA-POL-01 cl. 3.4 (p. 1) |
| q35 | What is the notice period for contract employees? | 15 days, unless the contract states a different period. | KA-POL-01 cl. 6.2 (p. 2) |
| q36 | How many unused annual leave days are paid out when I leave the company? | Up to 15 days, paid in the final settlement. | KA-POL-01 cl. 6.6 (p. 2) |
| q37 | How far in advance must I request international travel? | At least 15 working days before departure, with CEO approval. | KA-POL-05 cl. 2.2 (p. 1) |

## amendment (4)

The amendment notice changed a value. Both the original clause and the amendment must be retrieved, and the answer must give the current value.

| ID | Question | Correct answer | Source |
|---|---|---|---|
| q38 | What is the daily allowance for domestic travel? | PKR 4,500 per day from 1 September 2026 (previously PKR 3,500). | KA-POL-05 cl. 5.1 (p. 1); KA-AMD-2026-01 cl. 1.1 (p. 1) **(all)** |
| q39 | What is the mileage rate for using my own car? | PKR 55 per kilometre from 1 September 2026 (previously PKR 45). | KA-POL-05 cl. 6.1 (p. 1); KA-AMD-2026-01 cl. 1.2 (p. 1) **(all)** |
| q40 | How many days per week can I work from home? | Up to 2 days after probation with Line Manager approval; from 1 September 2026, up to 3 days for employees rated Exceeds Expectations or higher. | KA-POL-01 cl. 4.3 (p. 2); KA-AMD-2026-01 cl. 2.1 (p. 1) **(all)** |
| q41 | What is the daily allowance for international travel? | USD 50 per day. The amendment did not change it. | KA-POL-05 cl. 5.1 (p. 1) |

## out_of_scope (3)

Not in the documents. The system should refuse instead of guessing.

| ID | Question | Correct answer | Source |
|---|---|---|---|
| q42 | What is the monthly stipend for interns? | Not covered. Intern terms are in the Internship Guidelines (KA-POL-07), which are not in the document set. | none |
| q43 | What is the company's health insurance coverage limit? | Not covered in the documents. | none |
| q44 | Who is the CEO of Kestrel Analytics? | Not covered. The CEO is mentioned as a role but never named. | none |
