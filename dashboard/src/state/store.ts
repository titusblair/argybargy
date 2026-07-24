/**
 * Argybargy admin dashboard store — signals, poll loop, admin actions.
 *
 * Talks to the server described in `contract.ts`. All write endpoints send
 * header `X-Admin-Token: <token>`; the token is persisted to
 * `localStorage["cc_admin"]`.
 *
 * `agents` reconciles server state into presence view models via
 * `reconcilePresence` (see `presence.ts`). That function is pure and derives
 * lifecycle (`life`) and the one-shot `justJoined` pulse from the *previous*
 * call's output, so this module keeps the last computed `AgentView[]` in a
 * module-level ref (`prevAgents`) and threads it back in on every
 * recomputation — never calls `reconcilePresence` with `[]`.
 */

import { computed, signal } from "@preact/signals";
import type { AdminState } from "./contract";
import { type AgentView, reconcilePresence } from "./presence";

const TOKEN_KEY = "cc_admin";

export const token = signal<string>(localStorage.getItem(TOKEN_KEY) ?? "");
export const state = signal<AdminState | null>(null);
export const connection = signal<"idle" | "live" | "error">("idle");
export const view = signal<{
  kind: "room" | "dm";
  room: string;
  agent?: string;
}>({
  kind: "room",
  room: "build",
});

// Threaded back into reconcilePresence on every recompute — see module
// docblock. Updated only inside the `agents` computed, which re-runs
// whenever `state` changes.
let prevAgents: AgentView[] = [];

export const agents = computed<AgentView[]>(() => {
  const current = state.value;
  if (!current) {
    return prevAgents;
  }
  const next = reconcilePresence(prevAgents, current);
  prevAgents = next;
  return next;
});

/** Persists the admin token and updates the signal. */
export function setToken(t: string): void {
  token.value = t;
  localStorage.setItem(TOKEN_KEY, t);
}

/** Shared POST helper for admin actions: JSON body + X-Admin-Token header. */
async function api(path: string, body: unknown): Promise<unknown> {
  const res = await fetch(path, {
    body: JSON.stringify(body),
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Token": token.value,
    },
    method: "POST",
  });
  return res.json();
}

/** GET /admin/state, updates `state` and flips `connection`. */
export async function poll(): Promise<void> {
  try {
    const res = await fetch("/admin/state", {
      headers: { "X-Admin-Token": token.value },
    });
    if (!res.ok) {
      connection.value = "error";
      return;
    }
    state.value = (await res.json()) as AdminState;
    connection.value = "live";
  } catch {
    connection.value = "error";
  }
}

/** Starts polling every `ms` (default 3000). Returns a function that stops it. */
export function startPolling(ms = 3000): () => void {
  const id = setInterval(() => {
    poll().catch(() => {
      // poll() already routes failures into connection.value = "error";
      // this catch only guards setInterval's callback from an unhandled
      // rejection warning.
    });
  }, ms);
  return () => clearInterval(id);
}

export async function say(p: {
  text: string;
  room: string;
  sender: string;
  to: string;
  expects_reply: string | null;
}): Promise<void> {
  await api("/admin/say", p);
}

export function invite(p: {
  name: string;
  room: string;
  expires: string | null;
  capabilities: string | null;
}): Promise<unknown> {
  return api("/admin/invite", p);
}

export async function revoke(target: string): Promise<void> {
  await api("/admin/revoke", { target });
}

/** POSTs /admin/regenerate-token, persists and returns the new admin token. */
export async function regenerate(): Promise<string> {
  const result = (await api("/admin/regenerate-token", {})) as {
    admin_token: string;
  };
  setToken(result.admin_token);
  return result.admin_token;
}
