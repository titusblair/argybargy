/**
 * Pinned composer: send-as identity (editable), target pill (room -> menu of
 * "everyone" + online peers in the room; dm -> locked to the agent),
 * expects-reply pill (click-to-cycle), text input, send button. Ported from
 * the mockup's `#composer` + `renderComposer()` / `buildToMenu()` / `send()`.
 *
 * `say()` throws on a non-ok response (see store.ts's `api()` helper) — the
 * send is wrapped in try/catch so a failure surfaces inline instead of
 * silently eating the message; the input is only cleared on success.
 *
 * DEV/fixture mode has no live relay behind `/admin/say`, so `say()`'s fetch
 * would reject every send. There, this optimistically appends the sent
 * message straight onto the local `state` signal (mirroring the mockup's
 * `send()`, which does `state.messages.push(m)`) before firing `say()` —
 * that POST still happens (and its rejection is swallowed) so the code path
 * matches production, but the timeline updates immediately either way.
 *
 * All event handlers are `useCallback`-wrapped per this repo's lint config
 * (ultracite's `noJsxPropsBind`), which flags any JSX handler prop that
 * isn't a stable reference — including plain function declarations
 * recreated each render, not just inline arrows.
 */

import { PaperPlaneRightIcon, UsersThreeIcon } from "@phosphor-icons/react";
import { useCallback } from "preact/hooks";
import type { AgentView } from "../state/presence";
import { hueFor } from "../state/presence";
import { say, state } from "../state/store";
import { AgentAvatar } from "./AgentAvatar";

export interface ComposerView {
  agent?: string;
  kind: "room" | "dm";
  room: string;
}

function hueClass(name: string): string {
  return `hue-${hueFor(name) % 5}`;
}

/** className for the target pill: locked+hued for a DM, hued for a targeted
 * room broadcast, plain for "everyone". */
function toPillClass(dmAgent: string | undefined, to: string): string {
  if (dmAgent) {
    return `conv-pill conv-pill--hued conv-pill--lock ${hueClass(dmAgent)}`;
  }
  if (to === "all") {
    return "conv-pill";
  }
  return `conv-pill conv-pill--hued ${hueClass(to)}`;
}

