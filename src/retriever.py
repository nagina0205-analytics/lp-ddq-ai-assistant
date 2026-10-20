"""Split fund documents into sections and find the ones that best match a question.

Uses BM25, a standard keyword ranking method, written in plain Python so the
project has no heavy dependencies. The same logic is ported to JavaScript in
docs/agent.js for the browser demo.
"""
import math
import re
from collections import Counter
from pathlib import Path

STOPWORDS = set("""a an and are as at be by can do does did for from get has have how i in is it its
of on or our the their there this to was what when where which who whom why will with you your
much many long often any fund funds firm northwind ventures iii lp lps""".split())

SYNONYMS = {"size": ["total", "commitment"], "gp": ["general", "partner"], "increase": ["rise"],
            "industry": ["cover"], "industries": ["cover"]}


def stem(w):
    if w.endswith("s") and not w.endswith("ss") and len(w) > 4 and not re.search(r"(ies|ches|shes|xes|sses)$", w):
        w = w[:-1]
    for suf in ("ing", "ment", "ly"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if re.search(r"(ss|x|ch|sh)es$", w):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def tokenize(text, expand=False):
    out = []
    for w in re.findall(r"[a-z0-9]+(?:\.[0-9]+)?%?", text.lower()):
        if w in STOPWORDS:
            continue
        if expand and w in SYNONYMS:
            out.extend(stem(s) for s in SYNONYMS[w])
        else:
            out.append(stem(w))
    return out


def load_sections(corpus_dir):
    """Each '## heading' section becomes one searchable chunk with a citation id."""
    sections = []
    for path in sorted(Path(corpus_dir).glob("*.md")):
        doc, current, lines = path.stem, None, []
        for line in path.read_text().splitlines():
            if line.startswith("## "):
                if current and lines:
                    sections.append(make_section(doc, current, lines))
                current, lines = line[3:].strip(), []
            elif current and line.strip():
                lines.append(line.strip())
        if current and lines:
            sections.append(make_section(doc, current, lines))
    return sections


def make_section(doc, heading, lines):
    text = " ".join(lines)
    return {"id": f"{doc}#{heading}", "doc": doc, "heading": heading, "text": text,
            "tokens": tokenize(heading + " " + text)}


class BM25Retriever:
    def __init__(self, sections, k1=1.5, b=0.75):
        self.sections = sections
        self.k1, self.b = k1, b
        self.avg_len = sum(len(s["tokens"]) for s in sections) / len(sections)
        df = Counter(t for s in sections for t in set(s["tokens"]))
        n = len(sections)
        self.vocab = set(df)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def score(self, q, section):
        tf, length, total = Counter(section["tokens"]), len(section["tokens"]), 0.0
        for t in q:
            if t in tf:
                num = tf[t] * (self.k1 + 1)
                den = tf[t] + self.k1 * (1 - self.b + self.b * length / self.avg_len)
                total += self.idf[t] * num / den
        return total

    def search(self, question, k=3):
        q = tokenize(question, expand=True)
        ranked = sorted(((self.score(q, s), s) for s in self.sections), key=lambda x: -x[0])
        return [{"score": round(sc, 3), **{k2: v for k2, v in s.items() if k2 != "tokens"}}
                for sc, s in ranked[:k] if sc > 0]
