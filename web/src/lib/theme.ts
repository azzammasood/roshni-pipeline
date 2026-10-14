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

export function setTheme(theme: Theme) {
  try {
    if (theme === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, theme);
  } catch {
    // Blocked storage: the choice lasts for this page only.
  }
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  window.dispatchEvent(new Event(EVENT));
}

export const useTheme = () => useSyncExternalStore(subscribe, read, () => "system" as Theme);
