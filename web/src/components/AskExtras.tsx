"use client";
// Pieces of an Ask Roshni answer that need no language model:
// - AnswerChart: a bar chart chosen by code from the result's shape (one label column and one
//   numeric column, at most 24 rows). The table stays the source of truth; the chart is aria-hidden.
// - Feedback: one up/down vote per answer, with a fixed reason for a down vote (counts only).
// - Trace: every step of the answer with its time, model and tokens (the "Show the query" panel).
// - VoiceButton: the browser's own speech recognition, English or Urdu; hidden where unsupported.
import { useRef, useState, useSyncExternalStore } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/fill";
import { feedback as sendFeedback } from "@/lib/ask/api";
import { chartOf } from "@/lib/ask/chart";
import type { Answer } from "@/lib/ask/session";
import { num } from "@/lib/format";

type T = Dictionary["ask"];

export function AnswerChart({ a }: { a: Answer }) {
  const c = chartOf(a.columns, a.rows);
  if (!c) return null;
  const max = Math.max(...c.bars.map((b) => Math.abs(b.value))) || 1;
  return (
    <figure className="ask-chart" aria-hidden="true" dir="ltr" lang="en">
      <figcaption className="ask-chart-cap">
        {c.value} <span>by</span> {c.label}
      </figcaption>
      <ol>
        {c.bars.map((b, i) => (
          <li key={`${b.label}-${i}`} style={{ "--w": `${(Math.abs(b.value) / max) * 100}%`, "--i": Math.min(i, 16) } as React.CSSProperties}>
            <span className="ask-chart-label">{b.label}</span>
            <span className="ask-chart-bar">
              <span />
            </span>
            <span className="ask-chart-value">{b.text}</span>
          </li>
        ))}
      </ol>
    </figure>
  );
}

const REASONS = ["wrong", "unclear", "slow"] as const;

export function Feedback({ ticket, refused, t }: { ticket?: string; refused?: boolean; t: T }) {
  const [state, setState] = useState<"open" | "why" | "sent" | "closed">("open");
  const [share, setShare] = useState(false);
  if (!ticket) return null;
  const send = async (vote: "up" | "down", reason?: string) => {
    setState("sent");
    const r = await sendFeedback(ticket, vote, reason, vote === "down" && share);
    if (r.status !== "recorded") setState("closed");
  };
  if (state === "sent") return <p className="ask-vote text-sm" aria-live="polite">{t.voteThanks}</p>;
  if (state === "closed") return <p className="ask-vote text-sm text-muted" aria-live="polite">{t.voteClosed}</p>;
  const reasons = refused ? (["refused_wrongly", "unclear"] as const) : REASONS;
  return (
    <div className="ask-vote flex flex-wrap items-center gap-2 text-sm" role="group" aria-label={t.voteLabel}>
      <span>{t.voteLabel}</span>
      {state === "open" ? (
        <>
          {!refused && (
            <button type="button" className="chip px-2 py-0.5" onClick={() => send("up")}>
              <span aria-hidden="true">👍</span> {t.voteUp}
            </button>
          )}
          <button type="button" className="chip px-2 py-0.5" onClick={() => setState("why")}>
            <span aria-hidden="true">👎</span> {t.voteDown}
          </button>
        </>
      ) : (
        <>
          {reasons.map((r) => (
            <button key={r} type="button" className="chip px-2 py-0.5" onClick={() => send("down", r)}>
              {t.voteReasons[r]}
            </button>
          ))}
          <label className="flex items-start gap-2 basis-full max-w-prose text-xs">
            <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} className="mt-0.5" />
            <span>{t.shareQuestion}</span>
          </label>
        </>
      )}
    </div>
  );
}

export function Trace({ a, t, locale }: { a: Answer; t: T; locale: string }) {
  const n = (v: number) => num(v, locale);
  const rows: { step: string; who: string; result: string; time: string; tokens: string }[] = [];
  if (a.guard_score !== undefined && a.guard_score !== null)
    rows.push({ step: t.traceScreen, who: "Llama Prompt Guard 2", result: `P(attack) = ${a.guard_score.toFixed(3)}`, time: "", tokens: "" });
  const model = (at: Answer["attempts"][number]) =>
    rows.push({
      step: at.stage === "narrate" ? t.traceNarrate : at.stage === "plan2" ? t.traceReplan : t.tracePlan,
      who: at.model,
      result: at.outcome,
      time: `${n(at.latency_s)} s`,
      tokens: n(at.tokens),
    });
  const browser = (e: Answer["trace"][number]) =>
    rows.push({
      step: e.step === "guard" ? t.traceGuard : e.step === "run" ? t.traceRun : t.traceRetry,
      who: e.step === "replan" ? "" : e.step === "guard" ? "SQL guard" : "DuckDB-WASM",
      result: `${e.ok ? "ok" : "stopped"}${e.detail ? `: ${e.detail}` : ""}`,
      time: e.step === "replan" ? "" : `${n(e.ms)} ms`,
      tokens: "",
    });
  // Order: first plan, the browser's checks up to a retry, the corrected plan, the rest, narration.
  const cut = a.trace.findIndex((e) => e.step === "replan");
  const first = cut < 0 ? a.trace : a.trace.slice(0, cut + 1);
  const second = cut < 0 ? [] : a.trace.slice(cut + 1);
  a.attempts.filter((x) => x.stage === "plan1").forEach(model);
  first.forEach(browser);
  a.attempts.filter((x) => x.stage === "plan2").forEach(model);
  second.forEach(browser);
  a.attempts.filter((x) => x.stage === "narrate").forEach(model);
  if (!rows.length) return null;
  return (
    <div className="space-y-1">
      <h4 className="kicker">{t.traceTitle}</h4>
      <ol className="ask-trace" dir="ltr" lang="en">
        {rows.map((r, i) => (
          <li key={i}>
            <span className="ask-trace-step">{r.step}</span>
            <span className="ask-trace-who">{r.who}</span>
            <span className="ask-trace-result">{r.result}</span>
            <span className="ask-trace-time">{r.time}</span>
            <span className="ask-trace-tokens">{r.tokens && `${r.tokens} tok`}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

type Recognition = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};

const noop = () => () => {};

const recognitionClass = () => {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
};

export function VoiceButton({ locale, t, onText }: { locale: string; t: T; onText: (s: string) => void }) {
  // Known only in the browser; the static HTML renders without the button.
  const supported = useSyncExternalStore(noop, () => recognitionClass() !== null, () => false);
  const [listening, setListening] = useState(false);
  const rec = useRef<Recognition | null>(null);
  if (!supported) return null;
  const toggle = () => {
    if (listening) return rec.current?.stop();
    const R = recognitionClass();
    if (!R) return;
    const r = new R();
    r.lang = locale === "ur" ? "ur-PK" : "en-PK";
    r.interimResults = false;
    r.maxAlternatives = 1;
    r.onresult = (e) => onText(Array.from(e.results, (x) => x[0].transcript).join(" ").trim());
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    rec.current = r;
    setListening(true);
    r.start();
  };
  return (
    <button
      type="button"
      className={`ask-mic${listening ? " is-on" : ""}`}
      onClick={toggle}
      aria-pressed={listening}
      title={t.voiceNote}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M5 11a7 7 0 0 0 14 0M12 18v3" fill="none" />
      </svg>
      <span>{listening ? t.voiceStop : t.voiceStart}</span>
    </button>
  );
}

export const followUpLabel = (t: T, q: string, locale: string) => fill(t.followUpTo, { q }, locale);
