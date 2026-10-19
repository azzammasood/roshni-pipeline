import { feederSlug } from "./slug";

type Doc = "meta" | "feeders" | "dark_profiles" | "planned_shutdowns" | "areas" | "equity" | "maintenance";

/** Public URL of an export document for client-side fetches (fetch() does not add basePath). */
export const documentUrl = (doc: Doc) =>
  `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/data/v1/${doc}.json`;

/** Feeder page path for next/link (Link adds basePath itself). */
export const feederHref = (locale: string, feederId: string) =>
  `/${locale}/feeder/${feederSlug(feederId)}/`;
