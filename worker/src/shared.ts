// Questions visitors chose to share with a down vote ("Also share this question"), kept for
// SHARED_DAYS days so the publish job can turn them into eval candidates. Opt-in only: nothing is
// kept for any other question. Read with GET /v1/shared and the admin token (index.ts); without a
// token configured the endpoint does not exist.
import { type Store, pktDay } from "./quota";

export const SHARED_DAYS = 30;
export type SharedQuestion = { date: string; question: string; reason: string; sql: string | null };

export class Shared {
  constructor(private store: Store) {}

  async add(q: Omit<SharedQuestion, "date">, now: number, id: string): Promise<void> {
    await this.store.put(`q:${pktDay(now)}:${id}`, { ...q, date: pktDay(now) } satisfies SharedQuestion);
  }

  async list(now: number): Promise<SharedQuestion[]> {
    const oldest = pktDay(now - (SHARED_DAYS - 1) * 86_400_000);
    const all = await this.store.list<SharedQuestion>({ prefix: "q:" });
    return [...all.values()].filter((q) => q.date >= oldest).sort((a, b) => a.date.localeCompare(b.date));
  }

  async sweep(now: number): Promise<number> {
    const oldest = pktDay(now - (SHARED_DAYS - 1) * 86_400_000);
    let n = 0;
    for (const key of (await this.store.list({ prefix: "q:" })).keys()) {
      if (key.slice(2, 12) < oldest) n += Number(await this.store.delete(key));
    }
    return n;
  }
}
