"use client";
// The visitor's pinned feeder (home page lead), kept in this browser only. Storage may be blocked
// (private mode, previews): the site then works without a pin.
import { useSyncExternalStore } from "react";

const KEY = "roshni:feeder";
const EVENT = "roshni:feeder";

export function readPin(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
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

export function setPin(feederId: string | null) {
  try {
    if (feederId) localStorage.setItem(KEY, feederId);
    else localStorage.removeItem(KEY);
  } catch {
    // Blocked storage: nothing to keep.
  }
  window.dispatchEvent(new Event(EVENT));
}

/** The pinned feeder id; null on the server, before hydration and when nothing is pinned. */
export const usePin = () => useSyncExternalStore(subscribe, readPin, () => null);
