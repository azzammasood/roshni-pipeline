import type { Metadata } from "next";
import { Noto_Nastaliq_Urdu } from "next/font/google";
import Link from "next/link";
import { ExportText } from "@/components/ExportText";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { builtLocales, dirOf } from "@/i18n/config";
import { fromExport } from "@/i18n/dictionaries";
import { loadDocument } from "@/lib/data";
import { resolveLocale } from "@/lib/locale";
import { formatKarachi } from "@/lib/time";
import "./globals.css";

// Urdu is set in Nastaliq, self-hosted by next/font at build time. Not preloaded: only Urdu
// pages use it, so English pages never download it.
const nastaliq = Noto_Nastaliq_Urdu({
  subsets: ["arabic"],
  weight: ["400", "700"],
  display: "swap",
  preload: false,
  variable: "--font-urdu",
});

export const dynamicParams = false;
export const generateStaticParams = () => builtLocales.map((lang) => ({ lang }));

export async function generateMetadata({ params }: LayoutProps<"/[lang]">): Promise<Metadata> {
  const { dict } = await resolveLocale(params);
  return {
    title: { default: dict.site.name, template: `%s · ${dict.site.name}` },
    description: dict.site.tagline,
  };
}

export default async function LocaleLayout({ children, params }: LayoutProps<"/[lang]">) {
  const { locale, dict } = await resolveLocale(params);
  const meta = await loadDocument("meta");
  const other = builtLocales.find((l) => l !== locale);
  const nav = [
    ["", dict.nav.home],
    ["shutdowns/", dict.nav.shutdowns],
    ["karachi-equity/", dict.nav.equity],
    ["about/", dict.nav.about],
  ] as const;

  return (
    <html lang={locale} dir={dirOf(locale)} className={nastaliq.variable}>
      <body className="min-h-dvh flex flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:start-2 focus:top-2 bg-surface px-3 py-2"
        >
          {dict.site.skip}
        </a>
        <header className="border-b border-line">
          <div className="mx-auto max-w-5xl px-4 py-3 flex flex-wrap items-baseline gap-x-6 gap-y-2">
            <Link prefetch={false} href={`/${locale}/`} className="text-lg font-semibold">
              {dict.site.name}
            </Link>
            <nav aria-label={dict.nav.label} className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
              {nav.map(([href, label]) => (
                <Link key={href} prefetch={false} href={`/${locale}/${href}`} className="hover:underline">
                  {label}
                </Link>
              ))}
            </nav>
            {other && (
              <span className="ms-auto text-sm">
                <LanguageSwitch
                  from={locale}
                  to={other}
                  label={dict.site.otherLanguage}
                  ariaLabel={dict.site.otherLanguageLabel}
                />
              </span>
            )}
          </div>
          <p role="note" className="bg-notice text-notice-ink text-sm">
            <span className="block mx-auto max-w-5xl px-4 py-1.5">{dict.banner.scheduled}</span>
          </p>
        </header>
        <main id="main" className="flex-1 mx-auto w-full max-w-5xl px-4 py-6">
          {children}
        </main>
        <footer className="border-t border-line text-sm text-muted">
          <div className="mx-auto max-w-5xl px-4 py-4 space-y-1">
            <p>
              {dict.footer.lastUpdated}:{" "}
              <time dateTime={meta.last_updated}>{formatKarachi(meta.last_updated, locale)}</time>
            </p>
            <p>{dict.footer.timezone}</p>
            <ExportText as="p" value={fromExport(meta.data.disclaimer, locale)} />
          </div>
        </footer>
      </body>
    </html>
  );
}
