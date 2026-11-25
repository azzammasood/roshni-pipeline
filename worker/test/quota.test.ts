import { describe, expect, it } from "vitest";
import { MapStore, Quota, pktDay, secondsToPktMidnight, visitorId } from "../src/quota";

const LIMITS = { visitorPerMinute: 3, visitorPerDay: 10, globalPerMinute: 6, globalPerDay: 15, tokensPerDay: 1000 };
const T0 = Date.parse("2026-11-25T10:00:00Z"); // 15:00 in Karachi

describe("caps", () => {
  it("lets a visitor ask three a minute, then says when to retry", async () => {
    const q = new Quota(new MapStore(), LIMITS);
    for (let i = 0; i < 3; i++) expect((await q.admit("a", T0 + i * 1000)).ok).toBe(true);
    const r = await q.admit("a", T0 + 3000);
    expect(r).toMatchObject({ ok: false, reason: "visitor_minute", retry_after_s: 57 });
    expect((await q.admit("a", T0 + 61_000)).ok).toBe(true);
  });

  it("stops one visitor at ten a day without touching others", async () => {
    const q = new Quota(new MapStore(), { ...LIMITS, globalPerDay: 100, globalPerMinute: 100 });
    for (let i = 0; i < 10; i++) expect((await q.admit("a", T0 + i * 61_000)).ok).toBe(true);
    const r = await q.admit("a", T0 + 11 * 61_000);
    expect(r).toMatchObject({ ok: false, reason: "visitor_day", remaining: { visitor_today: 0 } });
    expect((await q.admit("b", T0 + 11 * 61_000)).ok).toBe(true);
  });

  it("caps the whole site per minute and per day", async () => {
    const q = new Quota(new MapStore(), LIMITS);
    for (let i = 0; i < 6; i++) expect((await q.admit(`v${i}`, T0)).ok).toBe(true);
    expect(await q.admit("v6", T0)).toMatchObject({ ok: false, reason: "site_minute" });
    for (let i = 0; i < 9; i++) expect((await q.admit(`w${i}`, T0 + 61_000 * (1 + Math.floor(i / 6)))).ok).toBe(true);
    expect(await q.admit("x", T0 + 300_000)).toMatchObject({ ok: false, reason: "site_day", remaining: { site_today: 0 } });
  });

  it("closes for the day when the token budget is spent", async () => {
    const q = new Quota(new MapStore(), LIMITS);
    await q.addTokens(1000, T0);
    expect(await q.admit("a", T0)).toMatchObject({ ok: false, reason: "site_tokens", remaining: { site_today: 0 } });
  });

  it("resets at midnight in Karachi, not UTC", async () => {
    const q = new Quota(new MapStore(), { ...LIMITS, visitorPerDay: 1 });
    const late = Date.parse("2026-11-25T18:59:00Z"); // 23:59 PKT
    expect((await q.admit("a", late)).ok).toBe(true);
    expect(await q.admit("a", late + 30_000)).toMatchObject({ reason: "visitor_day", retry_after_s: 30 });
    expect((await q.admit("a", late + 61_000)).ok).toBe(true); // 00:00:01 PKT, next day
    expect(pktDay(late)).toBe("2026-11-25");
    expect(pktDay(late + 61_000)).toBe("2026-11-26");
    expect(secondsToPktMidnight(T0)).toBe(9 * 3600);
  });

  it("sweeps old days and expired tickets", async () => {
    const s = new MapStore();
    const q = new Quota(s, LIMITS);
    await q.admit("a", T0);
    await q.putTicket("t1", { visitor: "a", question: "q", created: T0, replans: 0, narrated: false, history: [] });
    expect(await q.sweep(T0 + 86_400_000)).toBe(3);
    expect(s.m.size).toBe(0);
  });
});

describe("tickets", () => {
  it("belong to one visitor and expire after ten minutes", async () => {
    const q = new Quota(new MapStore(), LIMITS);
    await q.putTicket("t", { visitor: "a", question: "q", created: T0, replans: 0, narrated: false, history: [] });
    expect(await q.ticket("t", "a", T0 + 1000)).not.toBeNull();
    expect(await q.ticket("t", "b", T0 + 1000)).toBeNull();
    expect(await q.ticket("t", "a", T0 + 11 * 60_000)).toBeNull();
  });
});

describe("visitor ids", () => {
  it("never contain the address and change every day", async () => {
    const a = await visitorId("203.0.113.7", "salt", T0);
    expect(a).toMatch(/^[0-9a-f]{24}$/);
    expect(a).not.toContain("203");
    expect(await visitorId("203.0.113.7", "salt", T0 + 3600_000)).toBe(a);
    expect(await visitorId("203.0.113.7", "salt", T0 + 86_400_000)).not.toBe(a);
    expect(await visitorId("203.0.113.8", "salt", T0)).not.toBe(a);
  });
});
