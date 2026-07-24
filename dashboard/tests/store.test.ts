import { beforeEach, describe, expect, it, vi } from "vitest";

// `localStorage` is polyfilled globally by vitest.setup.ts.

beforeEach(() => {
  localStorage.clear();
  vi.resetModules();
});

/** Last call args for a vi.fn(), without a non-null assertion. */
function lastCall(
  mock: ReturnType<typeof vi.fn>
): [string, { headers: Record<string, string>; body: string }] {
  const { calls } = mock.mock;
  const call = calls.at(-1);
  if (!call) {
    throw new Error("expected at least one call");
  }
  return call as [string, { headers: Record<string, string>; body: string }];
}

describe("store", () => {
  it("poll stores state and flips connection to live", async () => {
    const body = {
      codes: [],
      hash_codes: false,
      messages: [],
      peers: { build: [{ name: "x", online: true, seconds_since_seen: 0 }] },
      public_url: "u",
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({ json: async () => body, ok: true, status: 200 })
    );
    const s = await import("../src/state/store");
    s.setToken("tok");
    await s.poll();
    expect(s.connection.value).toBe("live");
    expect(s.agents.value[0].name).toBe("x");
  });

  it("poll flips connection to error on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({ json: async () => ({}), ok: false, status: 500 })
    );
    const s = await import("../src/state/store");
    s.setToken("tok");
    await s.poll();
    expect(s.connection.value).toBe("error");
  });

  it("poll flips connection to error when fetch throws", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("network down"))
    );
    const s = await import("../src/state/store");
    s.setToken("tok");
    await s.poll();
    expect(s.connection.value).toBe("error");
  });

  it("agents computed threads prev through reconcilePresence (justJoined pulses once)", async () => {
    // Each call builds a fresh body object, mirroring real fetch().json()
    // (a new object every response) — a shared/reused object reference would
    // mask a real bug via the signals library's same-reference no-op skip.
    const makeOffline = () => ({
      codes: [],
      hash_codes: false,
      messages: [],
      peers: { build: [{ name: "x", online: false, seconds_since_seen: 100 }] },
      public_url: "u",
    });
    const makeOnline = () => ({
      codes: [],
      hash_codes: false,
      messages: [],
      peers: { build: [{ name: "x", online: true, seconds_since_seen: 0 }] },
      public_url: "u",
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        json: async () => makeOffline(),
        ok: true,
        status: 200,
      })
      .mockResolvedValueOnce({
        json: async () => makeOnline(),
        ok: true,
        status: 200,
      })
      .mockResolvedValueOnce({
        json: async () => makeOnline(),
        ok: true,
        status: 200,
      });
    vi.stubGlobal("fetch", fetchMock);
    const s = await import("../src/state/store");
    s.setToken("tok");

    await s.poll();
    expect(s.agents.value[0].online).toBe(false);

    await s.poll();
    expect(s.agents.value[0].online).toBe(true);
    expect(s.agents.value[0].justJoined).toBe(true);

    // Third poll with the peer still online: justJoined must NOT still be
    // true — proves prev is threaded module-to-module, not reset to [].
    await s.poll();
    expect(s.agents.value[0].justJoined).toBe(false);
  });

  it("setToken persists to localStorage under cc_admin", async () => {
    const s = await import("../src/state/store");
    s.setToken("abc123");
    expect(localStorage.getItem("cc_admin")).toBe("abc123");
    expect(s.token.value).toBe("abc123");
  });

  it("say POSTs to /admin/say with X-Admin-Token and correct body", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ json: async () => ({}), ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);
    const s = await import("../src/state/store");
    s.setToken("tok");
    await s.say({
      expects_reply: null,
      room: "build",
      sender: "operator",
      text: "hi",
      to: "all",
    });
    const [url, opts] = lastCall(fetchMock);
    expect(url).toBe("/admin/say");
    expect(opts.headers["X-Admin-Token"]).toBe("tok");
    expect(JSON.parse(opts.body)).toMatchObject({ text: "hi", to: "all" });
  });

  it("invite POSTs to /admin/invite with X-Admin-Token and correct body, returns json", async () => {
    const responseBody = {
      code: "c",
      instruction: "i",
      name: "n",
      room: "build",
      url: "u",
    };
    const fetchMock = vi.fn().mockResolvedValue({
      json: async () => responseBody,
      ok: true,
      status: 200,
    });
    vi.stubGlobal("fetch", fetchMock);
    const s = await import("../src/state/store");
    s.setToken("tok");
    const result = await s.invite({
      capabilities: null,
      expires: null,
      name: "n",
      room: "build",
    });
    const [url, opts] = lastCall(fetchMock);
    expect(url).toBe("/admin/invite");
    expect(opts.headers["X-Admin-Token"]).toBe("tok");
    expect(JSON.parse(opts.body)).toMatchObject({ name: "n", room: "build" });
    expect(result).toEqual(responseBody);
  });

  it("revoke POSTs to /admin/revoke with X-Admin-Token and correct body", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ json: async () => ({}), ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);
    const s = await import("../src/state/store");
    s.setToken("tok");
    await s.revoke("target-name");
    const [url, opts] = lastCall(fetchMock);
    expect(url).toBe("/admin/revoke");
    expect(opts.headers["X-Admin-Token"]).toBe("tok");
    expect(JSON.parse(opts.body)).toMatchObject({ target: "target-name" });
  });

  it("regenerate POSTs to /admin/regenerate-token, persists and returns the new token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      json: async () => ({ admin_token: "new-tok" }),
      ok: true,
      status: 200,
    });
    vi.stubGlobal("fetch", fetchMock);
    const s = await import("../src/state/store");
    s.setToken("old-tok");
    const result = await s.regenerate();
    const [url, opts] = lastCall(fetchMock);
    expect(url).toBe("/admin/regenerate-token");
    expect(opts.headers["X-Admin-Token"]).toBe("old-tok");
    expect(result).toBe("new-tok");
    expect(s.token.value).toBe("new-tok");
    expect(localStorage.getItem("cc_admin")).toBe("new-tok");
  });

  it("startPolling polls on an interval and stop() halts it", async () => {
    vi.useFakeTimers();
    const body = {
      codes: [],
      hash_codes: false,
      messages: [],
      peers: {},
      public_url: "u",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValue({ json: async () => body, ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);
    const s = await import("../src/state/store");
    s.setToken("tok");

    const stop = s.startPolling(1000);
    await vi.advanceTimersByTimeAsync(1000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    stop();
    await vi.advanceTimersByTimeAsync(3000);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    vi.useRealTimers();
  });
});
