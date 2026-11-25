import type { Metadata } from "next";
import { fill } from "@/i18n/dictionaries";
import { loadDocument } from "@/lib/data";
import { num } from "@/lib/format";
import { resolveLocale } from "@/lib/locale";
import { Stamp } from "@/components/Clock";
import { ScrollRegion } from "@/components/ScrollRegion";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import type { Healing as HealingDoc } from "@/types/v1";

export async function generateMetadata({ params }: PageProps<"/[lang]/health">): Promise<Metadata> {
  return { title: (await resolveLocale(params)).dict.nav.health };
}

const RUNS_SHOWN = 60;
const DAYS_SHOWN = 45;

/** Pipeline health (export 1.9.0 `health`): the pipeline's own run records, built at publish. */
export default async function Health({ params }: PageProps<"/[lang]/health">) {
  const { locale, dict } = await resolveLocale(params);
  const t = dict.health;
  const h = (await loadDocument("health")).data;
  const n = (v: number) => num(v, locale);
  const minutes = (s: number) => fill(t.minutes, { m: n(Math.round((s / 60) * 10) / 10) }, locale);

  const runs = h.publish_runs.slice(-RUNS_SHOWN);
  const last = h.publish_runs.at(-1);
  const since = last ? Date.parse(last.started_at) - 30 * 86_400_000 : 0;
  const month = h.publish_runs.filter((r) => Date.parse(r.started_at) >= since);
  const ok = month.filter((r) => r.conclusion === "success");
  const durations = ok.map((r) => r.duration_seconds).sort((a, b) => a - b);
  const median = durations.length ? durations[Math.floor(durations.length / 2)] : null;
  const dbtTotal = h.dbt.passed + h.dbt.warned + h.dbt.failed + h.dbt.skipped;
  const days = h.fetch_days.slice(-DAYS_SHOWN);
  const first = h.sizes[0];
  const now = h.sizes.at(-1);
  const sizeNames = t.sizesNames as Record<string, string>;
  const heal = h.healing ?? null;

  const tiles: [React.ReactNode, string][] = [
    [
      last ? (last.conclusion === "success" ? t.succeeded : t.failed) : "–",
      t.lastRun,
    ],
    [month.length ? fill(t.successOf, { ok: n(ok.length), n: n(month.length) }, locale) : "–", t.successRate],
    [median !== null ? minutes(median) : "–", t.medianTime],
    [fill(t.passedOf, { ok: n(h.dbt.passed), n: n(dbtTotal) }, locale), t.dbtPassed],
    [fill(t.hours, { h: n(h.freshness_target_hours) }, locale), t.target],
  ];

  return (
    <article className="space-y-12">
      <header className="space-y-3 max-w-4xl">
        <p className="kicker">{t.kicker}</p>
        <h1 className="headline text-4xl sm:text-6xl">{t.title}</h1>
        <p className="text-lg max-w-prose">{t.intro}</p>
      </header>

      <dl className="rule grid grid-cols-2 sm:grid-cols-5 gap-x-6 gap-y-4 pt-4">
        {tiles.map(([value, label]) => (
          <div key={label} className="border-t border-line pt-2 flex flex-col-reverse">
            <dt className="text-sm">
              {label}
              {label === t.lastRun && last && (
                <span className="block text-muted">
                  <Stamp iso={last.started_at} />
                </span>
              )}
            </dt>
            <dd className="headline text-3xl tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>

      <section className="rule pt-4 space-y-3">
        <h2 id="runs" className="headline text-3xl">
          {t.runsTitle}
        </h2>
        <p className="text-sm max-w-prose">{t.runsNote}</p>
        {runs.length === 0 ? (
          <p className="text-muted">{t.noRuns}</p>
        ) : (
          <>
            <Bars
              label={t.runsLabel}
              bars={runs.map((r) => ({
                value: r.duration_seconds,
                failed: r.conclusion !== "success",
              }))}
            />
            <details>
              <summary className="link cursor-pointer text-sm">{t.showNumbers}</summary>
              <ScrollRegion label={t.runsTitle}>
                <table className="data mt-2">
                  <thead>
                    <tr>
                      <th scope="col">{t.started}</th>
                      <th scope="col">{t.duration}</th>
                      <th scope="col">{t.result}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...runs].reverse().map((r) => (
                      <tr key={r.url}>
                        <td className="whitespace-nowrap">
                          <Stamp iso={r.started_at} />
                        </td>
                        <td className="tabular-nums whitespace-nowrap">{minutes(r.duration_seconds)}</td>
                        <td>
                          {r.conclusion === "success" ? t.succeeded : t.failed}{" "}
                          <a href={r.url} className="link text-sm" rel="noopener noreferrer" target="_blank">
                            {t.openRun}
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </ScrollRegion>
            </details>
          </>
        )}
      </section>

      {days.length > 0 && (
        <section className="rule pt-4 space-y-3">
          <h2 id="fetch" className="headline text-3xl">
            {t.fetchTitle}
          </h2>
          <p className="text-sm max-w-prose">{t.fetchNote}</p>
          <Bars
            label={t.fetchLabel}
            bars={days.map((d) => ({ value: d.fetches, part: d.new_files, failed: d.errors > 0 }))}
          />
          <details>
            <summary className="link cursor-pointer text-sm">{t.showNumbers}</summary>
            <ScrollRegion label={t.fetchTitle}>
              <table className="data mt-2">
                <thead>
                  <tr>
                    <th scope="col">{t.date}</th>
                    <th scope="col">{t.fetches}</th>
                    <th scope="col">{t.newFiles}</th>
                    <th scope="col">{t.errors}</th>
                  </tr>
                </thead>
                <tbody>
                  {[...days].reverse().map((d) => (
                    <tr key={d.date}>
                      <td className="tabular-nums whitespace-nowrap" dir="ltr">
                        {d.date}
                      </td>
                      <td className="tabular-nums">{n(d.fetches)}</td>
                      <td className="tabular-nums">{n(d.new_files)}</td>
                      <td className="tabular-nums">{n(d.errors)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
          </details>
        </section>
      )}

      {first && now && (
        <section className="rule pt-4 space-y-3">
          <h2 id="sizes" className="headline text-3xl">
            {t.sizesTitle}
          </h2>
          <p className="text-sm max-w-prose">{fill(t.sizesNote, { date: first.date }, locale)}</p>
          <ScrollRegion label={t.sizesTitle}>
            <table className="data">
              <thead>
                <tr>
                  <th scope="col">{t.table}</th>
                  <th scope="col">{t.rowsNow}</th>
                  <th scope="col">{fill(t.since, { date: first.date }, locale)}</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(now.rows).map(([key, rows]) => {
                  const change = rows - (first.rows[key] ?? rows);
                  return (
                    <tr key={key}>
                      <th scope="row" className="font-normal">
                        {sizeNames[key] ?? key}
                      </th>
                      <td className="tabular-nums">{n(rows)}</td>
                      <td className="tabular-nums" dir="ltr">
                        {change > 0 ? "+" : ""}
                        {n(change)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </ScrollRegion>
        </section>
      )}

      <section className="rule pt-4 space-y-3">
        <h2 id="quality" className="headline text-3xl">
          {t.qualityTitle}
        </h2>
        <p className="text-sm max-w-prose">{t.qualityNote}</p>
        <ScrollRegion label={t.qualityTitle}>
          <table className="data">
            <thead>
              <tr>
                <th scope="col">{t.table}</th>
                <th scope="col">{t.kept}</th>
                <th scope="col">{t.quarantined}</th>
                <th scope="col">{t.reasons}</th>
              </tr>
            </thead>
            <tbody>
              {h.parsed.map((p) => (
                <tr key={p.table}>
                  <th scope="row" className="font-mono text-xs font-normal" dir="ltr">
                    {p.table}
                  </th>
                  <td className="tabular-nums">{n(p.rows)}</td>
                  <td className="tabular-nums">{n(p.quarantined)}</td>
                  <td className="text-sm" lang="en" dir="ltr">
                    {p.top_reasons.map((r) => `${r.reason} (${num(r.rows, locale)})`).join("; ") || "–"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      </section>

      {heal && <Healing heal={heal} t={t} n={n} locale={locale} />}
    </article>
  );
}


/** Self-healing parsers (export 1.10.0 `health.healing`): last check, learned aliases, chaos eval. */
function Healing({
  heal,
  t,
  n,
  locale,
}: {
  heal: HealingDoc;
  t: Dictionary["health"];
  n: (v: number) => string;
  locale: Locale;
}) {
  const c = heal.last_check;
  const ev = heal.eval;
  const tiles: [string, string][] = c
    ? [
        [n(c.workbooks), t.healChecked],
        [n(c.drifted), t.healDrifted],
        [n(c.healed), t.healHealed],
        [n(heal.aliases.length), t.healAliases],
      ]
    : [];
  return (
    <section className="rule pt-4 space-y-4">
      <h2 id="healing" className="headline text-3xl">
        {t.healTitle}
      </h2>
      <p className="text-sm max-w-prose">{t.healNote}</p>
      {c ? (
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-4">
          {tiles.map(([value, label]) => (
            <div key={label} className="border-t border-line pt-2 flex flex-col-reverse">
              <dt className="text-sm">
                {label}
                {label === t.healChecked && (
                  <span className="block text-muted">
                    {t.healCheckedAt} <Stamp iso={c.checked_at} />
                  </span>
                )}
              </dt>
              <dd className="headline text-3xl tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-muted">{t.healNoCheck}</p>
      )}

      <h3 className="headline text-2xl">{t.aliasesTitle}</h3>
      {heal.aliases.length === 0 ? (
        <p className="text-sm">{t.aliasesNone}</p>
      ) : (
        <ScrollRegion label={t.aliasesTitle}>
          <table className="data">
            <thead>
              <tr>
                <th scope="col">{t.aliasHeader}</th>
                <th scope="col">{t.aliasField}</th>
                <th scope="col">{t.aliasBy}</th>
              </tr>
            </thead>
            <tbody>
              {heal.aliases.map((a) => (
                <tr key={`${a.parser}:${a.header}`}>
                  <th scope="row" className="font-normal">
                    <bdi>{a.header}</bdi>
                  </th>
                  <td className="font-mono text-xs" dir="ltr">
                    {a.field}
                  </td>
                  <td className="text-sm" lang="en" dir="ltr">
                    {a.by}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      )}

      {ev && (
        <>
          <h3 className="headline text-2xl">{t.evalTitle}</h3>
          <p className="text-sm max-w-prose">
            {fill(t.evalNote, { date: ev.run_on, w: n(ev.workbooks) }, locale)}
          </p>
          <ScrollRegion label={t.evalTitle}>
            <table className="data">
              <thead>
                <tr>
                  <th scope="col">{t.evalModel}</th>
                  <th scope="col">{t.evalRecovered}</th>
                  <th scope="col">{t.evalDifferent}</th>
                  <th scope="col">{t.evalFailed}</th>
                  <th scope="col">{t.evalTokens}</th>
                  <th scope="col">{t.evalSeconds}</th>
                </tr>
              </thead>
              <tbody>
                {ev.models.map((r) => (
                  <tr key={r.model}>
                    <th scope="row" className="font-mono text-xs font-normal" dir="ltr">
                      {r.model}
                    </th>
                    <td className="tabular-nums">
                      {fill(t.recoveredOf, { ok: n(r.recovered), n: n(r.cases) }, locale)}
                    </td>
                    <td className="tabular-nums">{n(r.healed_but_different)}</td>
                    <td className="tabular-nums">{n(r.failed)}</td>
                    <td className="tabular-nums">{n(r.tokens_total)}</td>
                    <td className="tabular-nums">{r.latency_mean_s === null ? "–" : n(r.latency_mean_s)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        </>
      )}
    </section>
  );
}

type Bar = { value: number; part?: number; failed: boolean };

/** Bars scaled to the largest value; `part` is drawn darker inside its bar; a failed bar is red
 *  and carries a cross, so the state never depends on colour alone. Decorative: the table under
 *  each chart carries the numbers. */
function Bars({ bars, label }: { bars: Bar[]; label: string }) {
  const W = 600;
  const H = 120;
  const gap = 2;
  const max = Math.max(1, ...bars.map((b) => b.value));
  const w = W / bars.length;
  return (
    <figure className="m-0" dir="ltr">
      <svg viewBox={`0 0 ${W} ${H + 14}`} className="w-full h-36" role="img" aria-label={label}>
        <line x1={0} x2={W} y1={H} y2={H} className="stroke-line" strokeWidth={1} />
        {bars.map((b, i) => {
          const x = i * w + gap / 2;
          const h = Math.max(2, (b.value / max) * (H - 4));
          const ph = b.part ? Math.max(1, (b.part / max) * (H - 4)) : 0;
          return (
            <g key={i}>
              <rect x={x} y={H - h} width={Math.max(1, w - gap)} height={h} className={b.failed ? "fill-signal" : "fill-accent opacity-40"} />
              {ph > 0 && <rect x={x} y={H - ph} width={Math.max(1, w - gap)} height={ph} className="fill-accent" />}
              {b.failed && (
                <text x={x + (w - gap) / 2} y={H + 11} textAnchor="middle" className="fill-signal" fontSize={10}>
                  ×
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
