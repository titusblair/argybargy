/**
 * Argybargy admin data contract.
 *
 * Mirrors the real server (`argybargy/dashboard.py`) exactly. This shape is
 * frozen — do not add, rename, or remove fields without updating the server.
 *
 * Endpoints:
 * - GET  /admin/state              -> AdminState
 * - POST /admin/invite   {name, room, expires, capabilities}
 *                                   -> {name, room, code, url, instruction}
 * - POST /admin/say      {text, room, sender, to, expects_reply}
 * - POST /admin/revoke   {target}
 * - POST /admin/regenerate-token   -> {admin_token}
 *
 * All write endpoints send header `X-Admin-Token: <token>`.
 */

export interface Peer {
  name: string;
  online: boolean;
  seconds_since_seen: number;
}

export interface Code {
  capabilities: string | null;
  code: string;
  expires: string | null;
  name: string;
  room: string;
}

export interface Message {
  claimed_by: string | null;
  expects_reply: string | null;
  from: string;
  room: string;
  text: string;
  to: string;
}

export interface AdminState {
  codes: Code[];
  hash_codes: boolean;
  messages: Message[];
  peers: Record<string, Peer[]>;
  public_url: string;
}
