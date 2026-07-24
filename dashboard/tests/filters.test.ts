import { describe, expect, it } from "vitest";
import { dmMessages, roomList, roomMessages } from "../src/state/filters";
import { FIXTURE } from "../src/state/fixture";

describe("filters", () => {
  it("roomList is the sorted union", () => {
    expect(roomList(FIXTURE)).toContain("build");
  });

  it("roomList is stable-sorted and deduped across peers keys + codes[].room", () => {
    expect(roomList(FIXTURE)).toEqual(["build", "default"]);
  });

  it("roomMessages returns only messages for that room", () => {
    const msgs = roomMessages(FIXTURE, "default");
    expect(msgs.every((m) => m.room === "default")).toBe(true);
    expect(msgs.length).toBeGreaterThan(0);
  });

  it("dmMessages returns only messages touching the agent", () => {
    const dm = dmMessages(FIXTURE, "build", "codex");
    expect(dm.every((m) => m.from === "codex" || m.to === "codex")).toBe(true);
    expect(dm.length).toBeGreaterThan(0);
  });

  it("dmMessages is scoped to the given room", () => {
    const dm = dmMessages(FIXTURE, "build", "codex");
    expect(dm.every((m) => m.room === "build")).toBe(true);
  });
});
