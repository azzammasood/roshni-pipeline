"use client";
import Link from "next/link";
import { useRef } from "react";
import { Bulb } from "@/components/Bulb";

/** Wordmark with the bulb; a click (also the link home) flickers the bulb on. */
export function Logo({ href, name }: { href: string; name: string }) {
  const ref = useRef<HTMLAnchorElement>(null);
  const light = () => {
    const el = ref.current;
    if (!el) return;
    el.classList.remove("lit");
    void el.offsetWidth; // restart the animation on repeated clicks
    el.classList.add("lit");
  };
  return (
    <Link
      ref={ref}
      prefetch={false}
      href={href}
      onClick={light}
      className="logo inline-flex items-end gap-1.5"
    >
      <Bulb className="logo-bulb h-10 w-9 sm:h-12 sm:w-10 shrink-0 -mb-0.5" />
      <span className="logo-word headline text-4xl sm:text-5xl">{name}</span>
    </Link>
  );
}
