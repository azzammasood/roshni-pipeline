// Site fonts, self-hosted by next/font at build time and shared by the locale layout and the 404.
// Latin: DM Serif Display (headlines, big numbers), Source Serif 4 (body), IBM Plex Mono (times,
// codes, kickers). Urdu is set in Nastaliq throughout; it is not preloaded, so English pages never
// download it.
import { DM_Serif_Display, IBM_Plex_Mono, Noto_Nastaliq_Urdu, Source_Serif_4 } from "next/font/google";

const display = DM_Serif_Display({ subsets: ["latin"], weight: "400", display: "swap", variable: "--font-display" });
const body = Source_Serif_4({ subsets: ["latin"], weight: ["400", "600"], display: "swap", variable: "--font-body" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "600"], display: "swap", variable: "--font-plex" });
const nastaliq = Noto_Nastaliq_Urdu({
  subsets: ["arabic"],
  weight: ["400", "700"],
  display: "swap",
  preload: false,
  variable: "--font-urdu",
});

export const fontVariables = [display, body, mono, nastaliq].map((f) => f.variable).join(" ");
