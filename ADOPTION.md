# Rolling out the LP Assistant to an investor relations team

A tool nobody trusts doesn't get used. This is the plan I would follow to take the agent from a pilot to everyday use, and the guide I would hand the team.

## 1. Pilot (weeks 1 to 3)

- Pick 2 people on the team and one narrow job: first drafts of DDQ answers.
- The agent drafts. A person reviews every answer before it goes to an LP. Nothing goes out unreviewed.
- Log every answer the reviewer had to change, and why. Those become new test questions.

**Exit criteria to widen the pilot:** at least 90% of drafts accepted with light edits, and zero answers that cited a source that did not say what the answer claimed.

## 2. Team rollout (weeks 4 to 8)

- Run a 45 minute training session (outline below), then office hours twice a week for the first month.
- Add the agent to the existing workflow instead of creating a new one. For example, run it from the DDQ tracker the team already uses.
- Name one owner for the documents and the portfolio data. The agent is only as current as its sources.

## 3. Measure and keep it honest

Track these every month and share them with the team:

| Measure | Why it matters |
| --- | --- |
| Hours saved on DDQ first drafts | The reason the tool exists |
| Share of answers accepted without edits | Trust and quality |
| Questions routed to a person, by reason | Shows which documents or data are missing |
| Hallucinations caught in review | Must stay at zero; any case triggers a fix and a new test |
| Data quality issues open in the CRM | Missing data turns into routed questions |

Every month, add the questions people actually asked to the held-out test set. Re-run the evaluation before any change to the prompt, the model or the documents.

## Training session outline (45 minutes)

1. **What it does and what it doesn't** (10 min). It answers from our documents and portfolio data only. It cites a source for every fact. When it can't confirm something, it says so and routes the question to us.
2. **Live demo** (10 min). Three questions: one from the documents, one from the portfolio data, one it should refuse.
3. **How to review an answer** (15 min). Open the cited section. Check the number. If the answer is wrong, log it with the question. That log is how the tool improves.
4. **Hands-on** (10 min). Everyone asks five real questions from a recent DDQ.

## Ground rules for the team

- The person who sends an answer to an LP owns that answer, not the tool.
- Never paste LP personal data or anything confidential into a tool that isn't approved.
- If the agent routes a question to you, that usually means a document or a data field is missing. Fix the source, not just the answer.
