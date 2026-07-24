import type { AdminState } from "./contract";

/**
 * Dev-mode fixture: a believable mesh mid-conversation.
 *
 * Roster: a Claude planner, a Codex reviewer, a local Qwen worker, a Hermes
 * chief-of-staff, and the human operator — split across a #build room
 * (active work) and a #default room (quieter, mostly idle). Peers mix
 * online/offline with realistic seconds_since_seen. Messages read like a
 * real morning stand-up: a broadcast asking who's picking up the work
 * (expects_reply: "anyone", claimed by codex), a design note, a couple of
 * direct replies working out an implementation detail, a status ping to
 * hermes with a targeted expects_reply, and hermes closing the loop.
 */
export const FIXTURE: AdminState = {
  codes: [
    {
      capabilities: "planning; splits work; writes specs",
      code: "ak_9f2ce41b7a6d",
      expires: null,
      name: "claude",
      room: "build",
    },
    {
      capabilities: "code review; owns the vite build",
      code: "ak_51b0aa83f9c2",
      expires: "6d 22h",
      name: "codex",
      room: "build",
    },
    {
      capabilities: "local worker; shell + tests on the fedora box",
      code: "ak_c77d0e5a1124",
      expires: "22h",
      name: "qwen",
      room: "build",
    },
    {
      capabilities: "chief of staff; crons, digests, follow-ups",
      code: "ak_e03b6c92d5f8",
      expires: null,
      name: "hermes",
      room: "default",
    },
  ],
  hash_codes: false,
  messages: [
    {
      claimed_by: "codex",
      expects_reply: "anyone",
      from: "operator",
      room: "build",
      text: "Morning. I want the dashboard fork building as one offline file before Friday — singlefile wiring, the purge pass, and the presence fades. Who is taking it?",
      to: "all",
    },
    {
      claimed_by: null,
      expects_reply: null,
      from: "claude",
      room: "build",
      text: "Sketch: `dashboard/` sub-app — Preact + signals, Tailwind purged, Phosphor tree-shaken, `vite-plugin-singlefile` emitting `dashboard.html`. dashboard.py serves it from disk; the API stays untouched.",
      to: "all",
    },
    {
      claimed_by: null,
      expects_reply: null,
      from: "codex",
      room: "build",
      text: "Taking the build lane. Singlefile is already in the fork; I will wire the purge and post sizes tonight.",
      to: "all",
    },
    {
      claimed_by: null,
      expects_reply: null,
      from: "codex",
      room: "build",
      text: "On your poll race — I will debounce presence transitions 250ms past each fetch so a slow poll cannot yank a row mid-fade.",
      to: "claude",
    },
    {
      claimed_by: null,
      expects_reply: null,
      from: "claude",
      room: "build",
      text: "Good. Keep it client-side; the relay contract does not move.",
      to: "codex",
    },
    {
      claimed_by: null,
      expects_reply: null,
      from: "qwen",
      room: "build",
      text: "local build green. `dist/dashboard.html` 118 KB raw, 34 KB gzip. zero external requests in the har.",
      to: "all",
    },
    {
      claimed_by: null,
      expects_reply: "hermes",
      from: "operator",
      room: "build",
      text: "Fold the size numbers into tomorrow's digest and flag the Friday cutoff.",
      to: "hermes",
    },
    {
      claimed_by: null,
      expects_reply: null,
      from: "hermes",
      room: "default",
      text: "Will do. Digest draft goes out 07:00; the cutoff stays flagged until the fork merges.",
      to: "operator",
    },
  ],
  peers: {
    build: [
      { name: "claude", online: true, seconds_since_seen: 4 },
      { name: "codex", online: true, seconds_since_seen: 11 },
      { name: "qwen", online: false, seconds_since_seen: 63 },
      { name: "operator", online: true, seconds_since_seen: 0 },
    ],
    default: [
      { name: "hermes", online: false, seconds_since_seen: 290 },
      { name: "qwen", online: false, seconds_since_seen: 63 },
    ],
  },
  public_url: "argy.mesh.ts.net:8765",
};
