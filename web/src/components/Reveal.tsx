"use client";
import { useEffect, useRef, useState } from "react";

/** Fades its content up the first time it scrolls into view. Server HTML is fully visible; the
 *  hidden state is applied only after hydration and only below the fold (motion.css). */
export function Reveal({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"idle" | "pending" | "shown">("idle");
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    if (el.getBoundingClientRect().top < window.innerHeight) return; // already on screen
    setState("pending");
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setState("shown");
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -10% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  const motion = state === "pending" ? "reveal-pending" : state === "shown" ? "reveal-shown" : "";
  return (
    <div ref={ref} className={`${className} ${motion}`.trim()}>
      {children}
    </div>
  );
}
