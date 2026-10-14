// Light-bulb mark (logo and opening animation). Geometry only; the lit/flicker states are CSS
// (globals.css: .bulb-*, .logo.lit, .intro).
import { Tower, armTips, wirePath } from "@/components/Pylon";

/** Bulb in a 40 x 48 box: rays, glass, filament, screw base. */
export function BulbArt() {
  return (
    <>
      <g className="bulb-rays" strokeLinecap="round">
        {Array.from({ length: 8 }, (_, i) => {
          const a = (i * Math.PI) / 4 - Math.PI / 2;
          const c = (r: number) => [20 + r * Math.cos(a), 17 + r * Math.sin(a)];
          const [x1, y1] = c(16.5);
          const [x2, y2] = c(21);
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} strokeWidth={1.8} />;
        })}
      </g>
      <path
        className="bulb-glass"
        d="M14 30c-4-3.4-6-7.6-6-12.2a12 12 0 0 1 24 0c0 4.6-2 8.8-6 12.2v3h-12z"
        stroke="currentColor"
        strokeWidth={1.8}
        strokeLinejoin="round"
      />
      <path className="bulb-filament" d="M16.5 30v-6l2-3.2 1.5 3 1.5-3 2 3.2v6" fill="none" strokeWidth={1.5} strokeLinejoin="round" />
      <path d="M14.5 36h11M15.5 39h9M17.5 42h5" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" />
    </>
  );
}

export function Bulb({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 48" className={className} aria-hidden="true" focusable="false">
      <BulbArt />
    </svg>
  );
}

/** First page of a browser session: a pulse runs along a power line into the bulb, the bulb
 *  flickers on, the name appears, and the curtain lifts. Pure CSS, so it plays before hydration;
 *  skipped on later pages (html.intro-seen) and for reduced motion. Decorative only. */
export function Intro({ name, other }: { name: string; other: string }) {
  const base = 190;
  const h = 110;
  const t1 = armTips(50, base, h);
  const t2 = armTips(190, base, h);
  const spanA = wirePath(t1.right.x, t1.right.y, t2.left.x, t2.left.y, 16);
  const spanB = `M${t2.right.x} ${t2.right.y}Q${(t2.right.x + 300) / 2} ${t2.right.y + 40} 300 133`;
  return (
    <div className="intro" aria-hidden="true">
      <div className="intro-stage">
        <svg viewBox="0 0 400 200" className="intro-art">
          <Tower x={50} base={base} h={h} className="stroke-sky-muted" width={1.4} />
          <Tower x={190} base={base} h={h} className="stroke-sky-muted" width={1.4} />
          <path d={spanA} fill="none" className="stroke-wire" strokeWidth={1.5} />
          <path d={spanB} fill="none" className="stroke-wire" strokeWidth={1.5} />
          <path d={spanA} pathLength={100} fill="none" className="intro-spark intro-spark-a" />
          <path d={spanB} pathLength={100} fill="none" className="intro-spark intro-spark-b" />
          <g transform="translate(256 40) scale(2.2)" className="intro-bulb text-sky-ink">
            <BulbArt />
          </g>
        </svg>
        <p className="intro-word">
          <span className="headline">{name}</span>
          <span className="intro-other">{other}</span>
        </p>
      </div>
    </div>
  );
}
