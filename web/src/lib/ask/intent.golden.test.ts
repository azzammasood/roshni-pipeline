// The router against the golden set: every golden question and paraphrase is a data question
// for the planner, except the documented forecast case, which the site answers with the
// visitor's own feeder schedule instead (the planner still refuses it for the CLI and MCP).
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { isPersonalSchedule } from "./intent";

const ROUTED_ON_PURPOSE = /^refuse_forecast(~|$)/;

function golden(): { id: string; q: string }[] {
  const text = readFileSync(path.join(__dirname, "../../../../config/ask_golden.yml"), "utf8");
  const out: { id: string; q: string }[] = [];
  let id = "";
  let n = 0;
  for (const line of text.split("\n")) {
    const m = line.match(/^ {2}- id: (\S+)/);
    if (m) [id, n] = [m[1], 0];
    const q = line.match(/^ {4}question: (.+)$/);
    if (q) out.push({ id, q: q[1].replace(/^["']|["']$/g, "") });
    const p = line.match(/^ {6}- "(.+)"$/);
    if (p) out.push({ id: `${id}~${++n}`, q: p[1].replace(/\\"/g, '"') });
  }
  return out;
}

describe("router on the golden set", () => {
  const items = golden();
  it("reads the whole set", () => expect(items.length).toBeGreaterThanOrEqual(100));
  it("sends every data question to the planner", () => {
    const routed = items.filter((i) => isPersonalSchedule(i.q)).map((i) => i.id);
    expect(routed.filter((id) => !ROUTED_ON_PURPOSE.test(id))).toEqual([]);
    expect(routed).toContain("refuse_forecast");
  });
});
