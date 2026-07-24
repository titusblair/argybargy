/**
 * Client-stamped arrival time for open expects_reply messages, shared
 * between ConversationHeader (turn chip) and ConversationTimeline (per-
 * message badge) so both timers agree on when a given message first showed
 * up as unanswered. Mirrors the mockup's `expectsAt` Map (mockup comment:
 * "production records first-poll arrival") — the wire contract has no
 * per-message timestamp, so this is a client-side WeakMap keyed by message
 * object identity. Message objects are stable across re-renders until a
 * fresh poll/fixture reset replaces `state.value`.
 */

import type { Message } from "../state/contract";

const expectsAt = new WeakMap<Message, number>();

/** First-observed arrival time (epoch ms) for an open expects_reply message. */
export function expectsSince(m: Message): number {
  const existing = expectsAt.get(m);
  if (existing !== undefined) {
    return existing;
  }
  const now = Date.now();
  expectsAt.set(m, now);
  return now;
}

/**
 * Stable synthetic id per message object, for React/Preact `key` props —
 * lets the timeline key list items without falling back to array index
 * (message text/sender/to can legitimately repeat). Same object-identity
 * reasoning as `expectsSince` above.
 */
const messageIds = new WeakMap<Message, number>();
let nextMessageId = 0;

export function messageKey(m: Message): number {
  const existing = messageIds.get(m);
  if (existing !== undefined) {
    return existing;
  }
  const id = nextMessageId;
  nextMessageId += 1;
  messageIds.set(m, id);
  return id;
}