export function ConversationComposer({
  view,
  onlinePeersInRoom,
  text,
  setText,
  sendAs,
  setSendAs,
  to,
  setTo,
  expectsReply,
  setExpectsReply,
  error,
  setError,
  menuOpen,
  setMenuOpen,
  editingSendAs,
  setEditingSendAs,
}: {
  view: ComposerView;
  onlinePeersInRoom: AgentView[];
  text: string;
  setText: (v: string) => void;
  sendAs: string;
  setSendAs: (v: string) => void;
  to: string;
  setTo: (v: string) => void;
  expectsReply: string | null;
  setExpectsReply: (v: string | null) => void;
  error: string | null;
  setError: (v: string | null) => void;
  menuOpen: boolean;
  setMenuOpen: (v: boolean) => void;
  editingSendAs: boolean;
  setEditingSendAs: (v: boolean) => void;
}) {
  const dmAgent = view.kind === "dm" ? view.agent : undefined;
  const target = dmAgent ?? to;

  // biome-ignore lint/correctness/useExhaustiveDependencies: state.value is read in the body (dev-mode optimistic append) — the rule's default-fix strips it incorrectly
  const doSend = useCallback(async () => {
    const trimmed = text.trim();
    if (!trimmed) {
      return;
    }
    const payload = {
      expects_reply: expectsReply,
      room: view.room,
      sender: sendAs.trim() || "operator",
      text: trimmed,
      to: dmAgent ?? to,
    };
    try {
      if (import.meta.env.DEV && state.value) {
        // No live relay in dev/fixture mode — append locally so the
        // timeline updates immediately, then still fire say() below.
        state.value = {
          ...state.value,
          messages: [
            ...state.value.messages,
            {
              claimed_by: null,
              expects_reply: payload.expects_reply,
              from: payload.sender,
              room: payload.room,
              text: payload.text,
              to: payload.to,
            },
          ],
        };
      }
      await say(payload);
      setText("");
      setExpectsReply(null);
      setError(null);
    } catch {
      if (import.meta.env.DEV) {
        setText("");
        setExpectsReply(null);
        setError(null);
      } else {
        setError("Send failed — the relay rejected that message. Try again.");
      }
    }
  }, [
    text,
    expectsReply,
    view.room,
    sendAs,
    dmAgent,
    to,
    setText,
    setExpectsReply,
    setError,
    state.value,
  ]);

  const onInputChange = useCallback(
    (e: Event) => {
      setText((e.target as HTMLInputElement).value);
    },
    [setText]
  );

  const onInputKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        doSend();
      }
    },
    [doSend]
  );

  const cycleExpects = useCallback(() => {
    const cycle: (string | null)[] = [null, "anyone"];
    if (target !== "all") {
      cycle.push(target);
    }
    const cur = cycle.indexOf(expectsReply);
    setExpectsReply(cycle[(cur + 1) % cycle.length]);
  }, [target, expectsReply, setExpectsReply]);

  const pickTo = useCallback(
    (name: string) => {
      setTo(name);
      if (expectsReply && expectsReply !== "anyone" && expectsReply !== name) {
        setExpectsReply(null);
      }
      setMenuOpen(false);
    },
    [expectsReply, setTo, setExpectsReply, setMenuOpen]
  );

  const pickAll = useCallback(() => pickTo("all"), [pickTo]);

  const startEditingSendAs = useCallback(() => {
    setEditingSendAs(true);
  }, [setEditingSendAs]);

  const stopEditingSendAs = useCallback(() => {
    setEditingSendAs(false);
  }, [setEditingSendAs]);

  const onSendAsChange = useCallback(
    (e: Event) => {
      setSendAs((e.target as HTMLInputElement).value.trim() || sendAs);
    },
    [sendAs, setSendAs]
  );

  const onSendAsKeyDown = useCallback((e: KeyboardEvent) => {
    e.stopPropagation();
    if (e.key === "Enter") {
      (e.target as HTMLInputElement).blur();
    }
  }, []);

  const toggleToMenu = useCallback(() => {
    setMenuOpen(!menuOpen);
  }, [menuOpen, setMenuOpen]);

  return (
    <div className="conv-composer" data-testid="composer">
      {error ? (
        <div
          className="conv-composer__error"
          data-testid="composer-error"
          role="alert"
        >
          {error}
        </div>
      ) : null}
      <div className="conv-composer__frame">
        <input
          autoComplete="off"
          className="conv-composer__input"
          onInput={onInputChange}
          onKeyDown={onInputKeyDown}
          placeholder={
            dmAgent ? `Message @${dmAgent}` : `Message #${view.room}`
          }
          // biome-ignore lint/suspicious/noUnknownAttribute: Preact's InputHTMLAttributes types this lowercase ("spellcheck"), not React's camelCase
          spellcheck={false}
          value={text}
        />
        <div className="conv-composer__row">
          {editingSendAs ? (
            <input
              autoFocus
              className="conv-composer__as-input"
              maxLength={16}
              onBlur={stopEditingSendAs}
              onChange={onSendAsChange}
              onKeyDown={onSendAsKeyDown}
              // biome-ignore lint/suspicious/noUnknownAttribute: Preact's InputHTMLAttributes types this lowercase ("spellcheck"), not React's camelCase
              spellcheck={false}
              value={sendAs}
            />
          ) : (
            <button
              className="conv-pill"
              onClick={startEditingSendAs}
              title="Send-as identity — click to edit"
              type="button"
            >
              as <b>{sendAs}</b>
            </button>
          )}

          <div className="conv-composer__to-wrap">
            <button
              className={toPillClass(dmAgent, to)}
              disabled={Boolean(dmAgent)}
              onClick={toggleToMenu}
              title="Target — maps to the 'to' field"
              type="button"
            >
              → {dmAgent ?? (to === "all" ? "everyone" : to)}
            </button>
            {menuOpen && !dmAgent ? (
              <div className="conv-menu" data-testid="to-menu">
                <button
                  className="conv-menu__item"
                  onClick={pickAll}
                  type="button"
                >
                  <UsersThreeIcon className="ph" size={15} />
                  <span className="conv-menu__who">everyone</span>
                  <span className="conv-menu__k mono">to: all</span>
                </button>
                {onlinePeersInRoom.map((r) => (
                  <ToMenuItem key={r.name} name={r.name} onPick={pickTo} />
                ))}
              </div>
            ) : null}
          </div>

          <button
            className={`conv-pill ${expectsReply ? "conv-pill--armed" : ""}`}
            data-testid="expects-pill"
            onClick={cycleExpects}
            title="expects_reply — click to cycle"
            type="button"
          >
            expects · {expectsReply ?? "—"}
          </button>

          <button
            className={`conv-send ${text.trim() ? "conv-send--ready" : ""}`}
            data-testid="send-button"
            onClick={doSend}
            title="Send (Enter)"
            type="button"
          >
            <PaperPlaneRightIcon className="ph" size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}

/** One row in the target menu — its own component so `onClick` can be a
 * stable per-item callback without an inline arrow in the parent. */
function ToMenuItem({
  name,
  onPick,
}: {
  name: string;
  onPick: (name: string) => void;
}) {
  const onClick = useCallback(() => onPick(name), [onPick, name]);
  return (
    <button className="conv-menu__item" onClick={onClick} type="button">
      <AgentAvatar name={name} size="sm" />
      <span className="conv-menu__who">{name}</span>
      <span className="conv-menu__k mono">to: {name}</span>
    </button>
  );
}
