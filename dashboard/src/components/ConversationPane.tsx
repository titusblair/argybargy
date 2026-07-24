/**
 * ConversationPane — channel header + message timeline + composer. Prop-
 * less: reads `view`, `state`, `agents`, and the `say` action from
 * `state/store.ts` directly. Ported from the locked mockup's main pane
 * (`#chead` + `#timeline` + `#composer` in argy-dashboard-mockup.html).
 *
 * Sub-components live alongside this file (Conversation- and Message-
 * prefixed names, per the lane-isolation contract for this task):
 *   - ConversationHeader   — room/DM header + turn-state chip.
 *   - ConversationTimeline — grouped message list + badges.
 *   - ConversationComposer — send-as / target / expects / input / send.
 *   - MessageBadges        — expects/claimed pill grammar.
 *   - conversation-clock   — shared client-stamped expects-arrival times.
 */

import { useCallback, useEffect, useRef, useState } from "preact/hooks";
import { dmMessages, roomMessages } from "../state/filters";
import { agents, state, view as viewSignal } from "../state/store";
import "./ConversationPane.css";
import { ConversationComposer } from "./ConversationComposer";
import { ConversationHeader } from "./ConversationHeader";
import { ConversationTimeline } from "./ConversationTimeline";

export interface View {
  agent?: string;
  kind: "room" | "dm";
  room: string;
}

/** Exposes a dev-only hook so Playwright can drive `view` without a sidebar. */
function installDevViewHook() {
  if (!import.meta.env.DEV) {
    return;
  }
  (window as unknown as { __setView?: (v: View) => void }).__setView = (
    v: View
  ) => {
    viewSignal.value = v;
  };
}
installDevViewHook();

/** Pixel slop under which the timeline is considered "scrolled to bottom". */
const BOTTOM_SLOP_PX = 32;

export function ConversationPane() {
  const view = viewSignal.value;
  const current = state.value;

  // Local 1s clock — drives the expects-elapsed timers without re-running
  // the poll loop. Mirrors the mockup's `setInterval(tick, 1000)`.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  // Composer-local state — lives here (not in ConversationComposer) so a
  // room/DM switch can reset the target cleanly.
  const [text, setText] = useState("");
  const [sendAs, setSendAs] = useState("operator");
  const [to, setTo] = useState("all");
  const [expectsReply, setExpectsReply] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [editingSendAs, setEditingSendAs] = useState(false);

  const timelineRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  const dmAgent = view.kind === "dm" ? view.agent : undefined;

  let messages: ReturnType<typeof roomMessages>;
  if (!current) {
    messages = [];
  } else if (dmAgent) {
    messages = dmMessages(current, view.room, dmAgent);
  } else {
    messages = roomMessages(current, view.room);
  }

  // Auto-scroll to bottom on new messages, but only if the user was already
  // at (or near) the bottom — otherwise hold their scroll position. `messages`
  // isn't read in the body; it's a trigger dep so this re-runs whenever the
  // derived message list changes identity (new send, room/DM switch, poll).
  // biome-ignore lint/correctness/useExhaustiveDependencies: messages is a trigger-only dep (new list identity => re-scroll), not read in the body
  useEffect(() => {
    const el = timelineRef.current;
    if (!el) {
      return;
    }
    if (stickToBottom.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages]);

  const onTimelineScroll = useCallback(() => {
    const el = timelineRef.current;
    if (!el) {
      return;
    }
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickToBottom.current = distanceFromBottom <= BOTTOM_SLOP_PX;
  }, []);

  // biome-ignore lint/correctness/useExhaustiveDependencies: view.room is read in the body — the rule's default-fix strips it incorrectly
  const onBack = useCallback(() => {
    viewSignal.value = { kind: "room", room: view.room };
  }, [view.room]);

  const dmPeer = dmAgent
    ? (agents.value.find((a) => a.name === dmAgent && a.room === view.room) ??
      agents.value.find((a) => a.name === dmAgent))
    : undefined;

  const presentCount = agents.value.filter(
    (a) => a.online && a.room === view.room
  ).length;

  const onlinePeersInRoom = agents.value.filter(
    (a) => a.online && a.room === view.room && a.name !== "operator"
  );

  const emptyRoomLabel = `Nothing in #${view.room} yet`;

  return (
    <main
      aria-label="Conversation"
      className="conv-pane"
      data-testid="conversation-pane"
    >
      <ConversationHeader
        dmAgent={dmAgent}
        dmOnline={dmPeer?.online ?? false}
        dmSecondsSinceSeen={dmPeer?.secondsSinceSeen ?? 0}
        messages={current?.messages ?? []}
        now={now}
        onBack={onBack}
        presentCount={presentCount}
        room={view.room}
      />

      <ConversationTimeline
        dmAgent={dmAgent}
        emptyRoomLabel={emptyRoomLabel}
        messages={messages}
        now={now}
        onScroll={onTimelineScroll}
        timelineRef={timelineRef}
      />

      <ConversationComposer
        editingSendAs={editingSendAs}
        error={error}
        expectsReply={expectsReply}
        menuOpen={menuOpen}
        onlinePeersInRoom={onlinePeersInRoom}
        sendAs={sendAs}
        setEditingSendAs={setEditingSendAs}
        setError={setError}
        setExpectsReply={setExpectsReply}
        setMenuOpen={setMenuOpen}
        setSendAs={setSendAs}
        setText={setText}
        setTo={setTo}
        text={text}
        to={to}
        view={view}
      />
    </main>
  );
}
