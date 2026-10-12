import type { ReactNode } from "react";

/** Horizontally scrollable wrapper for wide tables; focusable and labelled so keyboard users can
 *  scroll it (axe: scrollable-region-focusable). */
export function ScrollRegion({ label, dir, children }: { label: string; dir?: "ltr"; children: ReactNode }) {
  return (
    <div className="overflow-x-auto" role="region" aria-label={label} tabIndex={0} dir={dir}>
      {children}
    </div>
  );
}
