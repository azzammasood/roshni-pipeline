// Ranked shares (0-100 %) as a skyline of transmission towers: tower height = share; name, value
// and n below. Small-n areas are drawn dashed and muted. The SVG is decorative for screen
// readers; the same values are in the visually hidden list that follows it. In RTL the ranking
// starts at the right, like the text.
import { armTips, Tower, wirePath } from "@/components/Pylon";

export type SkylineRow = { label: string; value: number; valueText: string; note: string; flag?: string };

const STEP = 36;
const START = 120; // room for the first rotated label, which runs toward the start side
const END = 30;
const BASE = 236;
const SCALE = 1.9; // px per percentage point
const LEG = 9;

export function EquitySkyline({
  rows,
  rtl,
  label,
  ticks,
}: {
  rows: SkylineRow[];
  rtl: boolean;
  label: string;
  /** Gridline labels, e.g. [[50, "50%"], [100, "100%"]]. */
  ticks: [number, string][];
}) {
  const width = START + END + STEP * (rows.length - 1);
  const xAt = (i: number) => (rtl ? width - START - i * STEP : START + i * STEP);
  const h = (v: number) => Math.max(v * SCALE, 6);
  const tips = rows.map((r, i) => armTips(xAt(i), BASE, h(r.value), LEG));
  return (
    <figure className="m-0 space-y-2">
      <div className="overflow-x-auto" role="region" aria-label={label} tabIndex={0}>
        <svg
          viewBox={`0 0 ${width} 430`}
          className="min-w-[56rem] w-full"
          aria-hidden="true"
          focusable="false"
          style={{ direction: "ltr" }}
        >
          {ticks.map(([v, text]) => (
            <g key={v}>
              <line x1={0} x2={width} y1={BASE - v * SCALE} y2={BASE - v * SCALE} className="stroke-line" strokeDasharray="2 4" />
              <text x={rtl ? width : 0} y={BASE - v * SCALE - 4} textAnchor={rtl ? "end" : "start"} className="fill-muted font-mono text-[11px]">
                {text}
              </text>
            </g>
          ))}
          <line x1={0} x2={width} y1={BASE} y2={BASE} className="stroke-ink" strokeWidth={1.5} />
          {tips.slice(0, -1).map((t, i) => {
            const [a, b] = rtl ? [tips[i + 1].right, t.left] : [t.right, tips[i + 1].left];
            return <path key={i} d={wirePath(a.x, a.y, b.x, b.y, 8)} fill="none" className="stroke-wire" strokeWidth={1.4} />;
          })}
          {rows.map((r, i) => {
            const x = xAt(i);
            const small = Boolean(r.flag);
            return (
              <g key={r.label}>
                <Tower x={x} base={BASE} h={h(r.value)} legWidth={LEG} width={1.5} dashed={small} className={small ? "stroke-muted" : "stroke-ink"} />
                <text
                  transform={`translate(${rtl ? x - 3 : x + 3} ${BASE + 12}) rotate(${rtl ? 55 : -55})`}
                  textAnchor={rtl ? "start" : "end"}
                  className="fill-ink text-[12px]"
                >
                  <tspan>{r.label} </tspan>
                  <tspan className="font-display text-[14px]">{r.valueText}</tspan>
                  <tspan className="fill-muted font-mono text-[11px]"> {r.note}</tspan>
                  {r.flag && <tspan className="fill-signal font-mono text-[11px]"> {r.flag}</tspan>}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <ul className="sr-only">
        {rows.map((r) => (
          <li key={r.label}>
            {r.label}: {r.valueText} {r.note}
            {r.flag && ` (${r.flag})`}
          </li>
        ))}
      </ul>
    </figure>
  );
}
