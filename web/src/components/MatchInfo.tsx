"use client";
// Match confidence with an explanation on hover, focus or tap: what the percentage measures and
// who accepted the match, with the reviewer's reason (from the review seed; English only).
// The panel is position: fixed so the scrollable table around it never clips it.
import { useEffect, useId, useRef, useState } from "react";
import { fill } from "@/i18n/fill";
import type { MatchReview } from "@/types/v1";

export type MatchStrings = {
  confidence: string;
  exact: string;
  similarity: string;
  exactInfo: string;
  acceptedBy: string;
  acceptedOn: string;
  reason: string;
  who: Record<"rules" | "llm" | "claude" | "owner", string>;
};

type Props = {
  confidence: number | null;
  review?: MatchReview | null;
  printed: string;
  matched: string;
  locale: string;
  t: MatchStrings;
};

export function MatchInfo({ confidence, review, printed, matched, locale, t }: Props) {
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const [at, setAt] = useState<{ x: number; y: number } | null>(null);
  const exact = confidence === null || confidence >= 1;
  const pct = Math.round((confidence ?? 1) * 100);

  const open = () => {
    const r = button.current?.getBoundingClientRect();
    if (!r) return;
    const width = Math.min(320, window.innerWidth - 16);
    const rtl = document.documentElement.dir === "rtl";
    const x = rtl ? Math.max(8, r.right - width) : Math.min(r.left, window.innerWidth - width - 8);
    setAt({ x: Math.max(8, x), y: r.bottom + 4 });
  };
  const close = () => setAt(null);

  useEffect(() => {
    if (!at) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [at]);

  const who = review?.reviewed_by ? t.who[review.reviewed_by] : null;
  return (
    <span className="relative inline-block" onMouseEnter={open} onMouseLeave={close}>
      <button
        ref={button}
        type="button"
        className="text-xs text-muted underline decoration-dotted underline-offset-2 cursor-help"
        aria-describedby={at ? id : undefined}
        aria-expanded={at !== null}
        onFocus={open}
        onBlur={close}
        onClick={open /* a click also focuses: never toggle, or the tap would close it again */}
      >
        {exact ? t.exact : fill(t.confidence, { pct }, locale)}
      </button>
      {at && (
        <span
          id={id}
          role="tooltip"
          style={{ position: "fixed", left: at.x, top: at.y, width: 320, maxWidth: "calc(100vw - 16px)" }}
          className="z-50 block space-y-1 rounded border border-line bg-surface p-3 text-xs text-ink shadow-lg text-start"
        >
          <span className="block">
            {exact
              ? t.exactInfo
              : fill(t.similarity, { pct, printed, matched }, locale)}
          </span>
          {who && (
            <span className="block">
              {review?.reviewed_on
                ? fill(t.acceptedOn, { who, date: review.reviewed_on }, locale)
                : fill(t.acceptedBy, { who }, locale)}
            </span>
          )}
          {review?.reason && (
            <span className="block">
              {t.reason}{" "}
              <span lang="en" dir="ltr">
                {review.reason}
              </span>
            </span>
          )}
        </span>
      )}
    </span>
  );
}
