import { Fragment, type ReactNode } from "react";

/** Like `fill`, but placeholders take React nodes (e.g. a highlighted time inside a headline). */
export function rich(template: string, values: Record<string, ReactNode>): ReactNode[] {
  return template.split(/\{(\w+)\}/g).map((part, i) => {
    if (i % 2 === 0) return part;
    if (!(part in values)) throw new Error(`missing value for {${part}} in "${template}"`);
    return <Fragment key={i}>{values[part]}</Fragment>;
  });
}
