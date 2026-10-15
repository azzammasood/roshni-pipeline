"use client";
// Year by year: hours a day each company reported to NEPRA. The city is the one emphasised line;
// the other companies are grey hairlines and their median a darker hairline (one axis, one unit).
// Hover or arrow keys move a crosshair; a table view carries the same numbers.
import { useEffect, useRef, useState } from "react";
import { num } from "@/lib/format";

export type YearLinesProps = {
  years: string[];
  city: { name: string; values: (number | null)[] };
  median: (number | null)[];
  others: (number | null)[][];
  ranks: ({ rank: number; of: number } | null)[];
  locale: string;
  t: {
    label: string;
    unit: string;
    median: string;
    others: string;
    rank: string;
    fy: string;
  };
};

const PAD = { top: 16, right: 56, bottom: 28, left: 34 };

export function YearLines({ years, city, median, others, ranks, locale, t }: YearLinesProps) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [at, setAt] = useState<number | null>(null);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(280, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const H = 260;
  const all = [...city.values, ...median, ...others.flat()].filter((v): v is number => v !== null);
  const max = Math.max(4, Math.ceil(Math.max(...all)));
  const step = max > 12 ? 4 : 2;
  const x = (i: number) => PAD.left + (i * (width - PAD.left - PAD.right)) / Math.max(years.length - 1, 1);
  const y = (v: number) => PAD.top + (1 - v / max) * (H - PAD.top - PAD.bottom);
  const line = (vals: (number | null)[]) =>
    vals
      .map((v, i) => (v === null ? null : `${x(i)} ${y(v)}`))
      .reduce<string>((d, p, i, arr) => (p === null ? d : `${d}${i === 0 || arr[i - 1] === null ? "M" : "L"}${p}`), "");
  const n = (v: number) => num(v, locale);
  const lastIdx = city.values.findLastIndex((v) => v !== null);
  const pick = (clientX: number) => {
    const r = box.current!.getBoundingClientRect();
    const i = Math.round(((clientX - r.left - PAD.left) / (width - PAD.left - PAD.right)) * (years.length - 1));
    setAt(Math.min(Math.max(i, 0), years.length - 1));
  };
  const tick = (i: number) => years.length <= 8 || i % 2 === (years.length - 1) % 2;

  return (
    <div ref={box} className="relative select-none" dir="ltr">
      <svg
        width={width}
        height={H}
        role="img"
        aria-label={t.label}
        tabIndex={0}
        className="block max-w-full focus-visible:outline-2"
        onPointerMove={(e) => pick(e.clientX)}
        onPointerLeave={() => setAt(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") setAt((a) => Math.min((a ?? -1) + 1, years.length - 1));
          if (e.key === "ArrowLeft") setAt((a) => Math.max((a ?? years.length) - 1, 0));
          if (e.key === "Escape") setAt(null);
        }}
        onBlur={() => setAt(null)}
      >
        {Array.from({ length: max / step + 1 }, (_, k) => k * step).map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(v)} y2={y(v)} className="stroke-line" strokeWidth={1} />
            <text x={PAD.left - 6} y={y(v)} dy="0.32em" textAnchor="end" className="fill-muted chart-tick">
              {v}
            </text>
          </g>
        ))}
        {years.map((yr, i) =>
          tick(i) ? (
            <text key={yr} x={x(i)} y={H - 8} textAnchor="middle" className="fill-muted chart-tick">
              {yr.slice(2)}
            </text>
          ) : null,
        )}
        {others.map((vals, k) => (
          <path key={k} d={line(vals)} fill="none" className="stroke-line" strokeWidth={1.25} />
        ))}
        <path d={line(median)} fill="none" className="stroke-muted" strokeWidth={1.5} />
        <path d={line(city.values)} fill="none" className="stroke-accent chart-draw" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
        {city.values.map((v, i) =>
          v === null ? null : (
            <circle key={i} cx={x(i)} cy={y(v)} r={at === i ? 5 : 3} className="fill-accent stroke-surface" strokeWidth={2} />
          ),
        )}
        {lastIdx >= 0 && (
          <text x={x(lastIdx) + 8} y={y(city.values[lastIdx]!)} dy="0.32em" className="fill-ink chart-label">
            {n(city.values[lastIdx]!)}
          </text>
        )}
        {at !== null && (
          <line x1={x(at)} x2={x(at)} y1={PAD.top} y2={H - PAD.bottom} className="stroke-ink" strokeWidth={1} />
        )}
      </svg>
      {at !== null && (
        <div
          className="chart-tip pointer-events-none absolute z-10 border border-ink bg-surface px-2.5 py-1.5 text-xs shadow-[0_10px_24px_-14px_rgb(0_0_0/0.6)]"
          style={{ left: Math.min(Math.max(x(at) - 80, 0), width - 160), top: 0 }}
        >
          <p className="font-semibold">
            {t.fy} {years[at]}
          </p>
          <p>
            <span className="chart-key bg-accent" /> {city.name}: {city.values[at] === null ? "–" : `${n(city.values[at]!)} ${t.unit}`}
          </p>
          {ranks[at] && <p className="text-muted">{t.rank.replace("{rank}", String(ranks[at]!.rank)).replace("{of}", String(ranks[at]!.of))}</p>}
          <p>
            <span className="chart-key bg-muted" /> {t.median}: {median[at] === null ? "–" : `${n(median[at]!)} ${t.unit}`}
          </p>
        </div>
      )}
      <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs" dir="auto">
        <span><span className="chart-key bg-accent" /> {city.name}</span>
        <span><span className="chart-key bg-muted" /> {t.median}</span>
        <span><span className="chart-key bg-line" /> {t.others}</span>
      </p>
    </div>
  );
}
