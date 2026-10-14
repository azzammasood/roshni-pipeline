import { PageTransition } from "@/components/PageTransition";

// A template (unlike the layout) remounts on every navigation, so the page's enter and exit
// view transitions fire when the header tabs change.
export default function Template({ children }: { children: React.ReactNode }) {
  return <PageTransition>{children}</PageTransition>;
}
