/**
 * Channel header: room name + present-peer count for a room view, or agent
 * name + online/last-seen for a DM view — plus the room's turn-state chip
 * (latest open expects/claimed message in the room). Ported from the
 * mockup's `renderHeader()` + `turnChip()`.
 */

import {
  ArrowLeftIcon,
  AtIcon,
  HashIcon,
  UsersThreeIcon,
} from "@phosphor-icons/react";
import type { Message } from "../state/contract";
import { lastSeen } from "../state/format";
import { AgentAvatar } from "./AgentAvatar";
import { expectsSince } from "./conversation-clock";
import { ClaimedBadge, ExpectsBadge } from "./MessageBadges";

/** Latest message in `room` carrying an open turn-state (expects or claimed). */
function latestTurn(messages: Message[], room: string): Message | undefined {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const m = messages[i];
    if (m.room !== room) {
      continue;
    }
    if (!m.expects_reply || m.expects_reply === "none") {
      continue;
    }
    return m;
  }
}

function TurnChip({ turn, now }: { turn: Message | undefined; now: number }) {
  if (!turn) {
    return null;
  }
  if (turn.claimed_by) {
    return <ClaimedBadge by={turn.claimed_by} />;
  }
  return (
    <ExpectsBadge
      expectsReply={turn.expects_reply as string}
      now={now}
      since={expectsSince(turn)}
    />
  );
}

export function ConversationHeader({
  room,
  dmAgent,
  dmOnline,
  dmSecondsSinceSeen,
  presentCount,
  messages,
  now,
  onBack,
}: {
  room: string;
  dmAgent: string | undefined;
  dmOnline: boolean;
  dmSecondsSinceSeen: number;
  presentCount: number;
  messages: Message[];
  now: number;
  onBack: () => void;
}) {
  return (
    <header className="conv-header">
      {dmAgent ? (
        <>
          <button
            aria-label="Back to room"
            className="conv-header__back"
            onClick={onBack}
            title={`Back to #${room}`}
            type="button"
          >
            <ArrowLeftIcon className="ph" size={16} />
          </button>
          <AgentAvatar
            dot={dmOnline ? "on" : "off"}
            name={dmAgent}
            round
            size="sm"
          />
          <span className="conv-header__name" data-testid="channel-title">
            {dmAgent}
          </span>
          <span className="conv-header__meta mono">
            {dmOnline
              ? `online · ${lastSeen(dmSecondsSinceSeen)}`
              : `offline · ${lastSeen(dmSecondsSinceSeen)} ago`}
          </span>
          <span
            className="conv-header__filterchip"
            title="Direct view = client-side filter over room messages"
          >
            <AtIcon className="ph" size={11} />
            filtered · #{room}
          </span>
        </>
      ) : (
        <>
          <HashIcon className="ph conv-header__hash" size={16} />
          <span className="conv-header__name" data-testid="channel-title">
            {room}
          </span>
          <span className="conv-header__sep" />
          <span className="conv-header__meta">
            <UsersThreeIcon className="ph" size={13} />
            <span>{presentCount}</span>
            <span className="conv-header__plabel">&nbsp;present</span>
          </span>
          <TurnChip now={now} turn={latestTurn(messages, room)} />
        </>
      )}
    </header>
  );
}
