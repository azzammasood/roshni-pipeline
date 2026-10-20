import type { Metadata } from "next";
import { MyFeederPanel } from "@/components/MyFeederPanel";
import { resolveLocale } from "@/lib/locale";

export async function generateMetadata({ params }: PageProps<"/[lang]/my-feeder">): Promise<Metadata> {
  return { title: (await resolveLocale(params)).dict.nav.myFeeder };
}

/** One feeder only: search and pin it (kept in this browser), then its schedule and what is coming up. */
export default async function MyFeeder({ params }: PageProps<"/[lang]/my-feeder">) {
  const { locale, dict } = await resolveLocale(params);
  const { lead, common, sources, myFeeder, maintenance } = dict;
  return <MyFeederPanel locale={locale} t={{ lead, common, sources, myFeeder, maintenance }} />;
}
