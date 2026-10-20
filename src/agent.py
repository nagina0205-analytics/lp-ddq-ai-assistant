"""Agentic LP assistant.

An LP asks a question. The agent decides which tool to use (search the fund
documents, query the portfolio database, or hand the question to a person),
then answers with a citation for every fact. Anything it cannot support goes
to the investor relations team instead of being guessed.

Two modes, same tools and guardrails:
  - Claude mode (ANTHROPIC_API_KEY is set): Claude plans the steps and calls
    the tools through the Anthropic API's tool use feature.
  - Offline mode (no key): a rule-based planner calls the same tools. Free to
    run, used in tests, and ported to JavaScript for the browser demo.
"""
import json
import os
import re

from retriever import tokenize
from tools import TOOL_SCHEMAS, query_portfolio_db, run_tool
import tools

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
MAX_STEPS = 6
MIN_COVERAGE = 0.5
HUMAN_REVIEW = "I could not confirm this from the fund documents or the portfolio database, so I have routed it to the investor relations team."

AGENT_PROMPT = """You are an assistant for a venture firm's investor relations team. You answer due diligence
questions from limited partners (LPs).
Use the tools to find facts. Use search_fund_documents for fund terms, fees, policies, reporting and compliance.
Use query_portfolio_db for portfolio companies and fund performance numbers.
Rules:
- Every fact in your answer must come from a tool result in this conversation. Never use outside knowledge.
- If the tools do not answer the question, call route_to_human. Do not guess.
- Keep answers to one to three plain sentences with exact figures.
When you are done, reply with JSON only:
{"answer": "...", "citations": ["<section id or portfolio_db:table>", ...]}"""


def _get(block, key):
    return block.get(key) if isinstance(block, dict) else getattr(block, key, None)


