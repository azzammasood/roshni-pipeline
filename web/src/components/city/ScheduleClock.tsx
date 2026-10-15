"use client";
// A published schedule as a 24-hour clock: each spoke is one hour, its length the share of the
// area's feeders scheduled dark in that hour; under it, the same share per grid (IESCO) or IBC
// (K-Electric) as an hour-by-hour matrix in one hue. IESCO publishes one schedule per interruption
// level and never says which is in force, so the viewer picks the level. Schedules, not
// measurements.
import { useState } from "react";
import { fill } from "@/i18n/fill";
import { num } from "@/lib/format";
import { ScrollRegion } from "@/components/ScrollRegion";

export type ClockData = {
  feeders: number;
  avgHours: number;
  share: number[]; // 24 values, 0..1
  dark: number[]; // feeders dark in each hour
  rows: { name: string; feeders: number; share: number[] }[];
};

export type ClockStrings = {
  circle: string;
  level: string;
  levelChip: string;
  center: string;
  tip: string;
  matrix: string;
  rowHead: string;
  feeders: string;
  scale: string;
};

const SIZE = 300;
const C = SIZE / 2;
const pad = (h: number) => String(h % 24).padStart(2, "0");

export function ScheduleClock({
  circles,
  levels,
  data,
  initial,
  locale,
  t,
}: {
  circles?: { key: string; label: string }[];
  levels?: number[];
  data: Record<string, ClockData>;
  initial: { circle?: string; level?: number };
  locale: string;
  t: ClockStrings;
}) {
  const [circle, setCircle] = useState(initial.circle ?? "");
  const [level, setLevel] = useState<number | undefined>(initial.level);
  const [hour, setHour] = useState<number | null>(null);
  const key = [circle, level ?? ""].join("|");
  const d = data[key];
  if (!d) return null;
  const n = (v: number) => num(v, locale);
  const pct = (v: number) => num(Math.round(v * 100), locale);
  const inner = 74;
  const outer = C - 22;
  const spoke = (h: number) => {
    const a0 = (h / 24) * 2 * Math.PI + 0.02;
    const a1 = ((h + 1) / 24) * 2 * Math.PI - 0.02;
    const r1 = inner + d.share[h] * (outer - inner);
    const p = (r: number, a: number) => `${C + r * Math.sin(a)} ${C - r * Math.cos(a)}`;
    return `M${p(inner, a0)}L${p(r1, a0)}A${r1} ${r1} 0 0 1 ${p(r1, a1)}L${p(inner, a1)}A${inner} ${inner} 0 0 0 ${p(inner, a0)}Z`;
  };
  const tip = (h: number) =>
    fill(t.tip, { from: `${pad(h)}:00`, to: `${pad(h + 1)}:00`, pct: pct(d.share[h]), k: n(d.dark[h]), n: n(d.feeders) }, locale);

  return (
    <div className="space-y-4">
      {(circles || levels) && (
        <div className="flex flex-wrap gap-x-6 gap-y-3">
          {circles && (
            <div role="group" aria-label={t.circle} className="space-y-1">
              <p className="kicker" aria-hidden="true">{t.circle}</p>
              <div className="flex flex-wrap gap-1.5">
                {circles.map((c) => (
                  <button
                    key={c.key}
                    type="button"
                    aria-pressed={circle === c.key}
                    onClick={() => setCircle(c.key)}
                    className={`chip px-2 py-0.5 ${circle === c.key ? "bg-ink text-bg" : "hover:bg-surface"}`}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
          )}
          {levels && (
            <div role="group" aria-label={t.level} className="space-y-1">
              <p className="kicker" aria-hidden="true">{t.level}</p>
              <div className="flex flex-wrap gap-1.5">
                {levels.map((l) => (
                  <button
                    key={l}
                    type="button"
                    aria-pressed={level === l}
                    onClick={() => setLevel(l)}
                    className={`chip px-2 py-0.5 ${level === l ? "bg-ink text-bg" : "hover:bg-surface"}`}
                  >
                    {fill(t.levelChip, { n: l }, locale)}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[20rem_minmax(0,1fr)] items-start">
        <div className="mx-auto w-full max-w-[20rem]">
          <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="w-full clock-turn" key={key} aria-hidden="true" onPointerLeave={() => setHour(null)}>
            {[0.5, 1].map((g) => (
              <g key={g}>
                <circle cx={C} cy={C} r={inner + g * (outer - inner)} fill="none" className="stroke-line" strokeWidth={1} />
                <text x={C + 3} y={C - inner - g * (outer - inner) + 9} className="fill-muted chart-tick">
                  {pct(g)}%
                </text>
              </g>
            ))}
            <circle cx={C} cy={C} r={inner} fill="none" className="stroke-line" strokeWidth={1} />
            {[0, 6, 12, 18].map((h) => {
              const a = (h / 24) * 2 * Math.PI;
              return (
                <text key={h} x={C + (C - 7) * Math.sin(a)} y={C - (C - 7) * Math.cos(a)} textAnchor="middle" dy="0.35em" className="fill-muted chart-tick">
                  {pad(h)}
                </text>
              );
            })}
            {d.share.map((_, h) => (
              <path
                key={h}
                d={spoke(h)}
                className={hour === h ? "fill-accent" : "fill-dark"}
                opacity={hour === null || hour === h ? 1 : 0.45}
                onPointerEnter={() => setHour(h)}
              />
            ))}
            <text x={C} y={C - 4} textAnchor="middle" className="fill-ink chart-big">
              {n(d.avgHours)}
            </text>
            <foreignObject x={C - inner + 12} y={C + 6} width={2 * inner - 24} height={34}>
              <p className="text-center text-[10px] leading-tight text-muted">{t.center}</p>
            </foreignObject>
          </svg>
          <p className="min-h-[2.5rem] text-center text-sm" aria-live="polite">
            {hour !== null ? tip(hour) : fill(t.feeders, { n: n(d.feeders) }, locale)}
          </p>
        </div>

        <div className="min-w-0 space-y-2">
          <ScrollRegion label={t.matrix}>
            <table className="hour-matrix">
              <caption className="sr-only">{t.matrix}</caption>
              <thead>
                <tr>
                  <th scope="col" className="sticky start-0 bg-bg z-[1] text-start">{t.rowHead}</th>
                  {Array.from({ length: 24 }, (_, h) => (
                    <th key={h} scope="col" className={hour === h ? "is-hour" : undefined}>
                      {h % 3 === 0 ? pad(h) : <span className="sr-only">{pad(h)}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {d.rows.map((r) => (
                  <tr key={r.name}>
                    <th scope="row" className="sticky start-0 bg-bg z-[1] text-start font-normal">
                      <bdi>{r.name}</bdi> <span className="text-muted">({n(r.feeders)})</span>
                    </th>
                    {r.share.map((s, h) => (
                      <td
                        key={h}
                        title={`${pad(h)}:00 · ${pct(s)}%`}
                        className={hour === h ? "is-hour" : undefined}
                        onPointerEnter={() => setHour(h)}
                      >
                        <span className="hour-dot" style={{ opacity: s === 0 ? 0 : 0.15 + 0.85 * s }} />
                        <span className="sr-only">{pct(s)}%</span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
            <span>0%</span>
            <span className="hour-scale" aria-hidden="true" />
            <span>100%</span>
            <span>· {t.scale}</span>
          </p>
        </div>
      </div>
    </div>
  );
}
