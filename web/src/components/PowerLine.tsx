// A feeder's day as a power line strung between two towers: taut wire where the schedule has
// power, slack dashed wire over a yellow wash for each scheduled-dark window, and an optional red
// "now" marker. Time runs left to right in both directions (time axis, not text); the caller lists
// the windows as text next to it. Axis labels follow the viewer's 24/12-hour clock.
import { HourLabel } from "@/components/Clock";
import { armTips, Tower } from "@/components/Pylon";

const BASE = 86;
const TOWER_H = 62;

/** Compact strips (one per IESCO level) are wider for the same height, so they stack tightly. */
function geometry(compact?: boolean) {
  const W = compact ? 1100 : 640;
  const left = armTips(22, BASE, TOWER_H).right;
  const right = armTips(W - 22, BASE, TOWER_H).left;
  return { W, Y: left.y, X: (m: number) => left.x + (m / 1440) * (right.x - left.x) };
}

/** Split windows that cross midnight; returns sorted [start, end) pieces within 0..1440. */
function pieces(windows: { start: number; end: number }[]) {
  return windows
    .flatMap((w) => (w.end > w.start ? [[w.start, w.end]] : [[w.start, 1440], [0, w.end]]))
    .filter(([a, b]) => b > a)
    .sort((p, q) => p[0] - q[0]);
}

export function PowerLine({
  windows,
  now,
  label,
  compact,
}: {
  windows: { start: number; end: number }[];
  now?: number | null;
  label: string;
  compact?: boolean;
}) {
  const { W, Y, X } = geometry(compact);
  const dark = pieces(windows);
  const taut: [number, number][] = [];
  let cursor = 0;
  for (const [a, b] of dark) {
    if (a > cursor) taut.push([cursor, a]);
    cursor = Math.max(cursor, b);
  }
  if (cursor < 1440) taut.push([cursor, 1440]);
  const height = compact ? 92 : 94;
  return (
    <figure dir="ltr" className="m-0">
      <svg viewBox={`0 0 ${W} ${height}`} className="w-full" role="img" aria-label={label}>
        {dark.map(([a, b]) => (
          <g key={`w${a}`} className="text-wire">
            <rect x={X(a)} y={6} width={X(b) - X(a)} height={BASE - 10} className="wash" />
            <line x1={X(a)} x2={X(b)} y1={6} y2={6} stroke="currentColor" strokeWidth={4} />
          </g>
        ))}
        {[0, 6, 12, 18, 24].map((h) => (
          <line key={h} x1={X(h * 60)} x2={X(h * 60)} y1={BASE - 4} y2={BASE + 2} className="stroke-muted" />
        ))}
        {taut.map(([a, b]) => (
          <line key={`t${a}`} x1={X(a)} x2={X(b)} y1={Y} y2={Y} className="stroke-ink" strokeWidth={2.5} />
        ))}
        {dark.map(([a, b]) => {
          const sag = Math.min(22, (X(b) - X(a)) * 0.25 + 4);
          return (
            <path
              key={`s${a}`}
              d={`M${X(a)} ${Y}Q${(X(a) + X(b)) / 2} ${Y + sag * 2} ${X(b)} ${Y}`}
              fill="none"
              className="stroke-muted"
              strokeWidth={1.5}
              strokeDasharray="4 4"
            />
          );
        })}
        <Tower x={22} base={BASE} h={TOWER_H} className="stroke-ink" width={1.4} />
        <Tower x={W - 22} base={BASE} h={TOWER_H} className="stroke-ink" width={1.4} />
        {now != null && (
          <g className="stroke-signal">
            <line x1={X(now)} x2={X(now)} y1={2} y2={BASE} strokeWidth={2} />
            <circle cx={X(now)} cy={Y} r={4.5} className="fill-signal" />
          </g>
        )}
      </svg>
      {!compact && <HourAxis />}
    </figure>
  );
}

/** Hour labels aligned with a strip's time scale (`wide` for compact strips). HTML text, so it
 *  stays readable however far the strips are scaled down. */
export function HourAxis({ wide = false }: { wide?: boolean }) {
  const { W, X } = geometry(wide);
  return (
    <div aria-hidden="true" dir="ltr" className="relative h-5 font-mono text-xs text-muted">
      {[0, 6, 12, 18, 24].map((h) => (
        <span key={h} className="absolute -translate-x-1/2" style={{ left: `${(X(h * 60) / W) * 100}%` }}>
          <HourLabel hour={h} />
        </span>
      ))}
    </div>
  );
}
