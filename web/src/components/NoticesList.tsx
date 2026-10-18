// Notices IESCO posted on Facebook, recorded by hand (export 1.6.0 `notices`). Each links to the
// post; the summary is Roshni's wording. Shows nothing until a notice has been recorded.
import type { Dictionary } from "@/i18n/dictionaries";
import type { SocialNotice } from "@/types/v1";

export function NoticesList({
  notices,
  circle,
  t,
}: {
  notices: SocialNotice[];
  circle?: string;
  t: Dictionary["notices"];
}) {
  const list = notices
    .filter((n) => !circle || !n.circle || n.circle.toLowerCase() === circle.toLowerCase())
    .slice(0, 12);
  if (list.length === 0) return null;
  const kinds = t.kinds as Record<string, string>;
  return (
    <section aria-labelledby="notices" className="space-y-3">
      <p className="kicker">{t.kicker}</p>
      <h2 id="notices" className="headline text-3xl">
        {t.title}
      </h2>
      <p className="text-sm text-muted max-w-prose">{t.note}</p>
      <ol className="rule">
        {list.map((n) => (
          <li key={n.notice_id} className="border-b border-line py-3 grid gap-1 sm:grid-cols-[9rem_minmax(0,1fr)]">
            <p className="text-sm">
              <time dateTime={n.posted_on} className="font-mono" dir="ltr">
                {n.posted_on}
              </time>
              <span className="block kicker text-muted">{kinds[n.kind] ?? n.kind}</span>
            </p>
            <div>
              <p lang="en" dir="ltr" className="text-start">
                {n.summary}
              </p>
              {(n.window_date || n.areas) && (
                <p className="text-sm text-muted" dir="ltr">
                  {[n.window_date, n.start_local && n.end_local ? `${n.start_local}–${n.end_local}` : null, n.areas]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              )}
              <a href={n.url} className="link text-sm" rel="noopener noreferrer" target="_blank">
                {t.open}
              </a>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
