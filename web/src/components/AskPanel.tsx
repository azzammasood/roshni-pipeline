"use client";
// Ask Roshni: a question in, an answer whose numbers come from a query the browser ran on the
// published data. The Worker (worker/) plans and narrates; lib/ask/session.ts does the rest.
//
// Layout (owner review 2026-11-26): a night-sky console holds the question; under it a power line
// runs through the five stations of an answer (engine, query, check, run, answer) and a spark
// travels to the one at work. The answer switches on directly under the console and is scrolled
// into view; the example questions sit below it. Motion is CSS only and stops under
// prefers-reduced-motion (motion.css, "Ask Roshni").
// The query engine (about 8 MB compressed) starts loading before the first question: when the
// visitor focuses the box or points at the console or an example, or once the page is idle
// (not on data-saver connections). A lamp in the console says when it is ready.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/fill";
import { ASK_URL, quota, workerApi } from "@/lib/ask/api";
import { openDb } from "@/lib/ask/duckdb";
import { isPersonalSchedule } from "@/lib/ask/intent";
import { type Prepared, loadPrepared, toAnswer } from "@/lib/ask/prepared";
import { SITE_KEY, turnstileToken, warmTurnstile } from "@/lib/ask/turnstile";
import { type Answer, type Remaining, type Step, askQuestion } from "@/lib/ask/session";
import { num } from "@/lib/format";
import { AnswerChart, Feedback, Trace, VoiceButton, followUpLabel } from "@/components/AskExtras";
import { AskMySchedule } from "@/components/AskMySchedule";
import { BulbArt } from "@/components/Bulb";
import type { LeadStrings } from "@/components/PinnedFeeder";
import { ScrollRegion } from "@/components/ScrollRegion";

// From the golden set (config/ask_golden.yml): each is known to have an answer in the data.
// The first is the everyday question; it goes to the schedule engine (lib/ask/intent.ts).
const EXAMPLES: { tag: string; q: string }[] = [
  { tag: "Your feeder", q: "Will I get load shedding today?" },
  { tag: "K-Electric", q: "Which K-Electric IBC area has the most listed feeders?" },
  { tag: "K-Electric", q: "How many listed K-Electric feeders are scheduled for six hours a day, and how many for twelve?" },
  { tag: "NEPRA", q: "Show K-Electric's NEPRA-reported load-shedding hours per day for every fiscal year." },
  { tag: "IESCO", q: "What is the most common purpose given for IESCO maintenance windows?" },
];

type T = Dictionary["ask"];
type Phase = Step | "load";
type Station = "load" | "plan" | "check" | "run" | "narrate";
const STATIONS: Station[] = ["load", "plan", "check", "run", "narrate"];
const STATION_OF: Record<Phase, number> = { load: 0, guard: 1, plan: 1, replan: 1, check: 2, run: 3, narrate: 4 };

/** Where the line ended: index of the last station reached, and how. */
type Track = { at: number; state: "running" | "done" | "stopped"; replanned: boolean };

type Engine = "idle" | "warming" | "ready";

