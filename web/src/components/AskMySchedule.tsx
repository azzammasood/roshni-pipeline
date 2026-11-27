"use client";
// Ask Roshni's answer to "Will I get load shedding today?" (lib/ask/intent.ts): the pinned
// feeder's lead from the site's own schedule engine, the same component as My feeder, or the
// feeder finder when nothing is pinned. No language model and no question from the quota.
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { Dictionary } from "@/i18n/dictionaries";
import type { IescoLevel } from "@/lib/darkNow";
import { usePin } from "@/lib/pin";
import { karachiDate, karachiMinuteOfDay } from "@/lib/time";
import { useExport } from "@/lib/useExport";
import { FeederFinder, PinnedFeeder, type LeadStrings } from "@/components/PinnedFeeder";

export function AskMySchedule({ locale, t, lt }: { locale: string; t: Dictionary["ask"]; lt: LeadStrings }) {
  const state = useExport(["feeders", "dark_profiles"] as const);
  const maint = useExport(["maintenance_upcoming"] as const);
  const pin = usePin();
  const [now, setNow] = useState<Date | null>(null);
  const [level, setLevel] = useState<IescoLevel | null>(null);

  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  const ready = state.status === "ready" ? state.data : null;
  const scheduled = useMemo(() => ready?.feeders.data.filter((f) => f.has_schedule) ?? [], [ready]);
  const feeder = pin ? scheduled.find((f) => f.feeder_id === pin) : undefined;
  const profile = feeder ? ready?.dark_profiles.data.find((p) => p.feeder_id === feeder.feeder_id) : undefined;
  const today = now ? karachiDate(now) : null;
  const maintenance = useMemo(
    () =>
      feeder && today && maint.status === "ready"
        ? maint.data.maintenance_upcoming.data
            .filter((w) => w.feeder_id === feeder.feeder_id && !w.repeats_circle_window && w.outage_date >= today)
            .sort((a, b) => (a.outage_date + a.start_local).localeCompare(b.outage_date + b.start_local))
        : undefined,
    [feeder, today, maint],
  );

  return (
    <section aria-labelledby="ask-lead" className="ask-mine space-y-4">
      <p className="ask-route">
        <span className="ask-route-lamp" aria-hidden="true" />
        {t.mineRoute}
      </p>
      {!ready || !today ? (
        <p className="text-muted" id="ask-lead">
          {state.status === "error" ? lt.common.loadError : lt.common.loading}
        </p>
      ) : feeder ? (
        <>
          <PinnedFeeder
            feeders={scheduled}
            feeder={feeder}
            profile={profile}
            minute={karachiMinuteOfDay(now!)}
            today={today}
            level={level}
            onLevel={setLevel}
            maintenance={maintenance}
            locale={locale}
            t={lt}
            heading="h2"
          />
          <p className="text-sm">
            <Link prefetch={false} href={`/${locale}/my-feeder/`} className="link">
              {t.mineMore}
            </Link>
          </p>
        </>
      ) : (
        <>
          <p className="max-w-prose">{t.mineNoPin}</p>
          <FeederFinder feeders={scheduled} locale={locale} t={lt} heading="h2" />
        </>
      )}
    </section>
  );
}
