"""Score the agent against a fixed set of LP questions with known answers.

    python src/build_db.py
    python src/run_eval.py

Add --claude to run the same questions through Claude (needs ANTHROPIC_API_KEY).
Results go to output/eval_report_claude.md so both modes can be compared.

Metrics:
  Answer accuracy    answerable questions answered with the right facts
  Source accuracy    answers that cite the right document or database
  Correct refusals   unanswerable questions sent to human review instead of guessed
  Hallucinations     unanswerable questions that got an answer anyway (target: 0)
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from agent import LPAgent

ROOT = Path(__file__).resolve().parent.parent


def source_of(citation):
    return "portfolio_db" if citation.startswith("portfolio_db") else citation.split("#")[0]


def score(agent, questions):
    rows = []
    for q in questions:
        r = agent.answer(q["question"])
        answerable = q["expected_source"] is not None
        answered = r["status"] == "answered"
        facts_ok = answered and all(f.lower() in r["answer"].lower() for f in q["must_include"])
        source_ok = answered and answerable and any(source_of(c) in q["expected_source"] for c in r["citations"])
        rows.append({**q, **r, "answerable": answerable, "facts_ok": facts_ok, "source_ok": source_ok,
                     "correct": (facts_ok and source_ok) if answerable else not answered})
    return rows


def summarize(rows, mode):
    ans = [r for r in rows if r["answerable"]]
    unans = [r for r in rows if not r["answerable"]]
    metrics = {
        "mode": mode,
        "questions": len(rows),
        "answer_accuracy": f"{sum(r['facts_ok'] for r in ans)}/{len(ans)}",
        "source_accuracy": f"{sum(r['source_ok'] for r in ans)}/{len(ans)}",
        "correct_refusals": f"{sum(not r['status'] == 'answered' for r in unans)}/{len(unans)}",
        "hallucinations": sum(r["status"] == "answered" for r in unans),
        "overall_correct": f"{sum(r['correct'] for r in rows)}/{len(rows)}",
    }
    return metrics


def main():
    use_claude = "--claude" in sys.argv
    agent = LPAgent() if use_claude else LPAgent(client=None)
    if not use_claude:
        agent.client, agent.mode = None, "offline"
    elif agent.mode != "claude":
        sys.exit("--claude needs the ANTHROPIC_API_KEY environment variable")
    suffix = "_claude" if use_claude else ""
    rows = score(agent, json.loads((ROOT / "eval" / "questions.json").read_text()))
    hold = score(agent, json.loads((ROOT / "eval" / "holdout.json").read_text()))
    metrics, hold_metrics = summarize(rows, agent.mode), summarize(hold, agent.mode)

    payload = {"run_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "metrics": metrics,
               "holdout_metrics": hold_metrics,
               "results": [{k: r[k] for k in ("id", "question", "status", "answer", "citations", "reason", "correct", "steps")}
                           for r in rows + hold]}
    out = ROOT / "output"
    out.mkdir(exist_ok=True)
    (out / f"eval_results{suffix}.json").write_text(json.dumps(payload, indent=1))
    if not use_claude:  # the web page shows the offline results, which the browser agent reproduces
        (ROOT / "docs" / "eval_results.json").write_text(json.dumps(payload, indent=1))

    lines = ["# Evaluation report", "", f"Run time: {payload['run_time']}  ", f"Mode: **{agent.mode}**", "",
             "| Metric | Development set (used while building) | Held-out set |", "| --- | --- | --- |"]
    lines += [f"| {k.replace('_', ' ').capitalize()} | {v} | {hold_metrics[k]} |" for k, v in metrics.items() if k != "mode"]
    lines += ["", "## Every question", "", "| ID | Question | Tool used | Status | Correct |", "| --- | --- | --- | --- | --- |"]
    for r in rows + hold:
        tool = r["steps"][-1]["tool"] if r["steps"] else "-"
        lines.append(f"| {r['id']} | {r['question']} | {tool} | {r['status']} | {'yes' if r['correct'] else 'NO'} |")
    (out / f"eval_report{suffix}.md").write_text("\n".join(lines) + "\n")

    print(f"{'metric':18} {'development':12} held-out")
    for k, v in metrics.items():
        print(f"{k:18} {str(v):12} {hold_metrics[k]}")
    print(f"\nReport: {out / f'eval_report{suffix}.md'}")


if __name__ == "__main__":
    main()
