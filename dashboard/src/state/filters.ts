import type { AdminState, Message } from "./contract";

/** Union of `peers` keys and `codes[].room`, stable-sorted. */
export function roomList(state: AdminState): string[] {
  const rooms = new Set<string>();
  for (const room of Object.keys(state.peers)) {
    rooms.add(room);
  }
  for (const code of state.codes) {
    rooms.add(code.room);
  }
  return [...rooms].sort((a, b) => a.localeCompare(b));
}

/** All messages posted in `room`. */
export function roomMessages(state: AdminState, room: string): Message[] {
  return state.messages.filter((m) => m.room === room);
}

/** Messages in `room` where `agent` is either the sender or the recipient. */
export function dmMessages(
  state: AdminState,
  room: string,
  agent: string
): Message[] {
  return roomMessages(state, room).filter(
    (m) => m.from === agent || m.to === agent
  );
}
