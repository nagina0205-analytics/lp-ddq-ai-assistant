"""Ask the agent one question from the command line.

    python src/ask.py "What is the management fee?"
"""
import sys

from agent import LPAgent

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What is the management fee during the investment period?"
    r = LPAgent().answer(question)
    print(f"Q: {r['question']}\nA: {r['answer']}")
    print(f"Sources: {', '.join(r['citations']) or 'none'} | status: {r['status']} | mode: {r['mode']}")
    for s in r["steps"]:
        print(f"  step: {s['tool']} {s['input']}")
    if r["reason"]:
        print(f"Why: {r['reason']}")
