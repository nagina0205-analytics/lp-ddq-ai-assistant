/*
 * Parity test: the JavaScript agent must give the same status, answer and
 * citations as the Python agent on every evaluation question.
 *
 * Run from the project folder after `python src/run_eval.py`:
 *     node tests/test_agent_js.js
 */
const fs = require("fs");
const path = require("path");
const { LPAgentJS } = require("../docs/agent.js");

const docs = path.join(__dirname, "..", "docs");
const knowledge = JSON.parse(fs.readFileSync(path.join(docs, "knowledge.json"), "utf8"));
const portfolio = JSON.parse(fs.readFileSync(path.join(docs, "portfolio.json"), "utf8"));
const python = JSON.parse(fs.readFileSync(path.join(docs, "eval_results.json"), "utf8")).results;

const agent = new LPAgentJS(knowledge, portfolio);
let failures = 0;
for (const p of python) {
  const js = agent.answer(p.question);
  const same = js.status === p.status && js.answer === p.answer &&
    JSON.stringify(js.citations) === JSON.stringify(p.citations);
  if (!same) {
    failures++;
    console.log(`MISMATCH ${p.id}: ${p.question}`);
    console.log(`  python: [${p.status}] ${p.answer} ${JSON.stringify(p.citations)}`);
    console.log(`  js:     [${js.status}] ${js.answer} ${JSON.stringify(js.citations)}`);
  }
}
console.log(`${python.length - failures}/${python.length} questions match between Python and JavaScript`);
process.exit(failures ? 1 : 0);
