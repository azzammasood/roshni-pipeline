import { ViewTransition } from "react";

/** Page content slides between header tabs (NavLinks tags each navigation nav-forward or
 *  nav-back by tab order; motion.css has the slides). Other navigations do not animate. */
export function PageTransition({ children }: { children: React.ReactNode }) {
  const types = { "nav-forward": "nav-forward", "nav-back": "nav-back", default: "none" };
  return (
    <ViewTransition enter={types} exit={types} default="none">
      <div>{children}</div>
    </ViewTransition>
  );
}
