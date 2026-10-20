"""Load the CRM portfolio export and fund metrics into a SQLite portfolio database.

This is the integration step: data arrives as a CSV export from a CRM, gets
checked for completeness and valid values, and only then is loaded where the
assistant can query it. Problems are written to output/data_quality.md so a
person can fix them at the source.

    python src/build_db.py
"""
import csv
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "output"
DB = OUT / "portfolio.db"
REQUIRED = ["company", "sector", "stage", "lead_partner", "invested_usd", "current_value_usd"]


def check_company(row):
    """Return a list of problems for one portfolio company row."""
    problems = [f"{f} is missing" for f in REQUIRED if not row.get(f, "").strip()]
    for f in ("invested_usd", "current_value_usd"):
        v = row.get(f, "").strip()
        if v:
            try:
                if float(v) < 0:
                    problems.append(f"{f} is negative ({v})")
            except ValueError:
                problems.append(f"{f} is not a number ({v})")
    return problems


def clean_number(v):
    try:
        f = float(v)
        return f if f >= 0 else None
    except (TypeError, ValueError):
        return None


def build():
    OUT.mkdir(exist_ok=True)
    companies = list(csv.DictReader(open(DATA / "crm_portfolio_export.csv")))
    metrics = list(csv.DictReader(open(DATA / "fund_metrics.csv")))

    issues = []
    for r in companies:
        for p in check_company(r):
            issues.append((r["company"], p))

    if DB.exists():
        DB.unlink()
    with sqlite3.connect(DB) as con:
        con.execute("""CREATE TABLE portfolio_companies (
            company TEXT PRIMARY KEY, sector TEXT, stage TEXT, lead_partner TEXT,
            invested_usd REAL, current_value_usd REAL, board_seat TEXT, first_investment TEXT)""")
        con.execute("""CREATE TABLE fund_metrics (
            quarter TEXT PRIMARY KEY, net_irr REAL, tvpi REAL, dpi REAL, nav_usd REAL)""")
        con.executemany("INSERT INTO portfolio_companies VALUES (?,?,?,?,?,?,?,?)", [
            (r["company"], r["sector"], r["stage"], r["lead_partner"] or None,
             clean_number(r["invested_usd"]), clean_number(r["current_value_usd"]),
             r["board_seat"], r["first_investment"]) for r in companies])
        con.executemany("INSERT INTO fund_metrics VALUES (?,?,?,?,?)", [
            (m["quarter"], float(m["net_irr"]), float(m["tvpi"]), float(m["dpi"]), float(m["nav_usd"]))
            for m in metrics])

    lines = ["# Portfolio data quality check", "",
             f"Rows loaded: {len(companies)} companies, {len(metrics)} quarters of fund metrics  ",
             f"Issues found: **{len(issues)}**", "", "| Company | Issue |", "| --- | --- |"]
    lines += [f"| {c} | {p} |" for c, p in issues] or ["| none | |"]
    (OUT / "data_quality.md").write_text("\n".join(lines) + "\n")

    # The browser demo reads the same data as JSON
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        export = {t: [dict(r) for r in con.execute(f"SELECT * FROM {t}")] for t in ("portfolio_companies", "fund_metrics")}
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "portfolio.json").write_text(json.dumps(export, indent=1))
    from retriever import load_sections
    sections = [{k: v for k, v in sec.items() if k != "tokens"} for sec in load_sections(ROOT / "corpus")]
    (ROOT / "docs" / "knowledge.json").write_text(json.dumps(sections, indent=1))

    print(f"Built {DB.name}: {len(companies)} companies, {len(metrics)} quarters, {len(issues)} data quality issues")
    return issues


if __name__ == "__main__":
    build()
