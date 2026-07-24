import { describe, expect, it } from "vitest";
import { FIXTURE } from "../src/state/fixture";

describe("fixture", () => {
  it("matches AdminState shape with a mix of online/offline peers and >=1 expecting message", () => {
    const peers = Object.values(FIXTURE.peers).flat();
    expect(peers.some((p) => p.online)).toBe(true);
    expect(peers.some((p) => !p.online)).toBe(true);
    expect(
      FIXTURE.messages.some(
        (m) => m.expects_reply && m.expects_reply !== "none"
      )
    ).toBe(true);
    expect(FIXTURE.messages.some((m) => m.claimed_by)).toBe(true);
    expect(typeof FIXTURE.public_url).toBe("string");
  });
});
