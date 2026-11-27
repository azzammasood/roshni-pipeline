"use client";
// "Today, from the published data" (export ask/digest.json, written in publish by
// `roshni ask-prepared`): counts by SQL; in English one or two sentences by the main model under
// Ask Roshni's checks (placeholders only), in Urdu the same counts in a fixed sentence. Hidden
// when the file is missing or not from today (Pakistan date).
import { useEffect, useState } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import { fill } from "@/i18n/fill";
import { karachiDate } from "@/lib/time";

type Digest = { date: string; facts: Record<string, string>; text: string; narrated_by: string };

const URL_ = `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/data/v1/ask/digest.json`;

export function TodayDigest({ locale, t }: { locale: string; t: Dictionary["digest"] }) {
  const [d, setD] = useState<Digest | null>(null);
  useEffect(() => {
    fetch(URL_)
      .then((r) => (r.ok ? (r.json() as Promise<Digest>) : null))
      .then((x) => x && x.date === karachiDate(new Date()) && setD(x))
      .catch(() => {});
  }, []);
  if (!d) return null;
  const text = locale === "en" ? d.text : fill(t.template, d.facts, locale);
  return (
    <section aria-labelledby="digest" className="ask-digest">
      <h2 id="digest" className="kicker">
        {t.title}
      </h2>
      <p className="headline text-2xl sm:text-3xl max-w-4xl">{text}</p>
      <p className="text-xs text-muted">{d.narrated_by && locale === "en" ? fill(t.byModel, { m: d.narrated_by }, locale) : t.byCode}</p>
    </section>
  );
}
