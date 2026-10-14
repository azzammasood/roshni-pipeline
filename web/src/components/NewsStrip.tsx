// "In the news": recent load-shedding headlines from the approved outlets' feeds. Headline,
// outlet, date and a link to the original only; the words are the outlet's, never Roshni's, and
// headlines stay in the language the outlet published them in.
import type { Dictionary } from "@/i18n/dictionaries";
import { karachiDate } from "@/lib/time";
import type { NewsHeadline } from "@/types/v1";

export function NewsStrip({ items, t }: { items: NewsHeadline[]; t: Dictionary["news"] }) {
  return (
    <section aria-labelledby="news" className="space-y-3">
      <p className="kicker">{t.kicker}</p>
      <h2 id="news" className="headline text-2xl sm:text-3xl">
        {t.title}
      </h2>
      {items.length === 0 ? (
        <p className="text-muted max-w-prose">{t.empty}</p>
      ) : (
        <ol className="grid gap-x-6 sm:grid-cols-2 lg:grid-cols-3 rule">
          {items.map((h) => {
            const when = h.published_at ?? h.first_seen_at;
            return (
              <li key={h.link} className="border-b border-line py-3 min-w-0">
                <p className="kicker text-muted flex flex-wrap gap-x-2">
                  <span>{h.outlet}</span>
                  {when && (
                    <time dateTime={when} dir="ltr" className="font-mono">
                      {karachiDate(new Date(when))}
                    </time>
                  )}
                </p>
                <a
                  href={h.link}
                  rel="noopener noreferrer"
                  target="_blank"
                  className="headline text-lg block hover:underline decoration-wire decoration-2 underline-offset-4"
                >
                  <span lang="en" dir="ltr" className="block text-start">
                    {h.title}
                  </span>
                  <span className="sr-only"> ({t.external})</span>
                </a>
              </li>
            );
          })}
        </ol>
      )}
      <p className="text-sm text-muted max-w-prose">{t.note}</p>
    </section>
  );
}
