/**
 * Badge grammar for a single message: expects-reply (amber, with a live
 * elapsed timer while unclaimed) and claimed (green, "by <name>"). Ported
 * from the mockup's `.pill.expects` / `.pill.claimed` (argy-dashboard-
 * mockup.html `msgHtml()` + `.pill` rules).
 *
 * A message is in exactly one of three states:
 *   - claimed_by set            -> claimed badge, no timer.
 *   - expects_reply set, open   -> expects badge + elapsed timer.
 *   - neither                   -> no badge (caller shouldn't render one).
 */

import { CheckIcon } from "@phosphor-icons/react";
import { elapsedSince } from "../state/format";

export function ClaimedBadge({ by }: { by: string }) {
  return (
    <span
      className="badge-pill badge-pill--claimed"
      data-badge="claimed"
      title={`claimed_by: "${by}"`}
    >
      <CheckIcon className="ph" size={10} weight="bold" />
      claimed · {by}
    </span>
  );
}

export function ExpectsBadge({
  expectsReply,
  since,
  now,
}: {
  expectsReply: string;
  since: number;
  now: number;
}) {
  const label = expectsReply === "anyone" ? "anyone" : expectsReply;
  return (
    <span
      className="badge-pill badge-pill--expects"
      data-badge="expects"
      title={`expects_reply: "${expectsReply}" · unclaimed`}
    >
      expects · {label}
      <span className="badge-pill__timer mono">{elapsedSince(since, now)}</span>
    </span>
  );
}