class LPAgent:
    def __init__(self, client=None):
        self.client = client
        if self.client is None and os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic
            self.client = anthropic.Anthropic()
        self.mode = "claude" if self.client else "offline"

    def answer(self, question):
        trace = []
        if self.mode == "claude":
            return self._claude(question, trace)
        return self._offline(question, trace)

    # ---------------- Claude mode: real tool use loop ----------------
    def _claude(self, question, trace):
        messages = [{"role": "user", "content": question}]
        allowed_citations = set()
        for _ in range(MAX_STEPS):
            resp = self.client.messages.create(model=MODEL, max_tokens=800, system=AGENT_PROMPT,
                                               tools=TOOL_SCHEMAS, messages=messages)
            content = _get(resp, "content") or []
            if _get(resp, "stop_reason") != "tool_use":
                text = "".join(_get(b, "text") or "" for b in content if _get(b, "type") == "text")
                return self._finish(question, text, allowed_citations, trace)
            messages.append({"role": "assistant", "content": content})
            results = []
            for b in content:
                if _get(b, "type") != "tool_use":
                    continue
                name, args = _get(b, "name"), _get(b, "input") or {}
                result, cites = run_tool(name, args)
                trace.append({"tool": name, "input": args, "citations": cites})
                if name == "route_to_human":
                    return self._review(question, args.get("reason", "agent chose human review"), trace)
                allowed_citations.update(cites)
                results.append({"type": "tool_result", "tool_use_id": _get(b, "id"),
                                "content": json.dumps(result, default=str)[:6000]})
            messages.append({"role": "user", "content": results})
        return self._review(question, "agent hit the step limit", trace)

    def _finish(self, question, text, allowed, trace):
        try:
            data = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        except (AttributeError, json.JSONDecodeError):
            return self._review(question, "final reply was not valid JSON", trace)
        cites = [c for c in data.get("citations", []) if c in allowed]
        if not cites or not data.get("answer"):
            # Guardrail: no citation from a real tool result means a possible hallucination.
            return self._review(question, "answer had no citation from a tool result", trace)
        return self._result(question, data["answer"].strip(), cites, "answered", "", trace)

    # ---------------- Offline mode: rule-based planner ----------------
    def _offline(self, question, trace):
        q = question.lower()
        other_fund = re.search(r"\bfund\s+(i|ii|iv|v|vi|\d+)\b", q)
        if other_fund and other_fund.group(1) != "iii" and other_fund.group(1) != "3":
            # Guardrail added after the held-out test: the data only covers Fund III.
            trace.append({"tool": "route_to_human", "input": {"reason": "other fund"}, "citations": []})
            return self._review(question, f"question is about Fund {other_fund.group(1).upper()}, but the data only covers Fund III", trace)
        companies = [r["company"] for r in query_portfolio_db("SELECT company FROM portfolio_companies")]
        sectors = [r["sector"] for r in query_portfolio_db("SELECT DISTINCT sector FROM portfolio_companies")]

        if re.search(r"\b(irr|tvpi|dpi|nav)\b", q):
            return self._metric_answer(question, q, trace)
        named = [c for c in companies if c.lower() in q]
        if named:
            return self._company_answer(question, q, named[0], trace)
        if re.search(r"\b(exposure|how many companies|portfolio companies in)\b", q):
            return self._sector_answer(question, q, sectors, trace)
        return self._document_answer(question, trace)

    def _sql(self, sql, trace):
        rows, cites = run_tool("query_portfolio_db", {"sql": sql})
        trace.append({"tool": "query_portfolio_db", "input": {"sql": sql}, "citations": cites})
        return rows, cites

    def _metric_answer(self, question, q, trace):
        rows, cites = self._sql("SELECT quarter, net_irr, tvpi, dpi, nav_usd FROM fund_metrics ORDER BY quarter DESC LIMIT 1", trace)
        if not rows:
            return self._review(question, "no fund metrics loaded", trace)
        r = rows[0]
        parts = []
        if "irr" in q: parts.append(f"net IRR was {r['net_irr'] * 100:.1f}%")
        if "tvpi" in q: parts.append(f"TVPI was {r['tvpi']:.2f}x")
        if "dpi" in q: parts.append(f"DPI was {r['dpi']:.2f}x")
        if "nav" in q: parts.append(f"NAV was ${r['nav_usd'] / 1e6:,.0f} million")
        return self._result(question, f"As of {r['quarter']}, " + " and ".join(parts) + ".", cites, "answered", "", trace)

    FIELDS = [("lead partner|partner|who leads|who is the lead", "lead_partner", "The lead partner on {c} is {v}."),
              ("invest|check|cost", "invested_usd", "The fund has invested ${v:,.0f} in {c}."),
              ("value|worth|mark", "current_value_usd", "{c} is currently held at ${v:,.0f}."),
              ("board", "board_seat", "Board seat at {c}: {v}."),
              ("stage", "stage", "{c} is a {v} company."),
              ("sector|industry", "sector", "{c} is in {v}.")]

    def _company_answer(self, question, q, company, trace):
        for pattern, col, template in self.FIELDS:
            if re.search(pattern, q):
                rows, cites = self._sql(f"SELECT {col} FROM portfolio_companies WHERE company = '{company}'", trace)
                v = rows[0][col] if rows else None
                if v in (None, ""):
                    # Data completeness: the record exists but this field is empty or failed validation.
                    return self._review(question, f"{col} for {company} is missing in the portfolio database", trace)
                return self._result(question, template.format(c=company, v=v), cites, "answered", "", trace)
        return self._review(question, f"not sure which detail about {company} is being asked for", trace)

    def _sector_answer(self, question, q, sectors, trace):
        match = [s for s in sectors if s.lower() in q]
        if not match:
            rows, cites = self._sql("SELECT DISTINCT sector FROM portfolio_companies", trace)
            names = ", ".join(r["sector"] for r in rows)
            return self._result(question, f"The fund has no portfolio companies in that sector. Current sectors: {names}.",
                                cites, "answered", "", trace)
        s = match[0]
        rows, cites = self._sql("SELECT COUNT(*) AS n, SUM(invested_usd) AS inv FROM portfolio_companies "
                                f"WHERE sector = '{s}'", trace)
        r = rows[0]
        return self._result(question, f"The fund has {r['n']} companies in {s}, with ${r['inv'] / 1e6:,.1f} million invested.",
                            cites, "answered", "", trace)

    def _document_answer(self, question, trace):
        tools.search_fund_documents("warm up")
        retr = tools._retriever
        q_terms = tokenize(question, expand=True)
        raw_terms = tokenize(question)
        from retriever import SYNONYMS, stem
        def known(t):
            return t in retr.vocab or any(stem(x) in retr.vocab for k, v in SYNONYMS.items() if stem(k) == t for x in v)
        unknown = [t for t in raw_terms if not known(t)]
        if len(unknown) >= 2 or any(re.fullmatch(r"i{1,3}v?|vi{0,3}|iv|ix|x", t) for t in unknown):
            trace.append({"tool": "search_fund_documents", "input": {"query": question}, "citations": []})
            return self._review(question, f"no document covers: {', '.join(unknown)}", trace)

        hits, cites = run_tool("search_fund_documents", {"query": question})
        trace.append({"tool": "search_fund_documents", "input": {"query": question}, "citations": cites})
        if not hits or hits[0]["score"] < 1.0:
            return self._review(question, "no relevant section found", trace)

        qset = set(q_terms)
        scored = []
        for rank, h in enumerate(hits):
            for i, sent in enumerate(re.split(r"(?<=[.!?])\s+", h["text"])):
                cov = len(qset & set(tokenize(sent + " " + h["id"].split("#")[1]))) / max(1, len(qset))
                scored.append((cov - 0.05 * rank + self._intent_bonus(question, sent), rank, i, sent, h["id"]))
        scored.sort(key=lambda x: -x[0])
        best = scored[0]
        if best[0] < MIN_COVERAGE:
            return self._review(question, f"best sentence matched only {best[0]:.0%} of the question", trace)
        answer = best[3]
        if " and " in question.lower():
            second = [s for s in scored[1:] if s[4] == best[4] and s[3] != best[3] and re.search(r"\d", s[3])]
            if second:
                answer += " " + second[0][3]
        return self._result(question, answer, [best[4]], "answered", "", trace)

    @staticmethod
    def _intent_bonus(question, sentence):
        q, s = question.lower(), sentence.lower()
        if "size" in q and "total" in s: return 0.2
        if q.startswith("how long") and re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)[- ](years?|months?)\b", s): return 0.2
        if q.startswith("when") and re.search(r"\b(days?|within|after|each)\b", s): return 0.15
        if re.match(r"how (much|many)", q) and re.search(r"\d", s): return 0.15
        if q.startswith("who") and re.search(r"\b(members?|officer|partner|advisor)\b", s): return 0.1
        return 0.0

    # ---------------- helpers ----------------
    def _review(self, question, reason, trace):
        return self._result(question, HUMAN_REVIEW, [], "needs_human_review", reason, trace)

    def _result(self, question, answer, citations, status, reason, trace):
        return {"question": question, "status": status, "answer": answer, "citations": citations,
                "reason": reason, "mode": self.mode, "steps": trace}
