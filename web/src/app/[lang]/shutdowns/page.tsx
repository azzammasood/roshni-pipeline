import type { Metadata } from "next";
import { MaintenancePanel } from "@/components/MaintenancePanel";
import { ShutdownNotices } from "@/components/ShutdownNotices";
import { ShutdownTable } from "@/components/ShutdownTable";
import { fill } from "@/i18n/dictionaries";
import { loadDocument } from "@/lib/data";
import { resolveLocale } from "@/lib/locale";

export async function generateMetadata({
  params,
}: PageProps<"/[lang]/shutdowns">): Promise<Metadata> {
  return { title: (await resolveLocale(params)).dict.shutdowns.title };
}

export default async function Shutdowns({ params }: PageProps<"/[lang]/shutdowns">) {
  const { locale, dict } = await resolveLocale(params);
  const rows = (await loadDocument("planned_shutdowns")).data;
  const dates = rows.map((r) => r.outage_date).sort();
  const { shutdowns, common, matchState, feeder, match } = dict;
  const national = (await loadDocument("national")).data;
  return (
    <div className="space-y-10">
      <section className="space-y-3">
        <p className="kicker">{shutdowns.kicker}</p>
        <h1 className="headline text-4xl sm:text-6xl">{shutdowns.title}</h1>
        <p className="max-w-prose text-lg">{shutdowns.intro}</p>
        {rows.length > 0 && (
          <p className="text-sm text-muted">
            {fill(shutdowns.count, { n: rows.length, from: dates[0], to: dates.at(-1)! }, locale)}
          </p>
        )}
      </section>
      <ShutdownNotices locale={locale} t={{ shutdowns, matchState }} />
      <div className="rule pt-4">
        <MaintenancePanel data={national} locale={locale} t={dict.maintenance} />
      </div>
      <section aria-labelledby="all-shutdowns" className="rule pt-4 space-y-4">
        <h2 id="all-shutdowns" className="headline text-3xl">
          {shutdowns.tableTitle}
        </h2>
        <ShutdownTable locale={locale} t={{ shutdowns, common, matchState, feeder, match }} />
      </section>
    </div>
  );
}
