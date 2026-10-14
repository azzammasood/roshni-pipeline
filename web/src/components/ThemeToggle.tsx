"use client";
import { useEffect } from "react";
import { setTheme, useTheme, type Theme } from "@/lib/theme";

const ICONS: Record<Theme, React.ReactNode> = {
  system: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M8 2.5v11a5.5 5.5 0 0 0 0-11z" className="fill-current" />
    </>
  ),
  light: (
    <>
      <circle cx="8" cy="8" r="3" />
      <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3 3l1.4 1.4M11.6 11.6 13 13M3 13l1.4-1.4M11.6 4.4 13 3" />
    </>
  ),
  dark: <path d="M13 9.5A5.5 5.5 0 1 1 6.5 3 4.5 4.5 0 0 0 13 9.5z" />,
};

/** System / light / dark, stored per viewer (like the clock toggle). */
export function ThemeToggle({ label, names }: { label: string; names: Record<Theme, string> }) {
  const theme = useTheme();
  // The boot script sets data-theme before paint; re-apply it after hydration in case React ever
  // re-renders <html> from scratch (that drops attributes it did not render).
  useEffect(() => {
    if (theme !== "system" && document.documentElement.dataset.theme !== theme) setTheme(theme);
  }, [theme]);
  return (
    <span role="group" aria-label={label} className="inline-flex rounded border border-line" dir="ltr">
      {(["system", "light", "dark"] as const).map((value) => (
        <button
          key={value}
          type="button"
          aria-pressed={theme === value}
          aria-label={names[value]}
          title={names[value]}
          onClick={() => setTheme(value)}
          className={`px-1.5 py-1 ${theme === value ? "bg-dark text-bg" : "text-muted hover:text-ink"}`}
        >
          <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 fill-none stroke-current" strokeWidth={1.4} aria-hidden="true">
            {ICONS[value]}
          </svg>
        </button>
      ))}
    </span>
  );
}
