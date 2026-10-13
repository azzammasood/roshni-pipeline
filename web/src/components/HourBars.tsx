// 24 bars: scheduled dark minutes in each local hour, with a minutes axis (0/30/60). The window
// list next to it is the text equivalent. Hours run left to right in both directions (time axis,
// not text). Axis hour labels follow the viewer's 24/12-hour clock.
import { HourLabel } from "@/components/Clock";

const BAR = 28;
const LEFT = 44;
const H = 96;
const TOP = 8; // room for the top axis label

export function HourBars({ minutes, label, unit }: { minutes: number[]; label: string; unit: (n: number) => string }) {
  const w = LEFT + 24 * BAR;
  const y = (m: number) => TOP + H - (m / 60) * H;
  return (
    <figure dir="ltr">
      <svg viewBox={`0 0 ${w} ${TOP + H + 18}`} className="w-full" role="img" aria-label={label}>
        {[0, 30, 60].map((m) => (
          <g key={m}>
            <line x1={LEFT - 4} x2={w} y1={y(m) + 0.5} y2={y(m) + 0.5} className="stroke-line" />
            <text x={LEFT - 8} y={y(m) + 4} textAnchor="end" className="fill-muted text-[11px]">
              {unit(m)}
            </text>
          </g>
        ))}
        {minutes.map((m, i) => (
          <rect key={i} x={LEFT + i * BAR + 2} y={y(m)} width={BAR - 4} height={(m / 60) * H} className="fill-dark">
            <title>
              <HourLabel hour={i} /> · {unit(m)}
            </title>
          </rect>
        ))}
        {[0, 3, 6, 9, 12, 15, 18, 21].map((i) => (
          <text key={i} x={LEFT + i * BAR + 2} y={TOP + H + 14} className="fill-muted text-[11px]">
            <HourLabel hour={i} />
          </text>
        ))}
      </svg>
    </figure>
  );
}
