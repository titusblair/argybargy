import type { AdminState } from "./contract";

export type Life = "online" | "fading" | "offline";

export interface AgentView {
  hue: number;
  justJoined: boolean;
  life: Life;
  name: string;
  online: boolean;
  room: string;
  secondsSinceSeen: number;
}

function key(room: string, name: string): string {
  return `${room}/${name}`;
}

const HASH_MODULUS = 2 ** 31;

/** Stable 0-359 hue derived from a name hash — same name always same hue. */
export function hueFor(name: string): number {
  let hash = 0;
  for (const char of name) {
    hash = (hash * 31 + char.charCodeAt(0)) % HASH_MODULUS;
  }
  return hash % 360;
}

/**
 * Diffs the previous view list against fresh server state to produce the
 * merged agent list with lifecycle (`life`) and join-pulse (`justJoined`)
 * flags.
 *
 * Keyed by `room/name`. `justJoined` is true exactly when a key transitions
 * absent-or-offline -> online. `life` is `"online"` while the peer reports
 * online; once it goes offline, `life` stays `"fading"` until
 * `seconds_since_seen` (the server's own clock, in seconds) exceeds
 * `fadeMs`, then it becomes `"offline"`.
 */
export function reconcilePresence(
  prev: AgentView[],
  state: AdminState,
  opts?: { fadeMs?: number }
): AgentView[] {
  const fadeMs = opts?.fadeMs ?? 8000;

  const prevByKey = new Map<string, AgentView>();
  for (const view of prev) {
    prevByKey.set(key(view.room, view.name), view);
  }

  const out: AgentView[] = [];

  for (const [room, roomPeers] of Object.entries(state.peers)) {
    for (const peer of roomPeers) {
      const previous = prevByKey.get(key(room, peer.name));
      const wasOnline = previous?.online ?? false;
      const justJoined = peer.online && !wasOnline;

      let life: Life;
      if (peer.online) {
        life = "online";
      } else {
        const offlineMs = peer.seconds_since_seen * 1000;
        life = offlineMs >= fadeMs ? "offline" : "fading";
      }

      out.push({
        hue: hueFor(peer.name),
        justJoined,
        life,
        name: peer.name,
        online: peer.online,
        room,
        secondsSinceSeen: peer.seconds_since_seen,
      });
    }
  }

  return out;
}
