"use client";
// Live Ask Roshni usage on /health/: counts the Worker keeps per Pakistan day (lib/ask/stats.ts).
// Loaded in the browser, so it is current even though the page itself is built once a day.
import { useEffect, useState } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/fill";
import { ScrollRegion } from "@/components/ScrollRegion";
import { type Stats, fetchStats, quantileBucket, sum, totals } from "@/lib/ask/stats";
import { num } from "@/lib/format";

const DAYS_SHOWN = 14;

export function AskUsage({ locale, t }: { locale: string; t: Dictionary["health"] }) {
  const [stats, setStats] = useState<Stats | null | undefined>(undefined);
  useEffect(() => {
    void fetchStats().then(setStats);
  }, []);
  const n = (v: number) => num(v, locale);

  if (stats === undefined) return <p className="text-muted">{t.usageLoading}</p>;
  if (stats === null) return <p className="text-muted">{t.usageOff}</p>;

  const bucketText = (i: number | null) =>
    i === null
      ? "–"
      : i < stats.buckets_s.length
        ? fill(t.upTo, { s: n(stats.buckets_s[i]) }, locale)
        : fill(t.over, { s: n(stats.buckets_s.at(-1) ?? 0) }, locale);
  const all = totals(stats.days);
  const tiles: [string, string][] = [
    [n(all.questions), t.usageQuestions],
    [n(all.visitors), t.usageVisitors],
    [n(all.refused), t.usageRefused],
    [n(all.blocked), t.usageBlocked],
    [n(all.corrected), t.usageCorrected],
    [n(all.capped), t.usageCapped],
    [bucketText(all.medianBucket), t.usageMedian],
    [all.up + all.down ? `${n(all.up)} / ${n(all.down)}` : "–", t.usageVotes],
  ];
  const reasons = Object.entries(all.reasons).filter(([, v]) => v > 0);
  const recent = stats.days.slice(-DAYS_SHOWN).reverse();

  return (
    <div className="space-y-4">
      <p className="text-sm max-w-prose">
        {fill(t.usageNote, { d: n(stats.window_days) }, locale)}{" "}
        {fill(
          t.usageCaps,
          {
            vd: n(stats.caps.visitor_per_day),
            sd: n(stats.caps.site_per_day),
            tk: n(stats.caps.site_tokens_per_day),
          },
          locale,
        )}
      </p>
      <dl className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-4">
        {tiles.map(([value, label]) => (
          <div key={label} className="border-t border-line pt-2 flex flex-col-reverse">
            <dt className="text-sm">{label}</dt>
            <dd className="headline text-3xl tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      {reasons.length > 0 && (
        <p className="text-sm">
          {t.usageDownWhy}{" "}
          {reasons.map(([k, v]) => `${t.voteReasons[k as keyof typeof t.voteReasons] ?? k}: ${n(v)}`).join(" · ")}
        </p>
      )}
      {recent.length === 0 ? (
        <p className="text-sm">{t.usageNone}</p>
      ) : (
        <ScrollRegion label={t.usageTitle}>
          <table className="data">
            <thead>
              <tr>
                <th scope="col">{t.date}</th>
                <th scope="col">{t.colQuestions}</th>
                <th scope="col">{t.colVisitors}</th>
                <th scope="col">{t.colRefused}</th>
                <th scope="col">{t.colBlocked}</th>
                <th scope="col">{t.colCorrected}</th>
                <th scope="col">{t.colCapped}</th>
                <th scope="col">{t.evalTokens}</th>
                <th scope="col">{t.colMedian}</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((d) => (
                <tr key={d.date}>
                  <th scope="row" className="font-normal tabular-nums" dir="ltr">
                    {d.date}
                  </th>
                  <td className="tabular-nums">{n(d.questions)}</td>
                  <td className="tabular-nums">{n(d.visitors)}</td>
                  <td className="tabular-nums">{n(d.refused)}</td>
                  <td className="tabular-nums">{n(d.blocked)}</td>
                  <td className="tabular-nums">{n(d.replans.guard + d.replans.error + d.replans.empty)}</td>
                  <td className="tabular-nums">{n(sum(Object.values(d.capped)))}</td>
                  <td className="tabular-nums">{n(d.tokens)}</td>
                  <td className="tabular-nums">{bucketText(quantileBucket(d.plan_latency, 0.5))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      )}
    </div>
  );
}
