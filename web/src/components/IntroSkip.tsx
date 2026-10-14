"use client";
import { useEffect } from "react";

/** Lets a click, tap or key press skip the opening animation (it is pure CSS and plays before
 *  React loads; once hydrated, any input lifts the curtain at once). */
export function IntroSkip() {
  useEffect(() => {
    const root = document.documentElement;
    if (root.classList.contains("intro-seen")) return;
    const skip = () => root.classList.add("intro-seen");
    const opts = { once: true, capture: true } as const;
    window.addEventListener("pointerdown", skip, opts);
    window.addEventListener("keydown", skip, opts);
    return () => {
      window.removeEventListener("pointerdown", skip, opts);
      window.removeEventListener("keydown", skip, opts);
    };
  }, []);
  return null;
}
