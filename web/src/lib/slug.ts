// Feeder ids look like "iesco:ajk:048101" or "ke:33E". Slugs are lowercase so they stay unique
// on case-insensitive file systems; build fails if two ids ever collide.
export function feederSlug(feederId: string): string {
  return feederId.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

export function slugIndex<T extends { feeder_id: string }>(rows: T[]): Map<string, T> {
  const index = new Map<string, T>();
  for (const row of rows) {
    const slug = feederSlug(row.feeder_id);
    const prior = index.get(slug);
    if (prior) throw new Error(`slug collision: ${prior.feeder_id} and ${row.feeder_id} -> ${slug}`);
    index.set(slug, row);
  }
  return index;
}
