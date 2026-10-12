import type { ElementType } from "react";

/** Text that came from the export: translated, or kept in English and marked lang="en" dir="ltr"
 *  (so screen readers switch voice and the sentence lays out left-to-right in an RTL page). */
export function ExportText({
  value,
  as: Tag = "span",
  className,
}: {
  value: { text: string; lang?: "en" };
  as?: ElementType;
  className?: string;
}) {
  return value.lang ? (
    <Tag lang="en" dir="ltr" className={[className, "text-start"].filter(Boolean).join(" ")}>
      {value.text}
    </Tag>
  ) : (
    <Tag className={className}>{value.text}</Tag>
  );
}
