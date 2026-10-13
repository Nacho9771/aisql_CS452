# Draft class-channel post — waiting for live experiment results

**Project:** Gym SQL Assistant

**Code and database:** https://github.com/Nacho9771/aisql_CS452

This database represents a weightlifting gym business: people and members,
membership plans, locations, employees, equipment, check-ins, maintenance,
opening hours, and recorded payments. The terminal app lets users ask questions
in ordinary language. It generates SQL, executes it against a fictional SQLite
database, and explains the returned data in ordinary language.

**Schema picture:** attach `w_gym_chat.jpg`.

**Working example:** select an actual successful run from `examples.md` after
OpenAI API access is funded and the experiments have been executed.

**Failure/limitation example:** Connor asked how many people upgraded their
membership plans. The schema only stores current plans, not the history of plan
changes, so it cannot establish whether a person upgraded. Include the app's
actual response after running the experiment.

**Additional examples:** attach the generated `examples.md` file, which will
record SQL, query results, and friendly responses for ten questions under three
prompt settings. No successful live model run is claimed yet.

**Prompt comparison:** zero-shot, single-domain few-shot, and cross-domain
few-shot are implemented. Compare the actual result/status matches, answer
quality, token usage, and costs after the experiments finish. Do not fill this
section with assumed outcomes.

**Current validation:** eighteen offline tests pass. The local database passes a
foreign-key check and contains 15 tables, 400 fictional people, 360 members,
10 gyms, and 60 employees from the supplied dummy data. Live OpenAI requests currently return HTTP 429, and the API
account has not yet been funded. This draft is not ready to post as completed work.
