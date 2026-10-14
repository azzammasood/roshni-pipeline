"use client";
import { useEffect, useState } from "react";

/** Floating "back to top" button, shown once the reader is well down a long page. */
export function ToTop({ label }: { label: string }) {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const check = () => setShown(window.scrollY > 900);
    check();
    window.addEventListener("scroll", check, { passive: true });
    return () => window.removeEventListener("scroll", check);
  }, []);
  return (
    <button
      type="button"
      className="to-top grid h-11 w-11 place-items-center border-[1.5px] border-ink bg-wire text-notice-ink shadow-[0_10px_24px_-12px_rgb(0_0_0/0.6)]"
      data-shown={shown}
      inert={!shown}
      aria-label={label}
      title={label}
      onClick={() => {
        window.scrollTo({ top: 0 });
        document.getElementById("main")?.focus({ preventScroll: true });
      }}
    >
      <svg aria-hidden="true" viewBox="0 0 16 16" className="h-4 w-4 fill-none stroke-current" strokeWidth={1.8}>
        <path d="M3 10l5-5 5 5" />
      </svg>
    </button>
  );
}
