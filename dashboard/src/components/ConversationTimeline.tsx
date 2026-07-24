/**
 * Message timeline: groups consecutive messages from the same sender into
 * one avatar block (ported from the mockup's `renderTimeline()` /
 * `.grp` grouping), styles the operator distinctly (`.grp.op` / `.oppill`),
 * and renders the badge grammar per-message via `MessageBadges`.
 *
 * The wire contract (`contract.ts`) has no per-message timestamp, so the
 * Ops-Deck expects-elapsed timer needs a client-stamped arrival time. We
 * keep a module-level `WeakMap<Message, number>` recording "first time this
 * message object was observed with an open expects_reply" — mirroring the
 * mockup's `expectsAt` Map (mockup comment: "production records first-poll
 * arrival"). Because `state.value` messages are stable object references
 * until a fresh poll/fixture reset, this survives re-renders but naturally
 * resets on reload — matching the mockup's intent.
 */

import { HashIcon } from "@phosphor-icons/react";
import type { ComponentChild, RefObject } from "preact";
import type { Message } from "../state/contract";
import { hueFor } from "../state/presence";
import { AgentAvatar, brandVars } from "./AgentAvatar";
import { brandAccent } from "./agent-logos";
import { expectsSince, messageKey } from "./conversation-clock";
import { ClaimedBadge, ExpectsBadge } from "./MessageBadges";

function hueClass(name: string, isOperator: boolean): string {
  return isOperator ? "hue-op" : `hue-${hueFor(name) % 5}`;
}

/** The author name for a message group — brand color for a known vendor
 * (logo + name = one identity), the hue tint otherwise, and plain --text
 * for the operator. Mirrors the accent logic in AgentAvatar. */
function AuthorName({
  name,
  isOperator,
}: {
  name: string;
  isOperator: boolean;
}) {
  const brand = !isOperator && brandAccent(name);
  if (brand) {
    return (
      <span
        className="conv-group__name is-brand"
        style={brandVars(brand) as never}
      >
        {name}
      </span>
    );
  }
  return (
    <span
      className={`conv-group__name ${isOperator ? "" : hueClass(name, false)}`}
    >
      {name}
    </span>
  );
}

function DirectedTo({
  to,
  hideWhen,
}: {
  to: string;
  hideWhen: string | undefined;
}) {
  if (!to || to === "all" || to === hideWhen) {
    return null;
  }
  return <span className={`conv-dir ${hueClass(to, false)}`}>→ {to}</span>;
}

function MessageBody({
  message,
  now,
  dmAgent,
}: {
  message: Message;
  now: number;
  dmAgent: string | undefined;
}) {
  let badge: ComponentChild = null;
  if (message.claimed_by) {
    badge = <ClaimedBadge by={message.claimed_by} />;
  } else if (message.expects_reply && message.expects_reply !== "none") {
    badge = (
      <ExpectsBadge
        expectsReply={message.expects_reply}
        now={now}
        since={expectsSince(message)}
      />
    );
  }

  return (
    <div className="conv-msg">
      <DirectedTo hideWhen={dmAgent} to={message.to} />
      {message.text}
      {badge}
    </div>
  );
}

interface MessageGroup {
  isOperator: boolean;
  messages: Message[];
  sender: string;
}

function groupBySender(messages: Message[]): MessageGroup[] {
  const groups: MessageGroup[] = [];
  for (const m of messages) {
    const last = groups.at(-1);
    if (last && last.sender === m.from) {
      last.messages.push(m);
    } else {
      groups.push({
        isOperator: m.from === "operator",
        messages: [m],
        sender: m.from,
      });
    }
  }
  return groups;
}

export function ConversationTimeline({
  messages,
  now,
  dmAgent,
  emptyRoomLabel,
  timelineRef,
  onScroll,
}: {
  messages: Message[];
  now: number;
  dmAgent: string | undefined;
  emptyRoomLabel: string;
  timelineRef: RefObject<HTMLDivElement>;
  onScroll: () => void;
}) {
  if (messages.length === 0) {
    return (
      <div className="conv-timeline" onScroll={onScroll} ref={timelineRef}>
        <div className="conv-empty">
          <HashIcon className="ph" size={36} />
          <div className="conv-empty__t1">{emptyRoomLabel}</div>
          <div className="conv-empty__t2">
            Messages agents send here will show up live.
          </div>
        </div>
      </div>
    );
  }

  const groups = groupBySender(messages);

  return (
    <div
      className="conv-timeline"
      data-testid="timeline"
      onScroll={onScroll}
      ref={timelineRef}
    >
      <div className="conv-daydiv">
        <span>today</span>
      </div>
      {groups.map((group) => (
        <div
          className={`conv-group ${group.isOperator ? "conv-group--op" : ""}`}
          key={messageKey(group.messages[0])}
        >
          <AgentAvatar name={group.sender} size="lg" />
          <div className="conv-group__body">
            <div className="conv-group__head">
              <AuthorName isOperator={group.isOperator} name={group.sender} />
              {group.isOperator ? (
                <span className="conv-oppill">operator</span>
              ) : null}
            </div>
            {group.messages.map((m) => (
              <MessageBody
                dmAgent={dmAgent}
                key={messageKey(m)}
                message={m}
                now={now}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
