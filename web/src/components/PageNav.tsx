"use client";
import { useEffect, useRef, useState } from "react";

/**
 * "On this page" bar for the home page. It pins to the top once the reader scrolls past it and
 * marks the section in view (aria-current), so the long page is one tap from any section.
 */
export function PageNav({ label, links }: { label: string; links: [string, string][] }) {
  const [active, setActive] = useState<string | null>(null);
  const [stuck, setStuck] = useState(false);
  const row = useRef<HTMLDivElement>(null);

  // On a phone the links scroll sideways: keep the current one in view without moving the page.
  useEffect(() => {
    const box = row.current;
    const link = box?.querySelector<HTMLElement>("a[aria-current]");
    if (!box || !link) return;
    const b = box.getBoundingClientRect();
    const l = link.getBoundingClientRect();
    if (l.left < b.left || l.right > b.right) box.scrollBy({ left: l.left - b.left - (b.width - l.width) / 2 });
  }, [active]);

  useEffect(() => {
    const ids = links.map(([href]) => href.slice(1));
    const check = () => {
      const bar = document.getElementById("page-nav");
      const top = (bar?.getBoundingClientRect().height ?? 0) + 24;
      setStuck((bar?.getBoundingClientRect().top ?? 1) <= 0 && window.scrollY > 0);
      // The section in view is the last one whose heading has passed the bar.
      let current: string | null = null;
      for (const id of ids) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top <= top + 40) current = id;
      }
      // At the very bottom the last section is in view even if its heading is below the bar.
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) current = ids.at(-1)!;
      setActive(current);
    };
    check();
    window.addEventListener("scroll", check, { passive: true });
    window.addEventListener("resize", check);
    return () => {
      window.removeEventListener("scroll", check);
      window.removeEventListener("resize", check);
    };
  }, [links]);

  return (
    <nav id="page-nav" aria-label={label} className="page-nav" data-stuck={stuck}>
      <div ref={row} className="page-nav-inner">
        <span className="page-nav-label kicker text-muted shrink-0">{label}</span>
        <ul className="page-nav-links">
          {links.map(([href, text]) => (
            <li key={href}>
              <a href={href} aria-current={active === href.slice(1) ? "location" : undefined}>
                {text}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
