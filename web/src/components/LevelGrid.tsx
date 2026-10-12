// IESCO: one row per interruption level, one cell per local hour; a filled cell = scheduled dark
// for that whole hour IF the level is in force. Real table so screen readers can navigate it.
import { ScrollRegion } from "@/components/ScrollRegion";
type Props = {
  levels: Record<string, number[]>;
  caption: string;
  levelLabel: (n: string) => string;
  hourLabel: string;
  darkLabel: string;
};

export function LevelGrid({ levels, caption, levelLabel, hourLabel, darkLabel }: Props) {
  const hours = Array.from({ length: 24 }, (_, i) => i);
  return (
    <ScrollRegion label={caption} dir="ltr">
      <table className="level-grid">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col" className="sr-only">
              {hourLabel}
            </th>
            {hours.map((h) => (
              <th key={h} scope="col" className="text-[10px] font-normal text-muted">
                {h % 3 === 0 ? String(h).padStart(2, "0") : <span className="sr-only">{h}</span>}
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
