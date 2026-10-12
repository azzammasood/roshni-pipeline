// Horizontal bars (0-100 %), one per row, as a list so the values are plain text for screen
// readers. Bars grow from the inline start, so they mirror correctly in RTL.
export type ShareBar = { label: string; value: number; note: string; flag?: string };

export function ShareBars({ rows, valueText }: { rows: ShareBar[]; valueText: (v: number) => string }) {
  return (
    <ul className="space-y-1.5">
      {rows.map((r) => (
        <li
          key={r.label}
          className="grid grid-cols-[1fr_7rem] sm:grid-cols-[15rem_1fr_7rem] gap-x-3 items-center text-sm"
        >
          <span className="col-span-2 flex min-w-0 items-center gap-1 sm:col-span-1">
            <span className="truncate" title={r.label}>
              <bdi>{r.label}</bdi>
            </span>
            {r.flag && (
              <span className="shrink-0 rounded bg-notice px-1 text-xs text-notice-ink">{r.flag}</span>
            )}
          </span>
          <span className="block h-3 rounded-sm bg-line" aria-hidden="true">
            <span
              className="block h-3 rounded-sm bg-dark"
              style={{ inlineSize: `${Math.min(Math.max(r.value, 0.5), 100)}%` }}
            />
          </span>
          <span className="whitespace-nowrap tabular-nums">
            {valueText(r.value)} <span className="text-muted">{r.note}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
