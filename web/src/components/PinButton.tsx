"use client";
import { useEffect } from "react";
import { readPin, setPin, usePin } from "@/lib/pin";

/** Pin this feeder to the home page lead. Opening a feeder pins it when nothing is pinned yet. */
export function PinButton({ feederId, pin, pinned }: { feederId: string; pin: string; pinned: string }) {
  const current = usePin();
  useEffect(() => {
    if (!readPin()) setPin(feederId);
  }, [feederId]);
  const on = current === feederId;
  return (
    <button
      type="button"
      onClick={() => setPin(on ? null : feederId)}
      className={`chip px-2 py-0.5 ${on ? "bg-wire text-[#14213d] border-[#14213d]" : "hover:bg-surface"}`}
    >
      {on ? pinned : pin}
    </button>
  );
}
