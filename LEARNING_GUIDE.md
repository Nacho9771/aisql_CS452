# Learning guide (not a claim that you read the paper)

Read the assigned [paper](https://arxiv.org/html/2305.11853v3) yourself, particularly Sections 2–3 and the discussion of results. This guide helps you inspect the app.

The paper studies three settings: zero-shot provides schema and a question; single-domain few-shot adds examples from the same database; cross-domain few-shot uses examples from other databases. It also compares representations of schema, relationships, and table contents. Foreign keys and example values can help interpretation. Examples from the target database help with its join relationships, but do not supply all its content knowledge. Adding more examples does not always improve results; prompt length matters. Its older models and Spider benchmark differ from this small gym experiment.

## Things to investigate in this implementation

- Why send a schema? The model cannot inspect your SQLite file by itself.
- Why send column names with rows? `(18,)` is unclear without knowing what was counted.
- Why make two API calls? SQL generation and explaining actual results are separate jobs.
- What is a foreign key doing? Follow `member.person_id` to `person.person_id` and `member.home_location` to `gym_location.location_id` in a generated join.
- Why can a LEFT JOIN still lose an empty gym? Filtering the joined table in WHERE can remove its NULL row. For maintenance/check-ins, compare an ON condition.
- Why is COUNT(DISTINCT ...) different from COUNT(\*)? One counts distinct members; the other can count repeat visits or duplicated rows from a join.
- What would a one-row birthday query miss? This dataset deliberately has two equally common birthday dates. The query must preserve both if ties are requested.
- What does sharing an address prove? It supports a household proxy, not a family tree.
- Why can't the app answer upgrade history? A current plan and a previous plan are different facts. A change-history table would be needed to answer that question.
- Does successful execution prove correctness? Compare the generated query's result with the reference result, then check whether the friendly answer says the same thing.
- What does read-only protect? The DB file can be queried but not modified; that does not prevent a wrong SELECT or an inaccurate answer.
- What costs money? Both API calls consume input/output tokens. A few-shot prompt adds tokens before any answer is generated; inspect recorded usage and estimates.

For your report, describe what you actually observed. You can discuss a question that the schema cannot answer without claiming a model invented a wrong answer. Do not claim you've personally read/run/reviewed something until you've done it.