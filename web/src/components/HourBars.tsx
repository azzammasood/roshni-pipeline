// 24 bars: scheduled dark minutes in each local hour. Decorative; the window list next to it is
// the text equivalent. Hours run left to right in both directions (time axis, not text).
export function HourBars({ minutes, label }: { minutes: number[]; label: string }) {
  const w = 24 * 14;
  const h = 64;
  return (
    <figure className="space-y-1" dir="ltr">
      <svg viewBox={`0 0 ${w} ${h + 14}`} className="w-full max-w-xl" role="img" aria-label={label}>
        <line x1="0" x2={w} y1={h} y2={h} className="stroke-line" />
        {minutes.map((m, i) => (
          <rect
            key={i}
            x={i * 14 + 1}
            y={h - (m / 60) * h}
            width="12"
            height={(m / 60) * h}
            className="fill-dark"
          >
            <title>{`${String(i).padStart(2, "0")}:00 · ${m} min`}</title>
          </rect>
        ))}
        {[0, 6, 12, 18].map((i) => (
          <text key={i} x={i * 14 + 1} y={h + 12} className="fill-muted text-[9px]">
            {String(i).padStart(2, "0")}
          </text>
        ))}
      </svg>
    </figure>
  );
}
