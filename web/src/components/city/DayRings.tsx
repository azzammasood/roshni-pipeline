"use client";
// Share of the day: one ring per fiscal year (oldest inside, latest outside); each arc is the
// share of a 24-hour day the company reported as load shedding, starting at midnight (top) and
// running clockwise. Hovering a ring names its year in the centre. Decorative twin of the table
// on the same page, so the drawing itself is hidden from assistive technology.
import { useState } from "react";
import { num } from "@/lib/format";

const SIZE = 300;
const C = SIZE / 2;

function arc(r: number, frac: number) {
  if (frac <= 0) return "";
  if (frac >= 1) return `M${C} ${C - r}A${r} ${r} 0 1 1 ${C - 0.01} ${C - r}`;
  const a = frac * 2 * Math.PI;
  const x = C + r * Math.sin(a);
  const y = C - r * Math.cos(a);
  return `M${C} ${C - r}A${r} ${r} 0 ${frac > 0.5 ? 1 : 0} 1 ${x} ${y}`;
}

export function DayRings({
  rings,
  locale,
  t,
}: {
  rings: { year: string; hours: number }[];
  locale: string;
  t: { center: string; fy: string; hours: string };
}) {
  const [at, setAt] = useState<number | null>(null);
  const show = at ?? rings.length - 1;
  const inner = 52;
  const outer = C - 18;
  const gap = 2;
  const band = (outer - inner) / Math.max(rings.length, 1);
  const width = Math.max(band - gap, 2);
  const cur = rings[show];
  return (
    <div className="mx-auto w-full max-w-[20rem]">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="w-full" aria-hidden="true" onPointerLeave={() => setAt(null)}>
        {[0, 6, 12, 18].map((h) => {
          const a = (h / 24) * 2 * Math.PI;
          return (
            <text
              key={h}
              x={C + (C - 6) * Math.sin(a)}
              y={C - (C - 6) * Math.cos(a)}
              textAnchor="middle"
              dy="0.35em"
              className="fill-muted chart-tick"
            >
              {String(h).padStart(2, "0")}
            </text>
          );
        })}
        {rings.map((r, i) => {
          const radius = inner + i * band + width / 2;
          const on = i === show;
          return (
            <g key={r.year} onPointerEnter={() => setAt(i)} className="cursor-default">
              <circle cx={C} cy={C} r={radius} fill="none" className="stroke-line" strokeWidth={width} opacity={0.3} />
              <path
                d={arc(radius, r.hours / 24)}
                fill="none"
                className={on ? "stroke-accent" : "stroke-dark"}
                strokeWidth={width}
                strokeLinecap="butt"
                opacity={on ? 1 : 0.35 + (0.45 * i) / Math.max(rings.length - 1, 1)}
              />
              {/* wide invisible hit ring */}
              <circle cx={C} cy={C} r={radius} fill="none" stroke="transparent" strokeWidth={band} />
            </g>
          );
        })}
        {cur && (
          <>
            <text x={C} y={C - 10} textAnchor="middle" className="fill-ink chart-big">
              {num(cur.hours, locale)}
            </text>
            <text x={C} y={C + 10} textAnchor="middle" className="fill-muted chart-tick">
              {t.center}
            </text>
            <text x={C} y={C + 26} textAnchor="middle" className="fill-muted chart-tick">
              {t.fy} {cur.year}
            </text>
          </>
        )}
      </svg>
    </div>
  );
}
