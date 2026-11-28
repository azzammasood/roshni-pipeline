// Ask Roshni in a real browser: prepared answers open without the Worker, a personal question
// goes to the schedule engine, the equity page's link opens its prepared answer, and the page
// never scrolls sideways on a phone. The Worker (NEXT_PUBLIC_ASK_URL=http://ask.invalid in CI)
// is mocked; every call to /v1/ask is counted and must stay at zero here.
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const Q = "Which K-Electric IBC area has the most listed feeders?";
const PREPARED = {
  generated_at: "2026-11-28T03:00:00+00:00",
  built_at: "2026-11-28 08:00 PKT",
  items: [
    {
      id: "ibc-most-feeders", tag: "K-Electric", question: Q,
      answer: "IBC - Korangi has the most listed feeders, with 41.", narrated: true, model: "groq/test",
      sql: "select ibc, count(*) as feeders from dim_feeder group by 1 order by 2 desc limit 3",
      columns: ["ibc", "feeders"], rows: [["IBC - Korangi", "41"], ["IBC - Landhi", "33"], ["IBC - Malir", "20"]],
      truncated: false, tables: ["dim_feeder"], caveats: ["Among listed feeders only."], tokens: 0,
    },
  ],
};

async function mock(page: Page) {
  const calls = { ask: 0 };
  await page.route("http://ask.invalid/**", (route) => {
    const p = new URL(route.request().url()).pathname;
    if (p === "/v1/ask") calls.ask++;
    if (p === "/v1/quota") return route.fulfill({ json: { status: "ok", remaining: { visitor_today: 10, site_today: 150 } } });
    return route.fulfill({ status: 503, json: { status: "error" } });
  });
  await page.route("**/data/v1/ask/prepared.json", (route) => route.fulfill({ json: PREPARED }));
  return calls;
}

test("an example opens its prepared answer without the Worker", async ({ page }) => {
  const calls = await mock(page);
  await page.goto("/roshni-site/en/ask/");
  await page.getByRole("button", { name: Q }).click();
  await expect(page.locator(".ask-answer-text")).toContainText("IBC - Korangi");
  await expect(page.locator(".ask-chart li")).toHaveCount(3);
  await expect(page.locator(".ask-prepared")).toBeVisible();
  expect(calls.ask).toBe(0);
});

test("a personal question goes to the schedule engine", async ({ page }) => {
  const calls = await mock(page);
  await page.goto("/roshni-site/en/ask/");
  await page.locator("#ask-q").fill("Will I get load shedding today?");
  await page.locator("#ask-q").press("Enter");
  await expect(page.locator(".ask-mine")).toContainText("schedule engine");
  await expect(page.getByRole("heading", { name: "Find your feeder" })).toBeVisible();
  expect(calls.ask).toBe(0);
});

test("the equity page's link opens the prepared answer", async ({ page }) => {
  await mock(page);
  await page.goto("/roshni-site/en/ask/?p=ibc-most-feeders");
  await expect(page.locator(".ask-answer-text")).toContainText("IBC - Korangi");
});

test("no sideways scrolling on a phone", async ({ page }) => {
  await mock(page);
  await page.setViewportSize({ width: 375, height: 812 });
  for (const p of ["/roshni-site/en/ask/", "/roshni-site/ur/ask/", "/roshni-site/en/architecture/"]) {
    await page.goto(p);
    const [sw, iw] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
    expect(sw, p).toBeLessThanOrEqual(iw);
  }
});

// Accessibility (axe, WCAG 2 A and AA) on the AI pages with their new parts open: a prepared
// answer with its chart, trace and vote, the Urdu answer, the diagram and lanes, /health/.

for (const theme of ["light", "dark"] as const) {
  for (const [name, path, width] of [
    ["ask with answer", "/roshni-site/en/ask/?p=ibc-most-feeders", 1200],
    ["ask with answer, phone", "/roshni-site/en/ask/?p=ibc-most-feeders", 375],
    ["Urdu ask with answer", "/roshni-site/ur/ask/?p=ibc-most-feeders", 375],
    ["architecture", "/roshni-site/en/architecture/", 1200],
    ["health", "/roshni-site/en/health/", 375],
  ] as const) {
    test(`axe: ${name}, ${theme}`, async ({ page }) => {
      await mock(page);
      // As on every page after the first of a visit: the opening animation (decorative,
      // aria-hidden, 3 s) is skipped, so axe does not measure text while it fades in.
      await page.addInitScript((t) => {
        localStorage.setItem("roshni:theme", t);
        sessionStorage.setItem("roshni:intro", "1");
      }, theme);
      await page.setViewportSize({ width, height: 900 });
      await page.goto(path);
      if (path.includes("?p=")) await expect(page.locator(".ask-answer-text")).toBeVisible();
      const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
      expect(r.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).slice(0, 3).join(", ")}`)).toEqual([]);
    });
  }
}
