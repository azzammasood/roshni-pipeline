import type { Metadata } from "next";
import { Intro } from "@/components/Bulb";
import { ClockProvider, ClockToggle, NowStamp, Stamp } from "@/components/Clock";
import { ExportText } from "@/components/ExportText";
import { IntroSkip } from "@/components/IntroSkip";
import { LanguageSwitch } from "@/components/LanguageSwitch";
import { Logo } from "@/components/Logo";
import { NavLinks } from "@/components/NavLinks";
import { Skyline } from "@/components/Pylon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ToTop } from "@/components/ToTop";
import { builtLocales, dirOf } from "@/i18n/config";
import { fromExport, getDictionary } from "@/i18n/dictionaries";
import { loadDocument } from "@/lib/data";
import { BOOT_SCRIPT } from "@/lib/boot";
import { resolveLocale } from "@/lib/locale";
import { fontVariables } from "../fonts";
import "./globals.css";
import "./motion.css";

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
  // The name in the other script under the opening animation (روشنی on English pages, Roshni on Urdu).
  const otherName = (await getDictionary(locale === "en" ? "ur" : "en")).site.name;
  const nav = [
    ["", dict.nav.home],
    ["city/", dict.nav.cities],
    ["shutdowns/", dict.nav.shutdowns],
    ["karachi-equity/", dict.nav.equity],
    ["about/", dict.nav.about],
    ["architecture/", dict.nav.architecture],
  ] as const;

  return (
    // suppressHydrationWarning: the boot script sets data-theme / intro-seen before React loads.
    <html
      lang={locale}
      dir={dirOf(locale)}
      className={fontVariables}
      data-scroll-behavior="smooth"
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: BOOT_SCRIPT }} />
      </head>
      <body className="min-h-dvh flex flex-col">
        <Intro name={dict.site.name} other={otherName} steps={dict.site.loading} />
        <IntroSkip />
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:start-2 focus:top-2 bg-surface px-3 py-2 z-10"
        >
          {dict.site.skip}
        </a>
        <ClockProvider halves={{ am: dict.site.clock.am, pm: dict.site.clock.pm }}>
          <header>
            <div className="masthead">
              <div className="mx-auto max-w-5xl px-4 pt-4 flex flex-wrap items-end gap-x-4 gap-y-2">
                <Logo href={`/${locale}/`} name={dict.site.name} />
                <span className="ms-auto flex items-center gap-3 text-sm pb-1">
                  <ThemeToggle label={dict.site.theme.label} names={dict.site.theme} />
                  <ClockToggle label={dict.site.clock.label} h24={dict.site.clock.h24} h12={dict.site.clock.h12} />
                  {other && (
                    <LanguageSwitch
                      from={locale}
                      to={other}
                      label={dict.site.otherLanguage}
                      ariaLabel={dict.site.otherLanguageLabel}
                    />
                  )}
                </span>
                <div className="w-full border-y border-line py-1 flex flex-wrap gap-x-4 gap-y-0.5 font-mono text-[11px] text-muted">
                  <NowStamp />
                  <span dir="ltr">PKT · UTC+5</span>
                  <p role="note" className="text-ink">
                    {dict.banner.scheduled}
                  </p>
                </div>
              </div>
              <Skyline className="block w-full h-12 sm:h-16" />
            </div>
            <nav aria-label={dict.nav.label} className="rule-thin border-b-2 border-ink">
              <div className="mx-auto max-w-5xl px-4 text-sm">
                <NavLinks locale={locale} items={nav} />
              </div>
            </nav>
          </header>
          <main id="main" tabIndex={-1} className="flex-1 mx-auto w-full max-w-5xl px-4 py-6 focus:outline-none">
            {children}
          </main>
          <footer className="masthead text-sm">
            <Skyline className="block w-full h-10 opacity-70" />
            <div className="mx-auto max-w-5xl px-4 py-5 grid gap-4 sm:grid-cols-[auto_1fr]">
              <p className="headline text-2xl">{dict.site.name}</p>
              <div className="space-y-1 text-muted">
                <p>
                  {dict.footer.lastUpdated}: <Stamp iso={meta.last_updated} />
                </p>
                <p>{dict.footer.timezone}</p>
                <ExportText as="p" value={fromExport(meta.data.disclaimer, locale)} />
              </div>
            </div>
          </footer>
          <ToTop label={dict.site.toTop} />
        </ClockProvider>
      </body>
    </html>
  );
}
