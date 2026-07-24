/**
 * Pure formatting helpers for presence timestamps, expiry labels, and
 * elapsed-time timers. No side effects, no clock reads — callers pass `now`.
 */

/** "now" | "<n>s" | "<n>m" | "<n>h" bucketed from a seconds-since-seen count. */
export function lastSeen(seconds: number): string {
  if (seconds < 1) {
    return "now";
  }
  if (seconds < 60) {
    return `${Math.floor(seconds)}s`;
  }
  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}m`;
  }
  return `${Math.floor(seconds / 3600)}h`;
}

/** mm:ss elapsed between an epoch-ms start and `now`, e.g. "0:07", "1:05". */
export function elapsedSince(epochMs: number, now: number): string {
  const totalSeconds = Math.max(0, Math.floor((now - epochMs) / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}
