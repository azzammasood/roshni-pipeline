"use client";
import { useEffect, useState } from "react";
import type {
  DarkProfilesDocument,
  FeedersDocument,
  PlannedShutdownsDocument,
} from "@/types/v1";
import { documentUrl } from "./urls";

type ClientDocs = {
  feeders: FeedersDocument;
  dark_profiles: DarkProfilesDocument;
  planned_shutdowns: PlannedShutdownsDocument;
};

const pending = new Map<string, Promise<unknown>>();

function fetchDoc<K extends keyof ClientDocs>(doc: K): Promise<ClientDocs[K]> {
  if (!pending.has(doc)) {
    const p = fetch(documentUrl(doc)).then((r) => {
      if (!r.ok) throw new Error(`${doc}: HTTP ${r.status}`);
      return r.json();
    });
    p.catch(() => pending.delete(doc)); // allow a retry after a failure
    pending.set(doc, p);
  }
  return pending.get(doc) as Promise<ClientDocs[K]>;
}

export type LoadState<T> = { status: "loading" } | { status: "error" } | { status: "ready"; data: T };

/** Fetch export documents once per page load (shared between components). */
export function useExport<K extends keyof ClientDocs>(docs: readonly K[]) {
  const [state, setState] = useState<LoadState<Pick<ClientDocs, K>>>({ status: "loading" });
  const key = docs.join(",");
  useEffect(() => {
    let live = true;
    Promise.all(docs.map((d) => fetchDoc(d).then((v) => [d, v] as const)))
      .then((pairs) => live && setState({ status: "ready", data: Object.fromEntries(pairs) as Pick<ClientDocs, K> }))
      .catch(() => live && setState({ status: "error" }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}
