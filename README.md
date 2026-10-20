# LP Assistant Agent

Investor relations teams spend hours answering the same LP due diligence questions. What is the management fee? When are audited financials delivered? What was net IRR last quarter? Who leads our investment in a given company? The answers already exist, but they are spread across fund documents and a portfolio database.

This project is an AI agent that answers those questions. It decides which tool to use, answers with a citation for every fact, and sends anything it cannot confirm to a person instead of guessing.

**Live demo (runs in your browser, no login):** https://nagina0205-analytics.github.io/lp-ddq-ai-assistant/

All fund documents, companies and numbers are fictional.

## What it does

```
LP question
   |
   v
Agent plans the next step (Claude tool use, or the offline planner)
   |-- search_fund_documents  -> fund terms, fees, valuation, reporting, compliance
   |-- query_portfolio_db     -> read-only SQL on portfolio companies and fund metrics
   |-- route_to_human         -> when the sources do not answer it
   |
   v
Answer + citation, or "sent to investor relations" + the reason
```

- **Agentic workflow.** With an API key, Claude plans the steps and calls the tools through the Anthropic API's tool use feature. Without a key, a rule-based planner calls the same tools, so anyone can run it for free.
- **Integration and data quality.** `src/build_db.py` loads a CRM export into a SQLite portfolio database. It checks every row for missing and invalid values first. Two errors are planted on purpose, and the agent refuses to answer questions that depend on them instead of guessing.
- **Guardrails.** The SQL tool only allows a single read-only SELECT. An answer whose citation did not come from a tool result in that conversation is rejected as a possible hallucination. Questions about funds that aren't in the data go to a person.
- **Python and JavaScript.** The agent is written in Python. `docs/agent.js` is a JavaScript port that runs in the browser. A test checks that both versions give identical answers.
- **Adoption plan.** [ADOPTION.md](ADOPTION.md) covers the pilot, training session, success measures and ground rules for rolling it out to a team.

## Results

| Metric | Development set (used while building) | Held-out set |
| --- | --- | --- |
| Questions | 26 | 12 |
| Answer accuracy | 21/21 | 8/9 |
| Source accuracy | 21/21 | 8/9 |
| Correct refusals | 5/5 | 3/3 |
| Hallucinations | 0 | 0 |

Full report: [output/eval_report.md](output/eval_report.md). GitHub Actions refreshes it on every push.

**What the held-out set caught.** The development score is perfect because I built the agent against those questions. That's why there is a second set I didn't tune on. On its first run, the held-out set scored 10/12 with **one hallucination**: asked for Fund II's net IRR, the agent answered with Fund III's number. I added a guardrail that sends questions about other funds to a person. The held-out score is now 11/12 with zero hallucinations. The remaining miss (counting limited partners) is left in on purpose. Fixing it by tuning on the held-out set would make that score meaningless.

## Run it yourself

```
pip install -r requirements.txt
python src/build_db.py                    # load the CRM export, run data quality checks
python src/ask.py "What is the management fee?"
python src/run_eval.py                    # score the offline agent
python -m unittest discover tests -v      # Python tests
node tests/test_agent_js.js               # JavaScript matches Python
```

To use Claude, set your key and run the same commands:

```
export ANTHROPIC_API_KEY=your-key
python src/ask.py "What was net IRR last quarter?"
python src/run_eval.py --claude           # writes output/eval_report_claude.md
```

The Claude tool use loop is covered by unit tests that use a fake client: a normal cited answer, an invented citation, an answer with no tool call, a route to a person, and an attempted DELETE. All of these run without a key.

## Project layout

```
corpus/          fund documents (markdown, one section per topic)
data/            CRM portfolio export and fund metrics (CSV)
eval/            development and held-out question sets
src/build_db.py  integration: CSV to SQLite, with data quality checks
src/tools.py     the three tools and their JSON schemas
src/agent.py     the agent: Claude tool use loop and offline planner
src/run_eval.py  evaluation harness
docs/            browser demo (index.html, agent.js) for GitHub Pages
tests/           Python unit tests and the JavaScript parity test
ADOPTION.md      rollout, training and success measures
```

## What I'd do next with real data

Pull documents from the firm's data room and the CRM through their APIs, add the agent to the team's DDQ tracker, and grow the held-out set every month from the questions LPs actually ask.
