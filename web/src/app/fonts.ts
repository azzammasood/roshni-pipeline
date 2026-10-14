// Site fonts, self-hosted from src/app/fonts/ (owner, 2026-10-14: the build no longer downloads
// from Google Fonts, after a publish run failed on a font fetch). Files are the Latin (Arabic for
// Nastaliq) WOFF2 subsets Google Fonts serves; each family is under the SIL Open Font License 1.1
// (OFL-*.txt next to the files). DM Serif Display: headlines, big numbers; Source Serif 4: body;
// IBM Plex Mono: times, codes, kickers. Urdu is set in Nastaliq throughout; it is not preloaded,
// so English pages never download it.
import localFont from "next/font/local";

const display = localFont({
  src: "./fonts/dm-serif-display-latin-400.woff2",
  weight: "400",
  display: "swap",
  variable: "--font-display",
});
const body = localFont({
  src: "./fonts/source-serif-4-latin-var.woff2",
  weight: "400 600",
  display: "swap",
  variable: "--font-body",
});
const mono = localFont({
  src: [
    { path: "./fonts/ibm-plex-mono-latin-400.woff2", weight: "400" },
    { path: "./fonts/ibm-plex-mono-latin-600.woff2", weight: "600" },
  ],
  display: "swap",
  variable: "--font-plex",
});
const nastaliq = localFont({
  src: "./fonts/noto-nastaliq-urdu-arabic-var.woff2",
  weight: "400 700",
  display: "swap",
  preload: false,
  variable: "--font-urdu",
});

export const fontVariables = [display, body, mono, nastaliq].map((f) => f.variable).join(" ");
