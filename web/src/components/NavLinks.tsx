"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

/** Broadsheet section rule: the current section is underlined with a wire and marked for AT.
 *  Moving to a later tab is tagged nav-forward, to an earlier one nav-back, so the page slides
 *  in the matching direction (PageTransition); the wire glides to the new tab. */
export function NavLinks({ locale, items }: { locale: string; items: readonly (readonly [string, string])[] }) {
  const path = usePathname() ?? "";
  const current = (href: string) =>
    href ? path.startsWith(`/${locale}/${href}`) : path === `/${locale}` || path === `/${locale}/`;
  const here = items.findIndex(([href]) => current(href));
  const list = useRef<HTMLUListElement>(null);
  useEffect(() => {
    const tab = list.current?.querySelector<HTMLElement>('[aria-current="page"]');
    tab?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [here]);
  return (
    <ul ref={list} className="nav-row flex gap-x-5 overflow-x-auto whitespace-nowrap sm:flex-wrap sm:overflow-visible">
      {items.map(([href, label], i) => {
        const on = i === here;
        return (
          <li key={href} className="shrink-0">
            <Link
              prefetch={false}
              href={`/${locale}/${href}`}
              aria-current={on ? "page" : undefined}
              transitionTypes={on ? undefined : [here >= 0 && i < here ? "nav-back" : "nav-forward"]}
              className={`nav-tab relative inline-block py-1.5 border-b-4 border-transparent ${on ? "font-semibold" : ""}`}
            >
              {label}
              {on && (
                <span
                  aria-hidden="true"
                  className="absolute inset-x-0 -bottom-1 h-1 bg-wire"
                  style={{ viewTransitionName: "nav-wire" }}
                />
              )}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
