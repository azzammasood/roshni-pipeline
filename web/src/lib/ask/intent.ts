// Questions about the visitor's own supply ("Will I get load shedding today?", "meri bijli kab
// jaye gi", "کیا آج میرے علاقے میں لوڈ شیڈنگ ہوگی؟") are not data questions: the answer is one
// feeder's schedule. They go to the site's own schedule engine (lib/darkNow, the same code as the
// home and My feeder pages, oracle-tested against Python) for the feeder pinned in this browser,
// or to the feeder finder when none is pinned. No language model and no quota are involved.
//
// Deterministic on purpose: a router that guesses wrong sends a personal question to the
// planner, which refuses it with a pointer back here (AskPanel), so a miss is never a wrong answer.

const POWER = [
  /\bload[\s-]?shedd?ing\b/,
  /\bloadshedding\b/,
  /\b(power|electricity|light|lights|bijli|bijlee|current)\b/,
  /\b(outage|outages|cut|cuts|shutdown|blackout)\b/,
  /لوڈ\s?شیڈنگ|بجلی|لائٹ/,
];
const PERSONAL = [
  /\b(i|i'll|i'm|me|my|mine|we|our|ours|us|here)\b/,
  /\b(mera|meri|mere|hamara|hamari|hamare|ham|hum|mujhe|humein|hamein|yahan)\b/,
  /میرا|میری|میرے|ہمارا|ہماری|ہمارے|مجھے|ہمیں|یہاں/,
];
const WHEN = [
  /\b(today|tonight|now|tomorrow|this (morning|afternoon|evening)|when will|when is|next)\b/,
  /\b(aaj|aj|abhi|kal|raat|kab)\b/,
  /آج|ابھی|کل|رات|کب/,
];
// Aggregate questions ("How many feeders have load shedding today?", "Which area do we have the
// most cuts in?") stay with the planner, even with "today" or "we" in them.
const AGGREGATE = [
  /\b(how many|which|most|least|average|total|count|per|every|list|compare|share|percent|rank|feeders|areas|year|years|month|months|history|trend|nepra|reported)\b/,
  /\b(kitne|kitni|konsa|konsi|sab)\b/,
  /کتنے|کتنی|کون سا|کون سی|سب سے/,
];

// Never the schedule engine: account questions (refused by the planner; Roshni never touches
// consumer records) and areas outside IESCO and K-Electric, which Roshni has no feeders for.
const ELSEWHERE = [
  /\b(bill|bills|reference number|ref no|consumer number|meter|account)\b/,
  /\b(lesco|mepco|fesco|gepco|pesco|hesco|sepco|qesco|tesco)\b/,
  /\b(lahore|multan|faisalabad|gujranwala|sialkot|peshawar|quetta|sukkur|hyderabad|bahawalpur)\b/,
  /بل|میٹر|ریفرنس|لاہور|ملتان|فیصل آباد|پشاور|کوئٹہ|سکھر|حیدرآباد/,
];

const any = (res: RegExp[], s: string) => res.some((r) => r.test(s));

/** True when the question asks about the visitor's own supply rather than about the data. */
export function isPersonalSchedule(question: string): boolean {
  const s = question.toLowerCase().replace(/[’`]/g, "'");
  if (!any(POWER, s)) return false;
  if (any(AGGREGATE, s) || any(ELSEWHERE, s)) return false;
  return any(PERSONAL, s) || any(WHEN, s);
}
