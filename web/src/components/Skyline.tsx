"use client";
// Decorative skyline of towers with live-looking wires (masthead, 404, footer). The drawing is
// laid out for the box it is drawn in: towers are spaced across the measured width so the first
// and last always stand whole inside it, and the wires run on past both edges. Before the first
// measurement (static HTML) it uses a 1100-wide layout.
import { useEffect, useRef, useState } from "react";
import { Tower, armTips, wirePath } from "@/components/Pylon";

const H = 84;
const BASE = 80;
const HEIGHTS = [58, 46, 62, 50, 60, 44, 56];
const GAP = 170; // target distance between towers, in viewBox units
const MARGIN = 34; // clears the widest tower's cross-arm (about 15 units) with room to spare

export function Skyline({ className }: { className?: string }) {
  const ref = useRef<SVGSVGElement>(null);
  const [width, setWidth] = useState(1100);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const { width: w, height: h } = el.getBoundingClientRect();
      if (w > 0 && h > 0) setWidth(Math.round((H * w) / h));
    };
    measure(); // at once, then on every resize
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const count = Math.max(2, Math.round((width - 2 * MARGIN) / GAP) + 1);
  const step = (width - 2 * MARGIN) / (count - 1);
  const towers = Array.from({ length: count }, (_, i) => ({ x: MARGIN + i * step, h: HEIGHTS[i % HEIGHTS.length] }));
  const spans = towers.slice(0, -1).map((t, i) => {
    const n = towers[i + 1];
    const a = armTips(t.x, BASE, t.h);
    const b = armTips(n.x, BASE, n.h);
    return [wirePath(a.right.x, a.right.y, b.left.x, b.left.y, 14), wirePath(a.left.x, a.left.y, b.right.x, b.right.y, 22)];
  });
  // Lead-in and lead-out wires: the line continues beyond the frame.
  const first = armTips(towers[0].x, BASE, towers[0].h);
  const last = armTips(towers.at(-1)!.x, BASE, towers.at(-1)!.h);
  const ends = [
    wirePath(-20, first.left.y + 6, first.left.x, first.left.y, 8),
    wirePath(last.right.x, last.right.y, width + 20, last.right.y + 6, 8),
  ];

  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${width} ${H}`}
      preserveAspectRatio="xMidYMax slice"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      {[...spans.flat(), ...ends].map((d, i) => (
        <g key={i}>
          <path d={d} fill="none" className="stroke-wire" strokeWidth={1.3} vectorEffect="non-scaling-stroke" />
          <path d={d} fill="none" className="stroke-wire current" strokeWidth={2.5} vectorEffect="non-scaling-stroke" />
        </g>
      ))}
      {towers.map((t) => (
        <Tower key={t.x} x={t.x} base={BASE} h={t.h} className="stroke-sky-muted" />
      ))}
    </svg>
  );
}
