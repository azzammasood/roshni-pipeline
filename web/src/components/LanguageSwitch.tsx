"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

/** Link to the same page in the other language (paths are /<locale>/...; Link adds basePath). */
export function LanguageSwitch({
  from,
  to,
  label,
  ariaLabel,
}: {
  from: string;
  to: string;
  label: string;
  ariaLabel: string;
}) {
  const path = usePathname() ?? `/${from}/`;
  const href = path.replace(new RegExp(`^/${from}(?=/|$)`), `/${to}`);
  return (
    <Link prefetch={false} href={href} hrefLang={to} lang={to} aria-label={`${label}: ${ariaLabel}`} className="link">
      {label}
    </Link>
  );
}
