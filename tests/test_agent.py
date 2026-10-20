"""Unit tests. Run from the project folder:

    python src/build_db.py
    python -m unittest discover tests -v

The Claude tests use a fake client, so they check the tool use loop and the
guardrails without calling the API or needing a key.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.pop("ANTHROPIC_API_KEY", None)

import build_db  # noqa: E402
from agent import LPAgent  # noqa: E402
from tools import UnsafeQuery, query_portfolio_db  # noqa: E402

build_db.build()


class FakeClaude:
    """Plays back a scripted list of replies, the way the real API would return them."""
    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.script.pop(0)


def tool_call(name, args, call_id="t1"):
    return {"stop_reason": "tool_use", "content": [{"type": "tool_use", "id": call_id, "name": name, "input": args}]}


def final(text):
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": text}]}


class SqlGuardrailTests(unittest.TestCase):
    def test_select_works(self):
        self.assertEqual(len(query_portfolio_db("SELECT company FROM portfolio_companies")), 10)

    def test_write_is_blocked(self):
        with self.assertRaises(UnsafeQuery):
            query_portfolio_db("DROP TABLE portfolio_companies")

    def test_second_statement_is_blocked(self):
        with self.assertRaises(UnsafeQuery):
            query_portfolio_db("SELECT 1; DELETE FROM fund_metrics")


class DataQualityTests(unittest.TestCase):
    def test_planted_issues_are_found(self):
        issues = build_db.build()
        self.assertIn(("Mosaiq", "lead_partner is missing"), issues)
        self.assertTrue(any(c == "Driftwave" and "negative" in p for c, p in issues))


class OfflineAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = LPAgent()

    def test_document_question_cites_source(self):
        r = self.agent.answer("What is the management fee during the investment period?")
        self.assertEqual(r["status"], "answered")
        self.assertIn("2.5%", r["answer"])
        self.assertTrue(r["citations"][0].startswith("fees_and_expenses"))

    def test_database_question(self):
        r = self.agent.answer("Who is the lead partner on Lumora?")
        self.assertIn("Dana Whitfield", r["answer"])
        self.assertEqual(r["citations"], ["portfolio_db:portfolio_companies"])

    def test_missing_data_goes_to_a_person(self):
        self.assertEqual(self.agent.answer("Who is the lead partner on Mosaiq?")["status"], "needs_human_review")

    def test_unknown_topic_goes_to_a_person(self):
        self.assertEqual(self.agent.answer("Has any LP signed a side letter?")["status"], "needs_human_review")

    def test_other_fund_goes_to_a_person(self):
        self.assertEqual(self.agent.answer("What was the net IRR of Fund II?")["status"], "needs_human_review")


class ClaudeLoopTests(unittest.TestCase):
    def test_tool_use_then_cited_answer(self):
        fake = FakeClaude([
            tool_call("query_portfolio_db", {"sql": "SELECT net_irr FROM fund_metrics ORDER BY quarter DESC LIMIT 1"}),
            final('{"answer": "Net IRR was 16.2% as of 2026-Q3.", "citations": ["portfolio_db:fund_metrics"]}'),
        ])
        r = LPAgent(client=fake).answer("What is the latest net IRR?")
        self.assertEqual(r["status"], "answered")
        self.assertEqual(r["steps"][0]["tool"], "query_portfolio_db")
        # The tool result was sent back to the model on the second call
        self.assertEqual(fake.calls[1]["messages"][-1]["content"][0]["type"], "tool_result")

    def test_made_up_citation_is_rejected(self):
        fake = FakeClaude([
            tool_call("search_fund_documents", {"query": "management fee"}),
            final('{"answer": "The fee is 1%.", "citations": ["secret_memo#Fees"]}'),
        ])
        r = LPAgent(client=fake).answer("What is the management fee?")
        self.assertEqual(r["status"], "needs_human_review")

    def test_answer_without_tools_is_rejected(self):
        fake = FakeClaude([final('{"answer": "About 20%.", "citations": []}')])
        self.assertEqual(LPAgent(client=fake).answer("What is the IRR?")["status"], "needs_human_review")

    def test_route_to_human_is_respected(self):
        fake = FakeClaude([tool_call("route_to_human", {"reason": "not in the documents"})])
        r = LPAgent(client=fake).answer("Do you offer co-investment?")
        self.assertEqual(r["status"], "needs_human_review")
        self.assertEqual(r["reason"], "not in the documents")

    def test_unsafe_sql_from_model_is_blocked(self):
        fake = FakeClaude([
            tool_call("query_portfolio_db", {"sql": "DELETE FROM fund_metrics"}),
            final('{"answer": "Done.", "citations": []}'),
        ])
        r = LPAgent(client=fake).answer("Clean up the metrics")
        self.assertEqual(r["status"], "needs_human_review")
        self.assertEqual(len(query_portfolio_db("SELECT * FROM fund_metrics")), 5)


if __name__ == "__main__":
    unittest.main()
