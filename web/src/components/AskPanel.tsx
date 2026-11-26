"use client";
// Ask Roshni: a question in, an answer whose numbers come from a query the browser ran on the
// published data. The Worker (worker/) plans and narrates; lib/ask/session.ts does the rest.
import { useEffect, useRef, useState } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/fill";
import { ASK_URL, quota, workerApi } from "@/lib/ask/api";
import { openDb } from "@/lib/ask/duckdb";
import { type Answer, type Remaining, type Step, askQuestion } from "@/lib/ask/session";
import { num } from "@/lib/format";
import { ScrollRegion } from "@/components/ScrollRegion";

// From the golden set (config/ask_golden.yml): each is known to have an answer in the data.
const EXAMPLES = [
  "Which K-Electric IBC area has the most listed feeders?",
  "How many listed K-Electric feeders are scheduled for six hours a day, and how many for twelve?",
  "Show K-Electric's NEPRA-reported load-shedding hours per day for every fiscal year.",
  "What is the most common purpose given for IESCO maintenance windows?",
];

type T = Dictionary["ask"];

export function AskPanel({ locale, t }: { locale: string; t: T }) {
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<Step | "load" | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [remaining, setRemaining] = useState<Remaining | null>(null);
  const [loadError, setLoadError] = useState(false);
  const result = useRef<HTMLDivElement>(null);
  const n = (v: number) => num(v, locale);

  useEffect(() => {
    if (!ASK_URL) return;
    void quota().then((q) => q.remaining && setRemaining(q.remaining));
  }, []);

  if (!ASK_URL) return <p className="text-lg">{t.off}</p>;

  async function submit(q: string) {
    const text = q.trim();
    if (!text || busy) return;
    setBusy(true);
    setAnswer(null);
    setLoadError(false);
    try {
      setStep("load");
      const opened = await openDb();
      const a = await askQuestion(text, { api: workerApi, db: opened.db, ctx: opened.ctx, serialize: opened.serialize, onStep: setStep });
      setAnswer(a);
      if (a.remaining) setRemaining(a.remaining);
    } catch (e) {
      console.error("Ask Roshni could not load the query engine:", e);
      setLoadError(true);
    } finally {
      setBusy(false);
      setStep(null);
      requestAnimationFrame(() => result.current?.focus());
    }
  }

  const stepText: Record<Step | "load", string> = {
    load: t.stepLoad, plan: t.stepPlan, check: t.stepCheck, run: t.stepRun, replan: t.stepReplan, narrate: t.stepNarrate, guard: t.stepPlan,
  };

  return (
    <div className="space-y-8">
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          void submit(question);
        }}
      >
        <label htmlFor="ask-q" className="block font-semibold">
          {t.label}
        </label>
        <textarea
          id="ask-q"
          className="field w-full text-lg"
          rows={3}
          maxLength={500}
          dir="auto"
          value={question}
          placeholder={t.placeholder}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void submit(question);
            }
          }}
        />
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <button type="submit" disabled={busy || !question.trim()} className="chip px-4 py-1.5 bg-ink text-bg font-semibold disabled:opacity-50">
            {busy ? t.asking : t.ask}
          </button>
          {remaining && (
            <p className="text-sm text-muted">
              {fill(t.remaining, { v: n(remaining.visitor_today), s: n(remaining.site_today) }, locale)}
            </p>
          )}
        </div>
        <p className="text-sm text-muted">{t.englishOnly}</p>
      </form>

      <section aria-labelledby="ask-examples" className="space-y-2">
        <h2 id="ask-examples" className="text-sm font-semibold">
          {t.examplesTitle}
        </h2>
        <ul className="flex flex-wrap gap-2" lang="en" dir="ltr">
          {EXAMPLES.map((q) => (
            <li key={q}>
              <button
                type="button"
                disabled={busy}
                className="chip px-2 py-1 text-start text-sm hover:bg-surface disabled:opacity-50"
                onClick={() => {
                  setQuestion(q);
                  void submit(q);
                }}
              >
                {q}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <div aria-live="polite" className="min-h-6">
        {busy && step && <p className="text-sm text-muted">{stepText[step]}…</p>}
      </div>

      <div ref={result} tabIndex={-1} className="outline-none">
        {loadError && <p className="mark">{t.loadError}</p>}
        {answer && <AnswerView a={answer} t={t} locale={locale} />}
      </div>
    </div>
  );
}

function AnswerView({ a, t, locale }: { a: Answer; t: T; locale: string }) {
  const n = (v: number) => num(v, locale);
  const minutes = (s?: number) => n(Math.max(1, Math.ceil((s ?? 60) / 60)));
  if (a.status !== "answered") {
    const msg =
      a.status === "refused"
        ? t.refused
        : a.status === "blocked"
          ? t.blocked
          : a.status === "unavailable"
            ? t.unavailable
            : a.status === "capped"
              ? a.reason === "visitor_minute"
                ? fill(t.cappedMinute, { m: minutes(a.retry_after_s) }, locale)
                : a.reason === "site_minute"
                  ? fill(t.cappedBusy, { m: minutes(a.retry_after_s) }, locale)
                  : a.reason === "visitor_day"
                    ? t.cappedDay
                    : t.cappedSite
              : t.failed;
    const why = a.status === "refused" || a.status === "failed" ? a.reason : "";
    return (
      <section aria-labelledby="ask-answer" className="rule pt-4 space-y-2">
        <h2 id="ask-answer" className="headline text-3xl">
          {t.answerTitle}
        </h2>
        <p className="text-lg">{msg}</p>
        {why && (
          <p className="text-sm text-muted" lang="en" dir="ltr">
            {why}
          </p>
        )}
        {a.sql && <SqlDetails a={a} t={t} locale={locale} />}
      </section>
    );
  }
  return (
    <section aria-labelledby="ask-answer" className="rule pt-4 space-y-4">
      <h2 id="ask-answer" className="headline text-3xl">
        {t.answerTitle}
      </h2>
      <p className="text-xl max-w-prose" lang="en" dir="ltr">
        {a.answer}
      </p>
      {!a.narrated && a.n > 0 && <p className="text-sm text-muted">{t.templateNote}</p>}
      {a.columns.length > 0 && a.n > 0 && (
        <ScrollRegion label={t.tableTitle} dir="ltr">
          <table className="data" lang="en">
            <thead>
              <tr>
                {a.columns.map((c) => (
                  <th key={c} scope="col" className="font-mono text-xs">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {a.rows.map((r, i) => (
                <tr key={i}>
                  {r.map((v, j) => (
                    <td key={j} className="tabular-nums">
                      {v}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      )}
      <div className="space-y-1 text-sm">
        <h3 className="font-semibold">{t.caveatsTitle}</h3>
        <ul className="list-disc ps-5 space-y-1">
          <li>{t.notMeasured}</li>
          {a.caveats.map((c) => (
            <li key={c} lang="en" dir="ltr">
              {c}
            </li>
          ))}
          <li>{fill(a.truncated ? t.rowsCapped : t.rows, { n: n(a.n) }, locale)}</li>
        </ul>
      </div>
      <SqlDetails a={a} t={t} locale={locale} />
    </section>
  );
}

function SqlDetails({ a, t, locale }: { a: Answer; t: T; locale: string }) {
  const tokens = a.attempts.reduce((s, x) => s + x.tokens, 0);
  const models = [...new Set(a.models)];
  return (
    <details className="text-sm">
      <summary className="link cursor-pointer">{t.howThis}</summary>
      <div className="mt-2 space-y-2">
        <pre className="font-mono text-xs whitespace-pre-wrap break-words border border-line p-3" dir="ltr" lang="en">
          {a.sql}
        </pre>
        {models.length > 0 && (
          <p>
            {fill(t.writtenBy, { m: models.join(", "), t: num(tokens, locale) }, locale)}
          </p>
        )}
      </div>
    </details>
  );
}