const saveData = () =>
  typeof navigator !== "undefined" && Boolean((navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData);

// One engine per page load (lib/ask/duckdb.ts), so its state lives beside it, not in React.
let engineState: Engine = "idle";
const engineListeners = new Set<(e: Engine) => void>();
const setEngineState = (e: Engine) => {
  engineState = e;
  engineListeners.forEach((l) => l(e));
};
function warm() {
  warmTurnstile();
  if (engineState !== "idle") return;
  setEngineState("warming");
  openDb().then(
    () => setEngineState("ready"),
    () => setEngineState("idle"),
  );
}

const reduceMotion = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function AskPanel({ locale, t, lt }: { locale: string; t: T; lt: LeadStrings }) {
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState<Phase | null>(null);
  const [track, setTrack] = useState<Track | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [mine, setMine] = useState(false);
  // A follow-up: the earlier answer's ticket (the Worker holds its question and plan, 10 min).
  const [previous, setPrevious] = useState<{ ticket: string; q: string } | null>(null);
  // Answers the publish job prepared this morning (examples, equity links, busy fallback).
  const [prepared, setPrepared] = useState<Prepared | null>(null);
  const [asked, setAsked] = useState("");
  const [remaining, setRemaining] = useState<Remaining | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [engine, setEngine] = useState<Engine>(engineState);
  const result = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const human = useRef<HTMLDivElement>(null);
  const n = (v: number) => num(v, locale);

  useEffect(() => {
    if (!ASK_URL) return;
    void quota().then((q) => q.remaining && setRemaining(q.remaining));
  }, []);

  useEffect(() => {
    void loadPrepared().then((p) => {
      setPrepared(p);
      // /ask/?p=<id>: open a prepared answer (the equity page's "Explain this" links).
      const id = new URLSearchParams(window.location.search).get("p");
      const item = id ? p?.items.find((i) => i.id === id) : undefined;
      if (item && p) {
        setQuestion(item.question);
        setAsked(item.question);
        setAnswer(toAnswer(item, p.built_at, locale));
        setTrack({ at: 4, state: "done", replanned: false });
        requestAnimationFrame(() => result.current?.scrollIntoView({ block: "start" }));
      }
    });
  }, [locale]);

  useEffect(() => {
    engineListeners.add(setEngine);
    return () => {
      engineListeners.delete(setEngine);
    };
  }, []);

  useEffect(() => {
    if (!ASK_URL || saveData()) return;
    const id = window.setTimeout(() => {
      const idle = (window as Window & { requestIdleCallback?: (cb: () => void) => number }).requestIdleCallback;
      if (idle) idle(() => warm());
      else warm();
    }, 2500);
    return () => window.clearTimeout(id);
  }, []);

  // The box grows with the question (typed or filled in from an example), up to a cap.
  useLayoutEffect(() => {
    const el = input.current;
    if (!el) return;
    el.style.height = "auto";
    // scrollHeight leaves out the border; without it a 1 px scrollbar shows
    el.style.height = `${el.scrollHeight + el.offsetHeight - el.clientHeight}px`;
  }, [question]);

  useEffect(() => {
    if (!busy) return;
    const start = performance.now();
    const id = window.setInterval(() => setElapsed((performance.now() - start) / 1000), 100);
    return () => window.clearInterval(id);
  }, [busy]);

  if (!ASK_URL) return <p className="text-lg">{t.off}</p>;

  function onStep(p: Phase) {
    setPhase(p);
    setTrack((tr) => ({ at: STATION_OF[p], state: "running", replanned: (tr?.replanned ?? false) || p === "replan" }));
  }

  function reveal() {
    requestAnimationFrame(() => {
      const el = result.current;
      if (!el) return;
      el.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "start" });
      el.focus({ preventScroll: true });
    });
  }

  /** The visitor's own feeder: answered by the schedule engine, no model, no quota. */
  function showMine(text: string) {
    setAnswer(null);
    setTrack(null);
    setLoadError(false);
    setAsked(text);
    setMine(true);
    reveal();
  }

  /** A question the publish job already answered today: shown at once, no question used. */
  function showPrepared(text: string): boolean {
    const item = prepared?.items.find((i) => i.question.toLowerCase() === text.toLowerCase());
    if (!item || !prepared || previous) return false;
    setMine(false);
    setLoadError(false);
    setAsked(item.question);
    setAnswer(toAnswer(item, prepared.built_at, locale));
    setTrack({ at: 4, state: "done", replanned: false });
    reveal();
    return true;
  }

  async function submit(q: string) {
    const text = q.trim();
    if (!text || busy) return;
    if (isPersonalSchedule(text)) return showMine(text);
    if (showPrepared(text)) return;
    setMine(false);
    setBusy(true);
    setAnswer(null);
    setAsked(text);
    setLoadError(false);
    setElapsed(0);
    const ready = engineState === "ready";
    setTrack({ at: ready ? 1 : 0, state: "running", replanned: false });
    try {
      if (!ready) onStep("load");
      if (engineState === "idle") setEngineState("warming");
      const [opened, token] = await Promise.all([
        openDb(),
        human.current ? turnstileToken(human.current, locale).catch(() => "") : Promise.resolve(null),
      ]);
      setEngineState("ready");
      const a = await askQuestion(text, {
        api: workerApi,
        db: opened.db,
        ctx: opened.ctx,
        serialize: opened.serialize,
        onStep,
        previous: previous?.ticket,
        lang: locale === "ur" ? "ur" : "en",
        turnstile: token,
      });
      setPrevious(null);
      setAnswer(a);
      if (a.remaining) setRemaining(a.remaining);
      setTrack((tr) => ({
        at: a.status === "answered" ? 4 : (tr?.at ?? 1),
        state: a.status === "answered" ? "done" : "stopped",
        replanned: tr?.replanned ?? false,
      }));
    } catch (e) {
      console.error("Ask Roshni could not load the query engine:", e);
      if (engineState !== "ready") setEngineState("idle");
      setLoadError(true);
      setTrack((tr) => ({ at: tr?.at ?? 0, state: "stopped", replanned: tr?.replanned ?? false }));
    } finally {
      setBusy(false);
      setPhase(null);
      reveal();
    }
  }

  const stepText: Record<Phase, string> = {
    load: t.stepLoad,
    guard: t.stepPlan,
    plan: t.stepPlan,
    check: t.stepCheck,
    run: t.stepRun,
    replan: t.stepReplan,
    narrate: t.stepNarrate,
  };
  const stationText: Record<Station, string> = {
    load: t.stationLoad,
    plan: t.stationPlan,
    check: t.stationCheck,
    run: t.stationRun,
    narrate: t.stationNarrate,
  };
  const lit = answer?.status === "answered";

  return (
    <div className="space-y-10">
      <div
        className={`ask-console${busy ? " is-busy" : ""}${lit ? " is-lit" : ""}`}
        onPointerEnter={warm}
        onFocusCapture={warm}
      >
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            void submit(question);
          }}
        >
          <div className="flex items-baseline justify-between gap-4 flex-wrap">
            <label htmlFor="ask-q" className="kicker">
              {t.label}
            </label>
            {remaining && (
              <p className="ask-meter" aria-live="polite">
                <span className="ask-meter-dots" aria-hidden="true">
                  {Array.from({ length: Math.min(10, remaining.visitor_today) }, (_, i) => (
                    <span key={i} />
                  ))}
                </span>
                {fill(t.remaining, { v: n(remaining.visitor_today) }, locale)}
              </p>
            )}
          </div>
          {previous && (
            <p className="ask-followup">
              <span>{followUpLabel(t, previous.q, locale)}</span>
              <button type="button" className="link" onClick={() => setPrevious(null)}>
                {t.followUpCancel}
              </button>
            </p>
          )}
          <div className="ask-input-row">
            <textarea
              ref={input}
              id="ask-q"
              className="ask-input"
              rows={2}
              maxLength={500}
              dir="auto"
              value={question}
              placeholder={previous ? t.followUpPlaceholder : t.placeholder}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void submit(question);
                }
              }}
            />
            <VoiceButton locale={locale} t={t} onText={(s) => setQuestion(s)} />
            <button type="submit" disabled={busy || !question.trim()} className="ask-switch">
              <svg viewBox="0 0 40 48" className="ask-switch-bulb" aria-hidden="true" focusable="false">
                <BulbArt />
              </svg>
              <span>{busy ? t.asking : t.ask}</span>
            </button>
          </div>
          {SITE_KEY && (
            <>
              <div ref={human} className="ask-human" />
              <p className="ask-hint">{t.turnstileNote}</p>
            </>
          )}
          <div className="ask-hint-row">
            <p className="ask-hint">{t.hintEnter}</p>
            <p className={`ask-engine is-${engine}`} aria-live="polite">
              <span className="ask-engine-lamp" aria-hidden="true" />
              {engine === "ready" ? t.engineReady : engine === "warming" ? t.engineWarming : t.engineIdle}
            </p>
          </div>
        </form>

        {track && (
          <div className="ask-line-wrap">
            <ol
              className={`ask-line is-${track.state}`}
              style={{ "--at": track.at } as React.CSSProperties}
              aria-hidden="true"
            >
              {STATIONS.map((s, i) => {
                const state =
                  i < track.at || (i === track.at && track.state === "done")
                    ? "done"
                    : i === track.at
                      ? track.state === "running"
                        ? "active"
                        : "stopped"
                      : "todo";
                return (
                  <li key={s} className={`ask-station is-${state}`}>
                    <span className="ask-lamp" />
                    <span className="ask-station-name">
                      {stationText[s]}
                      {s === "plan" && track.replanned && <span className="ask-retry"> ↻</span>}
                    </span>
                  </li>
                );
              })}
            </ol>
            <p className="ask-status" aria-live="polite">
              <span>{busy && phase ? `${stepText[phase]}…` : ""}</span>
              <span className="ask-clock" dir="ltr">
                {track && (busy || answer) ? fill(t.seconds, { s: n(Math.round(elapsed * 10) / 10) }, locale) : ""}
              </span>
            </p>
          </div>
        )}
      </div>

      <div ref={result} tabIndex={-1} className="outline-none scroll-mt-24">
        {busy && !answer && <AnswerSkeleton />}
        {loadError && <p className="mark">{t.loadError}</p>}
        {mine && (
          <>
            <p className="ask-asked mb-3" lang="en" dir="auto">
              {asked}
            </p>
            <AskMySchedule locale={locale} t={t} lt={lt} />
          </>
        )}
        {answer && (
          <AnswerView
            a={answer}
            asked={asked}
            t={t}
            locale={locale}
            onMine={() => showMine(asked)}
            prepared={prepared}
            onPrepared={(q) => {
              setQuestion(q);
              showPrepared(q);
            }}
            onFollowUp={() => {
              if (!answer.ticket) return;
              setPrevious({ ticket: answer.ticket, q: asked });
              setQuestion("");
              input.current?.focus({ preventScroll: true });
              input.current?.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "center" });
            }}
          />
        )}
      </div>

      <section aria-labelledby="ask-examples" className="space-y-3">
        <h2 id="ask-examples" className="kicker">
          {answer || mine ? t.askAnother : t.examplesTitle}
        </h2>
        <ul className="ask-examples" lang="en" dir="ltr">
          {EXAMPLES.map(({ tag, q }) => (
            <li key={q}>
              <button
                type="button"
                disabled={busy}
                className="ask-example"
                onPointerEnter={warm}
                onFocus={warm}
                onClick={() => {
                  setQuestion(q);
                  input.current?.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "center" });
                  void submit(q);
                }}
              >
                <span className="ask-example-tag">{tag}</span>
                <span>{q}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function AnswerSkeleton() {
  return (
    <div className="ask-answer space-y-3" aria-hidden="true">
      <div className="skeleton h-4 w-24" />
      <div className="skeleton h-8 w-full max-w-2xl" />
      <div className="skeleton h-8 w-2/3 max-w-xl" />
      <div className="skeleton h-24 w-full mt-4" />
    </div>
  );
}

function AnswerView({
  a,
  asked,
  t,
  locale,
  onMine,
  onFollowUp,
  prepared,
  onPrepared,
}: {
  a: Answer;
  asked: string;
  t: T;
  locale: string;
  onMine: () => void;
  onFollowUp: () => void;
  prepared: Prepared | null;
  onPrepared: (q: string) => void;
}) {
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
            : a.status === "challenge"
              ? t.challenge
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
      <section aria-labelledby="ask-answer" className="ask-answer is-off space-y-3">
        <p className="ask-asked" lang="en" dir="auto">
          {asked}
        </p>
        <h2 id="ask-answer" className="headline text-3xl sm:text-4xl">
          {msg}
        </h2>
        {why && (
          <p className="text-sm text-muted max-w-prose" lang="en" dir="ltr">
            {why}
          </p>
        )}
        {a.status !== "blocked" && (
          <p className="max-w-prose">
            {t.mineOffer}{" "}
            <button type="button" className="link font-semibold" onClick={onMine}>
              {t.mineButton}
            </button>
          </p>
        )}
        {(a.status === "unavailable" || a.status === "capped") && prepared && prepared.items.length > 0 && (
          <div className="space-y-2">
            <p className="max-w-prose">{t.busyPrepared}</p>
            <ul className="flex flex-wrap gap-2" lang="en" dir="ltr">
              {prepared.items.map((p) => (
                <li key={p.id}>
                  <button type="button" className="chip px-2 py-1 text-start" onClick={() => onPrepared(p.question)}>
                    {p.question}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {a.status === "refused" && <Feedback ticket={a.ticket} refused t={t} />}
        {a.sql && <SqlDetails a={a} t={t} locale={locale} />}
      </section>
    );
  }
  return (
    <section aria-labelledby="ask-answer" className="ask-answer is-on space-y-5">
      <p className="ask-asked" lang="en" dir="auto">
        {asked}
      </p>
      <h2 id="ask-answer" className="sr-only">
        {t.answerTitle}
      </h2>
      <p className="ask-answer-text headline" lang={a.lang ?? "en"} dir={a.lang === "ur" ? "rtl" : "ltr"}>
        <span className="ask-answer-mark">{a.answer}</span>
      </p>
      {a.follow_up && <p className="kicker">{t.followUpDone}</p>}
      {a.prepared !== undefined && (
        <p className="ask-prepared text-sm">
          {fill(t.preparedNote, { at: a.prepared || "–" }, locale)}
        </p>
      )}
      {!a.narrated && a.n > 0 && <p className="text-sm text-muted">{t.templateNote}</p>}
      <AnswerChart a={a} />
      {a.columns.length > 0 && a.n > 0 && (
        <ScrollRegion label={t.tableTitle} dir="ltr">
          <table className="data ask-table" lang="en">
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
                <tr key={i} style={{ "--i": Math.min(i, 12) } as React.CSSProperties}>
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
      <div className="ask-fine space-y-1 text-sm">
        <h3 className="kicker">{t.caveatsTitle}</h3>
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
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        {a.ticket && (
          <button type="button" className="ask-followup-btn" onClick={onFollowUp}>
            <span aria-hidden="true">↳</span> {t.followUpAsk}
          </button>
        )}
        <Feedback ticket={a.ticket} t={t} />
      </div>
      <SqlDetails a={a} t={t} locale={locale} />
    </section>
  );
}

function SqlDetails({ a, t, locale }: { a: Answer; t: T; locale: string }) {
  const tokens = a.attempts.reduce((s, x) => s + x.tokens, 0);
  const models = [...new Set(a.models)];
  return (
    <details className="ask-sql text-sm">
      <summary className="link cursor-pointer">{t.howThis}</summary>
      <div className="mt-2 space-y-2">
        <pre className="ask-sql-code" dir="ltr" lang="en">
          {a.sql}
        </pre>
        {models.length > 0 && <p>{fill(t.writtenBy, { m: models.join(", "), t: num(tokens, locale) }, locale)}</p>}
        <Trace a={a} t={t} locale={locale} />
      </div>
    </details>
  );
}
