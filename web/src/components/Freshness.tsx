"use client";
// Data freshness in the masthead: how long ago the daily publish run last updated the data,
// measured in the viewer's browser (the static HTML cannot know "now"). The pipeline runs once a
// day, so past 30 hours the badge says the data may be out of date. Text, never colour alone.
import { useEffect, useState } from "react";
import { fill } from "@/i18n/fill";

const STALE_HOURS = 30;

export function Freshness({
  iso,
  locale,
  t,
}: {
  iso: string;
  locale: string;
  t: { fresh: string; stale: string; minutes: string; hours: string; days: string };
}) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    const tick = () => setNow(Date.now());
    tick();
    const id = setInterval(tick, 60_000);
    return () => clearInterval(id);
  }, []);
  if (now === null) return null;
  const minutes = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
  const ago =
    minutes < 90
      ? fill(t.minutes, { n: minutes }, locale)
      : minutes < 48 * 60
        ? fill(t.hours, { n: Math.round(minutes / 60) }, locale)
        : fill(t.days, { n: Math.round(minutes / 1440) }, locale);
  const stale = minutes > STALE_HOURS * 60;
  return (
    <span className={`freshness ${stale ? "is-stale" : ""}`}>
      <span className="freshness-dot" aria-hidden="true" />
      {fill(stale ? t.stale : t.fresh, { ago }, locale)}
    </span>
  );
}
