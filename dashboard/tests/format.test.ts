import { describe, expect, it } from "vitest";
import { elapsedSince, lastSeen, parseExpires } from "../src/state/format";

describe("format", () => {
  it("lastSeen buckets", () => {
    expect(lastSeen(0)).toBe("now");
    expect(lastSeen(75)).toBe("1m");
  });

  it("lastSeen seconds bucket", () => {
    expect(lastSeen(12)).toBe("12s");
  });

  it("lastSeen hours bucket", () => {
    expect(lastSeen(3600)).toBe("1h");
  });

  it("parseExpires handles null as never", () => {
    expect(parseExpires(null)).toBe("never");
  });

  it("parseExpires passes through a label", () => {
    expect(parseExpires("6d 22h")).toBe("6d 22h");
  });

  it("elapsedSince mm:ss", () => {
    expect(elapsedSince(0, 7000)).toBe("0:07");
  });

  it("elapsedSince pads seconds and grows minutes", () => {
    expect(elapsedSince(0, 65_000)).toBe("1:05");
  });
});
