// Tool logos for the "How it's built" page, rendered to inline SVG at build time (no requests).
// Brand marks come from Simple Icons (CC0; the marks remain their owners' trademarks and only name
// the tools used). Tools without a Simple Icons mark get a plain lettered tile, never a lookalike.
import type { SimpleIcon } from "simple-icons";
import {
  siApacheairflow,
  siApacheparquet,
  siClaude,
  siDatabricks,
  siDocker,
  siDuckdb,
  siEslint,
  siGit,
  siGithubactions,
  siGithubpages,
  siNextdotjs,
  siOpenrouter,
  siPrecommit,
  siPydantic,
  siPytest,
  siPython,
  siReact,
  siRss,
  siRuff,
  siTailwindcss,
  siTyper,
  siTypescript,
  siUv,
  siVitest,
} from "simple-icons";

const ICONS: Record<string, SimpleIcon> = {
  "Apache Airflow": siApacheairflow,
  Parquet: siApacheparquet,
  Claude: siClaude,
  Databricks: siDatabricks,
  Docker: siDocker,
  "Docker Compose": siDocker,
  DuckDB: siDuckdb,
  ESLint: siEslint,
  git: siGit,
  "GitHub Actions": siGithubactions,
  "GitHub Pages": siGithubpages,
  "Next.js": siNextdotjs,
  OpenRouter: siOpenrouter,
  "pre-commit": siPrecommit,
  pydantic: siPydantic,
  pytest: siPytest,
  Python: siPython,
  React: siReact,
  RSS: siRss,
  ruff: siRuff,
  "Tailwind CSS": siTailwindcss,
  "Typer CLI": siTyper,
  TypeScript: siTypescript,
  uv: siUv,
  Vitest: siVitest,
};

// Lettered tiles for tools Simple Icons does not carry.
const LETTERS: Record<string, string> = {
  dbt: "dbt",
  "dbt tests": "dbt",
  "Great Expectations": "GX",
  httpx: "hx",
  "Beautiful Soup": "bs4",
  "robots.txt": "bot",
  "poppler pdftotext": "pdf",
  openpyxl: "xl",
  RapidFuzz: "rf",
  "JSON Schema": "{ }",
  "axe-core": "axe",
  "SHA-256": "#",
  "ETag / If-Modified-Since": "304",
};

/** Marks too dark to see on the night tile are drawn in paper white instead. */
function fill(hex: string): string {
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.25 ? "#f4f1ea" : `#${hex}`;
}

export function hasLogo(name: string) {
  return name in ICONS || name in LETTERS;
}

/** A square night-sky tile holding the tool's mark (decorative: the tool's name is always shown
 *  next to it as text). */
export function ToolLogo({ name, size = "md" }: { name: string; size?: "sm" | "md" }) {
  const icon = ICONS[name];
  const box = size === "sm" ? "h-5 w-5 p-[3px]" : "h-10 w-10 p-2";
  if (icon) {
    return (
      <span aria-hidden="true" className={`tool-tile ${box}`}>
        <svg viewBox="0 0 24 24" className="h-full w-full" fill={fill(icon.hex)}>
          <path d={icon.path} />
        </svg>
      </span>
    );
  }
  return (
    <span aria-hidden="true" className={`tool-tile tool-letters ${box} ${size === "sm" ? "text-[0.45rem]" : "text-[0.7rem]"}`}>
      {LETTERS[name] ?? name.slice(0, 2)}
    </span>
  );
}
