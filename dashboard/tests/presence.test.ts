import { describe, expect, it } from "vitest";
import { hueFor, reconcilePresence } from "../src/state/presence";

const S = (peers: any) => ({
  codes: [],
  hash_codes: false,
  messages: [],
  peers,
  public_url: "",
});

describe("presence", () => {
  it("marks a newly-appeared online peer justJoined", () => {
    const out = reconcilePresence(
      [],
      S({ mesh: [{ name: "hermes", online: true, seconds_since_seen: 0 }] })
    );
    expect(out[0].life).toBe("online");
    expect(out[0].justJoined).toBe(true);
  });

  it("keeps a dropped peer as fading before offline", () => {
    const prev = reconcilePresence(
      [],
      S({ mesh: [{ name: "qwen", online: true, seconds_since_seen: 0 }] })
    );
    const out = reconcilePresence(
      prev,
      S({ mesh: [{ name: "qwen", online: false, seconds_since_seen: 3 }] }),
      { fadeMs: 8000 }
    );
    expect(out[0].life).toBe("fading");
  });

  it("hue is stable per name and in range", () => {
    expect(hueFor("alice")).toBe(hueFor("alice"));
    expect(hueFor("alice")).toBeGreaterThanOrEqual(0);
    expect(hueFor("alice")).toBeLessThan(360);
  });
});
