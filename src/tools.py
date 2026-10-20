"""The tools the agent can use. Each one is a plain Python function with a JSON schema,
so Claude can call it through the API's tool use feature.

1. search_fund_documents  find the document sections that answer a question
2. query_portfolio_db     run a read-only SQL query on the portfolio database
3. route_to_human         hand the question to the investor relations team
"""
import re
import sqlite3
from pathlib import Path

from retriever import BM25Retriever, load_sections

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "output" / "portfolio.db"
_retriever = None

SCHEMA_HINT = """Tables:
portfolio_companies(company, sector, stage, lead_partner, invested_usd, current_value_usd, board_seat, first_investment)
fund_metrics(quarter, net_irr, tvpi, dpi, nav_usd)   -- quarter looks like '2026-Q3'; net_irr is a decimal (0.162 = 16.2%)"""

TOOL_SCHEMAS = [
    {
        "name": "search_fund_documents",
        "description": "Search the fund's legal and policy documents (terms, fees, valuation, reporting, compliance). "
                       "Returns the best matching sections with their citation ids.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "query_portfolio_db",
        "description": "Run ONE read-only SQL SELECT on the portfolio database. " + SCHEMA_HINT,
        "input_schema": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]},
    },
    {
        "name": "route_to_human",
        "description": "Use when neither the documents nor the database answer the question. Never guess.",
        "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]},
    },
]


def search_fund_documents(query, k=5):
    global _retriever
    if _retriever is None:
        _retriever = BM25Retriever(load_sections(ROOT / "corpus"))
    return _retriever.search(query, k=k)


class UnsafeQuery(ValueError):
    pass


def query_portfolio_db(sql, limit=50):
    """Guardrails: one statement, SELECT only, database opened read-only."""
    s = sql.strip().rstrip(";")
    if ";" in s:
        raise UnsafeQuery("only one statement is allowed")
    if not re.match(r"(?is)^\s*(with\b.*?\)\s*)?select\b", s):
        raise UnsafeQuery("only SELECT queries are allowed")
    if re.search(r"(?i)\b(insert|update|delete|drop|alter|create|attach|pragma|replace)\b", s):
        raise UnsafeQuery("query contains a write or admin keyword")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(s).fetchmany(limit)]
    finally:
        con.close()


def run_tool(name, args):
    """Dispatch a tool call and return (result, citations)."""
    if name == "search_fund_documents":
        hits = search_fund_documents(args["query"])
        return [{"id": h["id"], "text": h["text"], "score": h["score"]} for h in hits], [h["id"] for h in hits]
    if name == "query_portfolio_db":
        try:
            rows = query_portfolio_db(args["sql"])
        except (UnsafeQuery, sqlite3.Error) as e:
            return {"error": str(e)}, []
        tables = sorted(set(re.findall(r"(?i)\b(portfolio_companies|fund_metrics)\b", args["sql"])))
        return rows, [f"portfolio_db:{t}" for t in tables]
    if name == "route_to_human":
        return {"routed": True, "reason": args.get("reason", "")}, []
    return {"error": f"unknown tool {name}"}, []
