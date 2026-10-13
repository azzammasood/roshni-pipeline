// Site-wide 404 (out/404.html, which GitHub Pages serves for any missing path). The root layout
// lives under [lang], so this page carries its own <html> and styles and offers every built
// language, since the URL may not say which one the visitor wanted.
import type { Metadata } from "next";
import Link from "next/link";
import { builtLocales, dirOf } from "@/i18n/config";
import en from "@/i18n/en.json";
import ur from "@/i18n/ur.json";
import "./[lang]/globals.css";

const dicts = { en, ur } as const;

export const metadata: Metadata = {
  title: `${en.notFound.title} · ${en.site.name}`,
  robots: { index: false },
};

export default function GlobalNotFound() {
  return (
    <html lang="en">
      <body className="min-h-dvh">
        <header className="border-b border-line">
          <div className="mx-auto max-w-5xl px-4 py-3">
            <Link prefetch={false} href="/en/" className="text-lg font-semibold">
              {en.site.name}
            </Link>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-10 space-y-10">
          {builtLocales.map((locale) => {
            const d = dicts[locale];
            const pages = [
              ["", d.nav.home],
              ["shutdowns/", d.nav.shutdowns],
              ["karachi-equity/", d.nav.equity],
              ["about/", d.nav.about],
            ] as const;
            return (
              <section key={locale} lang={locale} dir={dirOf(locale)} className="space-y-3">
                <h1 className="text-2xl font-semibold">{d.notFound.title}</h1>
                <p>{d.notFound.body}</p>
                <ul className="list-disc ps-5 space-y-1">
                  {pages.map(([href, label]) => (
                    <li key={href}>
                      <Link prefetch={false} href={`/${locale}/${href}`} className="link">
                        {href ? label : d.notFound.home}
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </main>
      </body>
    </html>
  );
}
