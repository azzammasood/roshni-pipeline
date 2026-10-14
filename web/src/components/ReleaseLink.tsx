import { fill } from "@/i18n/fill";
import { isoMonth, monthLabel } from "@/lib/time";

/** IESCO's press-release listing (the only public page for them; numbers restart each month). */
export const IESCO_RELEASES = "https://iesco.com.pk/press-release";

/** "No. 12 (Oct 2026)", linked to IESCO's press-release page. */
export function ReleaseLink({
  no,
  period,
  locale,
  t,
}: {
  no: string | null;
  period?: string | null;
  locale: string;
  t: { release: string; releaseNoMonth: string; releaseLink: string };
}) {
  if (!no) return <>–</>;
  const text = period
    ? fill(t.release, { no, month: monthLabel(isoMonth(period), locale) }, locale)
    : fill(t.releaseNoMonth, { no }, locale);
  return (
    <a href={IESCO_RELEASES} className="link whitespace-nowrap" title={t.releaseLink} rel="noopener noreferrer" target="_blank">
      {text}
    </a>
  );
}
