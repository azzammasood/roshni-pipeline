// Transmission tower and power-line primitives (SVG), shared by the masthead skyline, the feeder
// day strip and the equity skyline. Geometry only: colours come from the caller's classes.

/** Half-widths of a tower of height h: base legs and waist. `width` fixes the leg half-width
 *  (charts, where towers of every height share one footprint). */
const legs = (h: number, width?: number) => {
  const hw = width ?? h * 0.16 + 4;
  return { hw, mw: hw * 0.45 };
};

/** Where the wires hang: the two cross-arm tips of a tower standing at (x, base) with height h. */
export function armTips(x: number, base: number, h: number, width?: number) {
  const { hw } = legs(h, width);
  const y = base - h + h * 0.2;
  return { left: { x: x - hw * 1.1, y }, right: { x: x + hw * 1.1, y } };
}

/** Lattice tower outline as one path: legs, cross-arm, cross-bracing and insulators. */
export function towerPath(x: number, base: number, h: number, width?: number): string {
  const top = base - h;
  const { hw, mw } = legs(h, width);
  const waist = top + h * 0.35;
  const arm = top + h * 0.2;
  const ins = Math.max(h * 0.05, 1.5);
  return [
    `M${x - hw} ${base}L${x - mw} ${waist}L${x} ${top}L${x + mw} ${waist}L${x + hw} ${base}`,
    `M${x - hw * 1.1} ${arm}L${x + hw * 1.1} ${arm}`,
    `M${x - hw * 1.1} ${arm}l0 ${ins}M${x + hw * 1.1} ${arm}l0 ${ins}`,
    `M${x - mw * 0.8} ${top + h * 0.4}L${x + hw * 0.9} ${base}`,
    `M${x + mw * 0.8} ${top + h * 0.4}L${x - hw * 0.9} ${base}`,
    `M${x - mw * 0.7} ${top + h * 0.12}L${x + mw * 0.7} ${top + h * 0.12}`,
  ].join("");
}

/** A hanging wire between two points, sagging `sag` below the lower end. */
export function wirePath(x1: number, y1: number, x2: number, y2: number, sag: number): string {
  return `M${x1} ${y1}Q${(x1 + x2) / 2} ${Math.max(y1, y2) + sag} ${x2} ${y2}`;
}

export function Tower({
  x,
  base,
  h,
  className,
  width = 1.2,
  legWidth,
  dashed,
}: {
  x: number;
  base: number;
  h: number;
  className?: string;
  width?: number;
  legWidth?: number;
  dashed?: boolean;
}) {
  return (
    <path
      d={towerPath(x, base, h, legWidth)}
      fill="none"
      strokeWidth={width}
      strokeDasharray={dashed ? "3 2" : undefined}
      strokeLinejoin="round"
      vectorEffect="non-scaling-stroke"
      className={className}
    />
  );
}

/** Decorative skyline of towers with live-looking wires (masthead, 404, footer). */
export function Skyline({ className }: { className?: string }) {
  const base = 80;
  const towers = [40, 210, 380, 550, 720, 890, 1060].map((x, i) => ({ x, h: [58, 46, 62, 50, 60, 44, 56][i] }));
  const spans = towers.slice(0, -1).map((t, i) => {
    const n = towers[i + 1];
    const a = armTips(t.x, base, t.h);
    const b = armTips(n.x, base, n.h);
    return [wirePath(a.right.x, a.right.y, b.left.x, b.left.y, 14), wirePath(a.left.x, a.left.y, b.right.x, b.right.y, 22)];
  });
  return (
    <svg
      viewBox="0 0 1100 84"
      preserveAspectRatio="xMidYMax slice"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      {spans.flat().map((d, i) => (
        <g key={i}>
          <path d={d} fill="none" className="stroke-wire" strokeWidth={1.3} vectorEffect="non-scaling-stroke" />
          <path d={d} fill="none" className="stroke-wire current" strokeWidth={2.5} vectorEffect="non-scaling-stroke" />
        </g>
      ))}
      {towers.map((t) => (
        <Tower key={t.x} x={t.x} base={base} h={t.h} className="stroke-sky-muted" />
      ))}
    </svg>
  );
}
