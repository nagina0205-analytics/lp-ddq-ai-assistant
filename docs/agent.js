/*
 * LP assistant, JavaScript version.
 *
 * A port of the Python offline agent (src/agent.py, src/retriever.py) so the
 * agent runs in any browser with no server and no API key. Same tools, same
 * guardrails, same answers: tests/test_agent_js.js checks that both versions
 * agree on every evaluation question.
 *
 * Works in the browser (window.LPAgentJS) and in Node (module.exports).
 */
(function (root) {
  "use strict";

  const STOPWORDS = new Set(("a an and are as at be by can do does did for from get has have how i in is it its " +
    "of on or our the their there this to was what when where which who whom why will with you your " +
    "much many long often any fund funds firm northwind ventures iii lp lps").split(" "));
  const SYNONYMS = { size: ["total", "commitment"], gp: ["general", "partner"], increase: ["rise"],
    industry: ["cover"], industries: ["cover"] };
  const HUMAN_REVIEW = "I could not confirm this from the fund documents or the portfolio database, so I have routed it to the investor relations team.";
  const MIN_COVERAGE = 0.5;

  function stem(w) {
    if (w.endsWith("s") && !w.endsWith("ss") && w.length > 4 && !/(ies|ches|shes|xes|sses)$/.test(w)) w = w.slice(0, -1);
    for (const suf of ["ing", "ment", "ly"]) {
      if (w.endsWith(suf) && w.length - suf.length >= 3) return w.slice(0, -suf.length);
    }
    if (w.endsWith("ies") && w.length > 4) return w.slice(0, -3) + "y";
    if (/(ss|x|ch|sh)es$/.test(w)) return w.slice(0, -2);
    if (w.endsWith("s") && !w.endsWith("ss") && w.length > 3) return w.slice(0, -1);
    return w;
  }

  function tokenize(text, expand) {
    const out = [];
    for (const w of text.toLowerCase().match(/[a-z0-9]+(?:\.[0-9]+)?%?/g) || []) {
      if (STOPWORDS.has(w)) continue;
      if (expand && SYNONYMS[w]) SYNONYMS[w].forEach(s => out.push(stem(s)));
      else out.push(stem(w));
    }
    return out;
  }

  const count = arr => arr.reduce((m, t) => m.set(t, (m.get(t) || 0) + 1), new Map());
  const money0 = v => v.toLocaleString("en-US", { maximumFractionDigits: 0 });
  const money1 = v => v.toLocaleString("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  class BM25 {
    constructor(sections, k1 = 1.5, b = 0.75) {
      this.k1 = k1; this.b = b;
      this.sections = sections.map(s => ({ ...s, tokens: tokenize(s.heading + " " + s.text) }));
      this.avgLen = this.sections.reduce((a, s) => a + s.tokens.length, 0) / this.sections.length;
      const df = new Map();
      this.sections.forEach(s => new Set(s.tokens).forEach(t => df.set(t, (df.get(t) || 0) + 1)));
      const n = this.sections.length;
      this.vocab = new Set(df.keys());
      this.idf = new Map([...df].map(([t, d]) => [t, Math.log(1 + (n - d + 0.5) / (d + 0.5))]));
    }
    score(q, s) {
      const tf = count(s.tokens), len = s.tokens.length;
      let total = 0;
      for (const t of q) {
        if (!tf.has(t)) continue;
        const f = tf.get(t);
        total += this.idf.get(t) * (f * (this.k1 + 1)) / (f + this.k1 * (1 - this.b + this.b * len / this.avgLen));
      }
      return total;
    }
    search(question, k = 5) {
      const q = tokenize(question, true);
      return this.sections.map(s => ({ score: this.score(q, s), s }))
        .sort((a, b) => b.score - a.score).slice(0, k).filter(x => x.score > 0)
        .map(x => ({ score: Math.round(x.score * 1000) / 1000, id: x.s.id, heading: x.s.heading, text: x.s.text }));
    }
  }

  class LPAgentJS {
    constructor(knowledge, portfolio) {
      this.retriever = new BM25(knowledge);
      this.db = portfolio;
      this.mode = "offline-js";
    }

    answer(question) {
      const trace = [], q = question.toLowerCase();
      const other = q.match(/\bfund\s+(i|ii|iv|v|vi|\d+)\b/);
      if (other && other[1] !== "iii" && other[1] !== "3") {
        trace.push({ tool: "route_to_human", input: { reason: "other fund" }, citations: [] });
        return this.review(question, `question is about Fund ${other[1].toUpperCase()}, but the data only covers Fund III`, trace);
      }
      const companies = this.db.portfolio_companies.map(r => r.company);
      const sectors = [...new Set(this.db.portfolio_companies.map(r => r.sector))];
      if (/\b(irr|tvpi|dpi|nav)\b/.test(q)) return this.metric(question, q, trace);
      const named = companies.filter(c => q.includes(c.toLowerCase()));
      if (named.length) return this.company(question, q, named[0], trace);
      if (/\b(exposure|how many companies|portfolio companies in)\b/.test(q)) return this.sector(question, q, sectors, trace);
      return this.documents(question, trace);
    }

    // "SQL" against the exported tables. The query text is recorded so the steps match the Python agent.
    query(sql, table, fn, trace) {
      const cites = [`portfolio_db:${table}`];
      trace.push({ tool: "query_portfolio_db", input: { sql }, citations: cites });
      return [fn(this.db[table]), cites];
    }

    metric(question, q, trace) {
      const [r, cites] = this.query("SELECT quarter, net_irr, tvpi, dpi, nav_usd FROM fund_metrics ORDER BY quarter DESC LIMIT 1",
        "fund_metrics", rows => [...rows].sort((a, b) => b.quarter.localeCompare(a.quarter))[0], trace);
      if (!r) return this.review(question, "no fund metrics loaded", trace);
      const parts = [];
      if (q.includes("irr")) parts.push(`net IRR was ${(r.net_irr * 100).toFixed(1)}%`);
      if (q.includes("tvpi")) parts.push(`TVPI was ${r.tvpi.toFixed(2)}x`);
      if (q.includes("dpi")) parts.push(`DPI was ${r.dpi.toFixed(2)}x`);
      if (q.includes("nav")) parts.push(`NAV was $${money0(r.nav_usd / 1e6)} million`);
      return this.result(question, `As of ${r.quarter}, ` + parts.join(" and ") + ".", cites, "answered", "", trace);
    }

    company(question, q, c, trace) {
      const fields = [
        [/lead partner|partner|who leads|who is the lead/, "lead_partner", v => `The lead partner on ${c} is ${v}.`],
        [/invest|check|cost/, "invested_usd", v => `The fund has invested $${money0(v)} in ${c}.`],
        [/value|worth|mark/, "current_value_usd", v => `${c} is currently held at $${money0(v)}.`],
        [/board/, "board_seat", v => `Board seat at ${c}: ${v}.`],
        [/stage/, "stage", v => `${c} is a ${v} company.`],
        [/sector|industry/, "sector", v => `${c} is in ${v}.`],
      ];
      for (const [re, col, fmt] of fields) {
        if (!re.test(q)) continue;
        const [row, cites] = this.query(`SELECT ${col} FROM portfolio_companies WHERE company = '${c}'`,
          "portfolio_companies", rows => rows.find(r => r.company === c), trace);
        const v = row ? row[col] : null;
        if (v === null || v === undefined || v === "") {
          return this.review(question, `${col} for ${c} is missing in the portfolio database`, trace);
        }
        return this.result(question, fmt(v), cites, "answered", "", trace);
      }
      return this.review(question, `not sure which detail about ${c} is being asked for`, trace);
    }

    sector(question, q, sectors, trace) {
      const match = sectors.filter(s => q.includes(s.toLowerCase()));
      if (!match.length) {
        const [names, cites] = this.query("SELECT DISTINCT sector FROM portfolio_companies", "portfolio_companies",
          rows => [...new Set(rows.map(r => r.sector))].join(", "), trace);
        return this.result(question, `The fund has no portfolio companies in that sector. Current sectors: ${names}.`, cites, "answered", "", trace);
      }
      const s = match[0];
      const [r, cites] = this.query(`SELECT COUNT(*) AS n, SUM(invested_usd) AS inv FROM portfolio_companies WHERE sector = '${s}'`,
        "portfolio_companies", rows => {
          const hit = rows.filter(x => x.sector === s);
          return { n: hit.length, inv: hit.reduce((a, x) => a + (x.invested_usd || 0), 0) };
        }, trace);
      return this.result(question, `The fund has ${r.n} companies in ${s}, with $${money1(r.inv / 1e6)} million invested.`, cites, "answered", "", trace);
    }

    documents(question, trace) {
      const vocab = this.retriever.vocab;
      const known = t => vocab.has(t) || Object.entries(SYNONYMS).some(([k, v]) => stem(k) === t && v.some(x => vocab.has(stem(x))));
      const unknown = tokenize(question).filter(t => !known(t));
      if (unknown.length >= 2 || unknown.some(t => /^(i{1,3}v?|vi{0,3}|iv|ix|x)$/.test(t))) {
        trace.push({ tool: "search_fund_documents", input: { query: question }, citations: [] });
        return this.review(question, `no document covers: ${unknown.join(", ")}`, trace);
      }
      const hits = this.retriever.search(question);
      trace.push({ tool: "search_fund_documents", input: { query: question }, citations: hits.map(h => h.id) });
      if (!hits.length || hits[0].score < 1.0) return this.review(question, "no relevant section found", trace);

      const qset = new Set(tokenize(question, true));
      const scored = [];
      hits.forEach((h, rank) => {
        h.text.split(/(?<=[.!?])\s+/).forEach((sent, i) => {
          const st = new Set(tokenize(sent + " " + h.id.split("#")[1]));
          const cov = [...qset].filter(t => st.has(t)).length / Math.max(1, qset.size);
          scored.push([cov - 0.05 * rank + intentBonus(question, sent), rank, i, sent, h.id]);
        });
      });
      scored.sort((a, b) => b[0] - a[0]);
      const best = scored[0];
      if (best[0] < MIN_COVERAGE) return this.review(question, `best sentence matched only ${Math.round(best[0] * 100)}% of the question`, trace);
      let answer = best[3];
      if (question.toLowerCase().includes(" and ")) {
        const second = scored.slice(1).find(s => s[4] === best[4] && s[3] !== best[3] && /\d/.test(s[3]));
        if (second) answer += " " + second[3];
      }
      return this.result(question, answer, [best[4]], "answered", "", trace);
    }

    review(question, reason, trace) { return this.result(question, HUMAN_REVIEW, [], "needs_human_review", reason, trace); }
    result(question, answer, citations, status, reason, trace) {
      return { question, status, answer, citations, reason, mode: this.mode, steps: trace };
    }
  }

  function intentBonus(question, sentence) {
    const q = question.toLowerCase(), s = sentence.toLowerCase();
    if (q.includes("size") && s.includes("total")) return 0.2;
    if (q.startsWith("how long") && /\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)[- ](years?|months?)\b/.test(s)) return 0.2;
    if (q.startsWith("when") && /\b(days?|within|after|each)\b/.test(s)) return 0.15;
    if (/^how (much|many)/.test(q) && /\d/.test(s)) return 0.15;
    if (q.startsWith("who") && /\b(members?|officer|partner|advisor)\b/.test(s)) return 0.1;
    return 0;
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { LPAgentJS, tokenize, stem };
  else root.LPAgentJS = LPAgentJS;
})(typeof window !== "undefined" ? window : globalThis);
