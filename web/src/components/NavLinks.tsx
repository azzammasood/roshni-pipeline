"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

/** Broadsheet section rule: the current section is underlined with a wire and marked for AT. */
export function NavLinks({ locale, items }: { locale: string; items: readonly (readonly [string, string])[] }) {
  const path = usePathname() ?? "";
  const current = (href: string) =>
    href ? path.startsWith(`/${locale}/${href}`) : path === `/${locale}` || path === `/${locale}/`;
  return (
    <ul className="flex flex-wrap gap-x-5">
      {items.map(([href, label]) => {
        const on = current(href);
        return (
          <li key={href}>
            <Link
              prefetch={false}
              href={`/${locale}/${href}`}
              aria-current={on ? "page" : undefined}
              className={`inline-block py-1.5 border-b-4 ${on ? "border-wire font-semibold" : "border-transparent hover:border-line"}`}
            >
              {label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
