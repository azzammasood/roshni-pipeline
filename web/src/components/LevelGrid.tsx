// IESCO: one row per interruption level, one cell per local hour; a filled cell = scheduled dark
// for that whole hour IF the level is in force. Real table so screen readers can navigate it.
// Every hour is labelled (24-hour "00".."23", or 12-hour numbers under an AM/PM header row).
import { HourLabel, In12h } from "@/components/Clock";
import { ScrollRegion } from "@/components/ScrollRegion";

type Props = {
  levels: Record<string, number[]>;
  caption: string;
  levelLabel: (n: string) => string;
  hourLabel: string;
  darkLabel: string;
  halves: { am: string; pm: string };
};

export function LevelGrid({ levels, caption, levelLabel, hourLabel, darkLabel, halves }: Props) {
  const hours = Array.from({ length: 24 }, (_, i) => i);
  return (
    <ScrollRegion label={caption} dir="ltr">
      <table className="level-grid">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <In12h>
            <tr aria-hidden="true">
              <th />
              <th colSpan={12} className="text-[10px] font-normal text-muted text-start">
                {halves.am}
              </th>
              <th colSpan={12} className="text-[10px] font-normal text-muted text-start">
                {halves.pm}
              </th>
            </tr>
          </In12h>
          <tr>
            <th scope="col" className="sr-only">
              {hourLabel}
            </th>
            {hours.map((h) => (
              <th key={h} scope="col" className="text-[10px] font-normal text-muted tabular-nums">
                <HourLabel hour={h} compact />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Object.entries(levels).map(([n, mins]) => (
            <tr key={n}>
              <th scope="row" className="pe-2 text-xs font-normal whitespace-nowrap text-start">
                {levelLabel(n)}
              </th>
              {mins.map((m, h) => (
                <td key={h} className={m > 0 ? "on" : undefined}>
                  {m > 0 && <span className="sr-only">{darkLabel}</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollRegion>
  );
}
