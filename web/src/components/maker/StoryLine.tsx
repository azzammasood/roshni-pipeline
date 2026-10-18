"use client";
// "The night it started": the maker's story as chapters hung on a power line that runs down the
// page. Each chapter's lamp lights (and stays lit) when the chapter scrolls into view; the last
// lamp is this page. Static HTML shows every chapter lit, so nothing depends on JavaScript.
import { useEffect, useRef, useState } from "react";
import { BulbArt } from "@/components/Bulb";

export type Chapter = { kicker: string; title: string; body: string };

export function StoryLine({ chapters, finale }: { chapters: Chapter[]; finale: string }) {
  const list = useRef<HTMLOListElement>(null);
  // null = not hydrated yet: render everything lit.
  const [lit, setLit] = useState<Set<number> | null>(null);

  useEffect(() => {
    const el = list.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const items = [...el.querySelectorAll<HTMLElement>("[data-chapter]")];
    // Once hydrated, chapters below the fold start dark.
    setLit(new Set(items.filter((it) => it.getBoundingClientRect().top < window.innerHeight * 0.6).map((it) => Number(it.dataset.chapter))));
    const io = new IntersectionObserver(
      (entries) => {
        const on = entries.filter((e) => e.isIntersecting).map((e) => Number((e.target as HTMLElement).dataset.chapter));
        if (on.length) setLit((prev) => new Set([...(prev ?? []), ...on]));
      },
      { rootMargin: "0px 0px -40% 0px" },
    );
    items.forEach((it) => io.observe(it));
    return () => io.disconnect();
  }, []);

  const isLit = (i: number) => lit === null || lit.has(i);
  const all = chapters.length;
  const progress = lit === null ? 1 : lit.size / (all + 1);

  return (
    <ol ref={list} className="story-line" style={{ "--progress": progress } as React.CSSProperties}>
      {chapters.map((c, i) => (
        <li key={c.title} data-chapter={i} className={`story-chapter ${isLit(i) ? "is-lit" : ""}`}>
          <span className="story-lamp" aria-hidden="true">
            <svg viewBox="0 0 40 48">
              <BulbArt />
            </svg>
          </span>
          <p className="story-kicker">{c.kicker}</p>
          <h2 className="headline story-title">{c.title}</h2>
          <p className="story-body">{c.body}</p>
        </li>
      ))}
      <li data-chapter={all} className={`story-chapter story-finale ${isLit(all) ? "is-lit" : ""}`}>
        <span className="story-lamp" aria-hidden="true">
          <svg viewBox="0 0 40 48">
            <BulbArt />
          </svg>
        </span>
        <p className="headline story-title">{finale}</p>
      </li>
    </ol>
  );
}
