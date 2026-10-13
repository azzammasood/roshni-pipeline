/** Scheduled windows [start, end) in minutes from hourly dark minutes (IESCO slots are whole
 *  hours). A run that ends at midnight joins one that starts at 00:00 (e.g. 23:00–01:00). */
export function hourWindows(mins: number[]): { start: number; end: number }[] {
  const runs: { start: number; end: number }[] = [];
  mins.forEach((m, h) => {
    if (m <= 0) return;
    const last = runs.at(-1);
    if (last && last.end === h * 60) last.end = h * 60 + 60;
    else runs.push({ start: h * 60, end: h * 60 + 60 });
  });
  const first = runs[0];
  const last = runs.at(-1);
  if (runs.length > 1 && first.start === 0 && last!.end === 1440) {
    runs.shift();
    last!.end = first.end;
  }
  return runs.sort((a, b) => a.start - b.start);
}
