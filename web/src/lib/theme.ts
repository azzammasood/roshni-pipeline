"use client";
// Viewer's theme choice: "system" (follow the OS) or a fixed light/dark, kept in this browser.
import { useSyncExternalStore } from "react";

export type Theme = "system" | "light" | "dark";
const KEY = "roshni:theme";
const EVENT = "roshni:theme";

function read(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function apply(theme: Theme) {
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  window.dispatchEvent(new Event(EVENT));
}

/** Saves and applies a theme. With `from` (the toggle's position) and motion welcome, the new
 *  theme spreads from that point as a circle (View Transitions API); otherwise it is instant. */
export function setTheme(theme: Theme, from?: { x: number; y: number }) {
  try {
    if (theme === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, theme);
  } catch {
    // Blocked storage: the choice lasts for this page only.
  }
  const root = document.documentElement;
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!from || still || typeof document.startViewTransition !== "function") return apply(theme);
  root.classList.add("theme-swap");
  const vt = document.startViewTransition(() => apply(theme));
  const radius = Math.hypot(Math.max(from.x, innerWidth - from.x), Math.max(from.y, innerHeight - from.y));
  vt.ready
    .then(() =>
      root.animate(
        { clipPath: [`circle(0px at ${from.x}px ${from.y}px)`, `circle(${radius}px at ${from.x}px ${from.y}px)`] },
        { duration: 650, easing: "cubic-bezier(0.4, 0, 0.2, 1)", pseudoElement: "::view-transition-new(root)" },
      ),
    )
    .catch(() => {});
  vt.finished.finally(() => root.classList.remove("theme-swap"));
}

export const useTheme = () => useSyncExternalStore(subscribe, read, () => "system" as Theme);
