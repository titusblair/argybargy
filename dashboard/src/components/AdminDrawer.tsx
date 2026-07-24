/**
 * Admin drawer — "the demoted plumbing." Prop-less: reads `drawerOpen` from
 * `state/ui.ts` (gates render; the close control sets it false) and
 * `state`, `token`, plus actions `invite`/`revoke`/`regenerate`/`setToken`
 * from `state/store.ts`. Ported from the locked mockup's `#drawer` markup
 * (argy-dashboard-mockup.html) — token entry, mint-a-key form, access-keys
 * table, regenerate-token danger zone, public URL. Custom look lives in the
 * co-located AdminDrawer.css (`.ad-` prefix); layout/overlay/scrim/slide
 * transform is owned by app.tsx.
 *
 * `invite`/`revoke`/`regenerate` throw on a non-ok response (see store.ts's
 * `api()` helper) — every call site here wraps them in try/catch and shows
 * an inline error instead of assuming success.
 */

import {
  ArrowClockwiseIcon,
  BroadcastIcon,
  CheckIcon,
  CopyIcon,
  GearSixIcon,
  KeyIcon,
  UsersThreeIcon,
  XIcon,
} from "@phosphor-icons/react";
import { useCallback, useState } from "preact/hooks";
import type { Code } from "../state/contract";
import {
  invite,
  regenerate,
  revoke,
  setToken,
  state,
  token,
} from "../state/store";
import { drawerOpen } from "../state/ui";
import "./AdminDrawer.css";

const EXPIRY_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { label: "never", value: "" },
  { label: "10 minutes", value: "10m" },
  { label: "30 minutes", value: "30m" },
  { label: "60 minutes", value: "60m" },
  { label: "1 day", value: "1d" },
  { label: "1 week", value: "1w" },
  { label: "1 month", value: "1mo" },
];

/** Dev-only test affordance — lets drawer.spec.ts open the drawer without
 * depending on the sidebar gear (owned by a sibling lane). Compiles out of
 * production since `import.meta.env.DEV` is statically replaced by Vite. */
if (import.meta.env.DEV) {
  (window as unknown as { __openDrawer: () => void }).__openDrawer = () => {
    drawerOpen.value = true;
  };
}

function closeDrawer() {
  drawerOpen.value = false;
}

function roomNames(current: ReturnType<typeof state.peek> | null): string[] {
  const set = new Set<string>();
  if (current) {
    for (const room of Object.keys(current.peers)) {
      set.add(room);
    }
    for (const code of current.codes) {
      set.add(code.room || "default");
    }
  }
  if (set.size === 0) {
    set.add("default");
  }
  return [...set];
}

function isOnline(
  current: ReturnType<typeof state.peek> | null,
  name: string
): boolean {
  if (!current) {
    return false;
  }
  return Object.values(current.peers).some((list) =>
    list.some((p) => p.name === name && p.online)
  );
}

/** Copies `text` to the clipboard, flips `copied` true for ~1.2s. Clipboard
 * failures (permissions/insecure context) are swallowed — the value stays
 * visible on screen to copy by hand either way, so there's nothing actionable
 * to surface as an error. */
async function copyToClipboard(text: string, setCopied: (v: boolean) => void) {
  try {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  } catch {
    // Non-fatal — see docblock above.
  }
}

function TokenSection() {
  const [draft, setDraft] = useState(token.value);
  const [saved, setSaved] = useState(false);

  const onInput = useCallback((e: Event) => {
    setDraft((e.target as HTMLInputElement).value);
  }, []);

  const save = useCallback(() => {
    setToken(draft.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 1200);
  }, [draft]);

  return (
    <section className="ad-sec">
      <div className="ad-label">
        <KeyIcon size={13} />
        Admin token
      </div>
      <div className="ad-frow">
        <input
          aria-label="Admin token"
          autoComplete="off"
          className="ad-field ad-grow"
          onInput={onInput}
          placeholder="paste admin token"
          type="password"
          value={draft}
        />
        <button className="ad-btn" onClick={save} type="button">
          {saved ? <CheckIcon size={13} /> : null}
          Save
        </button>
      </div>
      <p className="ad-hint">
        Sent as <code>X-Admin-Token</code> on every write. Stored only in this
        browser.
      </p>
    </section>
  );
}

function MintKeyForm() {
  const current = state.value;
  const rooms = roomNames(current);
  const [name, setName] = useState("");
  const [room, setRoom] = useState(rooms[0] ?? "default");
  const [expiry, setExpiry] = useState("");
  const [capabilities, setCapabilities] = useState("");
  const [result, setResult] = useState<{
    name: string;
    room: string;
    code: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [pending, setPending] = useState(false);

  const onNameInput = useCallback((e: Event) => {
    setName((e.target as HTMLInputElement).value);
  }, []);
  const onRoomChange = useCallback((e: Event) => {
    setRoom((e.target as HTMLSelectElement).value);
  }, []);
  const onExpiryChange = useCallback((e: Event) => {
    setExpiry((e.target as HTMLSelectElement).value);
  }, []);
  const onCapabilitiesInput = useCallback((e: Event) => {
    setCapabilities((e.target as HTMLInputElement).value);
  }, []);

  const mint = useCallback(async () => {
    const trimmed = name.trim();
    if (!trimmed) {
      return;
    }
    setError(null);
    setPending(true);
    try {
      const res = (await invite({
        capabilities: capabilities.trim() || null,
        expires: expiry || null,
        name: trimmed,
        room,
      })) as { code?: string };
      setResult({ code: res.code ?? "", name: trimmed, room });
      setName("");
      setCapabilities("");
    } catch {
      setError("Could not mint the key. Check the admin token and try again.");
    } finally {
      setPending(false);
    }
  }, [name, room, expiry, capabilities]);

  const copyCode = useCallback(() => {
    if (result) {
      copyToClipboard(result.code, setCopied);
    }
  }, [result]);

  return (
    <section className="ad-sec">
      <h2 className="ad-label">
        <KeyIcon size={13} />
        Mint a key
      </h2>
      <div className="ad-frow">
        <input
          aria-label="Agent name"
          autoComplete="off"
          className="ad-field ad-grow"
          onInput={onNameInput}
          placeholder="agent name"
          value={name}
        />
        <select
          aria-label="Room"
          className="ad-field"
          onChange={onRoomChange}
          style={{ width: 108 }}
          value={room}
        >
          {rooms.map((r) => (
            <option key={r} value={r}>
              #{r}
            </option>
          ))}
        </select>
      </div>
      <div className="ad-frow">
        <select
          aria-label="Expiry"
          className="ad-field"
          onChange={onExpiryChange}
          style={{ width: 120 }}
          value={expiry}
        >
          {EXPIRY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <input
          aria-label="Capabilities"
          autoComplete="off"
          className="ad-field ad-grow"
          onInput={onCapabilitiesInput}
          placeholder="capabilities (optional)"
          value={capabilities}
        />
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          className="ad-btn primary"
          disabled={pending || !name.trim()}
          onClick={mint}
          type="button"
        >
          {pending ? "Minting…" : "Mint key"}
        </button>
      </div>
      {result ? (
        <div className="ad-resultbox">
          Key for <b>{result.name}</b> in <b>#{result.room}</b>
          <div className="ad-code">{result.code}</div>
          <div style={{ marginTop: 7 }}>
            <button className="ad-btn" onClick={copyCode} type="button">
              {copied ? <CheckIcon size={12} /> : <CopyIcon size={12} />}
              Copy code
            </button>
          </div>
          <p className="ad-hint">
            Copy it now — with hashing on it will not be shown again.
          </p>
        </div>
      ) : null}
      {error ? <div className="ad-errorbox">{error}</div> : null}
    </section>
  );
}

function KeyRow({ code }: { code: Code }) {
  const current = state.value;
  const online = isOnline(current, code.name);
  const hashCodes = current?.hash_codes ?? false;
  const [confirming, setConfirming] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const copyCode = useCallback(() => {
    copyToClipboard(code.code, setCopied);
  }, [code.code]);

  const doRevoke = useCallback(async () => {
    if (!confirming) {
      setConfirming(true);
      setTimeout(() => setConfirming(false), 2600);
      return;
    }
    setConfirming(false);
    setError(null);
    setPending(true);
    try {
      await revoke(code.name);
    } catch {
      setError("Revoke failed — key is still active.");
    } finally {
      setPending(false);
    }
  }, [confirming, code.name]);

  return (
    <div className="ad-krow">
      <div className="ad-kline">
        <span className={`ad-kdot${online ? "on" : ""}`} />
        <span className="ad-kname">{code.name}</span>
        <span className="ad-kmeta">
          #{code.room || "default"} · {code.expires || "never"}
        </span>
        <span className="ad-kacts">
          {hashCodes ? null : (
            <button
              aria-label={`Copy key for ${code.name}`}
              className={`ad-icbtn${copied ? "ok" : ""}`}
              onClick={copyCode}
              type="button"
            >
              {copied ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
            </button>
          )}
          <button
            className={`ad-kkill${confirming ? "confirm" : ""}`}
            disabled={pending}
            onClick={doRevoke}
            type="button"
          >
            {confirming ? "Sure?" : "Revoke"}
          </button>
        </span>
      </div>
      {hashCodes ? null : <div className="ad-kcode">{code.code}</div>}
      {code.capabilities ? (
        <div className="ad-kcap">{code.capabilities}</div>
      ) : null}
      {error ? <div className="ad-errorbox">{error}</div> : null}
    </div>
  );
}

function KeysSection() {
  const current = state.value;
  const codes = current?.codes ?? [];

  return (
    <section
      aria-label="Access keys"
      className="ad-sec"
      data-testid="admin-keys"
    >
      <h2 className="ad-label">
        <UsersThreeIcon size={13} />
        Access keys <span className="mono">· {codes.length}</span>
      </h2>
      {codes.length === 0 ? (
        <p className="ad-hint">No keys minted yet.</p>
      ) : (
        <div>
          {codes.map((c) => (
            <KeyRow code={c} key={`${c.name}-${c.room}`} />
          ))}
        </div>
      )}
    </section>
  );
}

function RegenerateSection() {
  const [armed, setArmed] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [pending, setPending] = useState(false);

  const doRegenerate = useCallback(async () => {
    if (!armed) {
      setArmed(true);
      setTimeout(() => setArmed(false), 2800);
      return;
    }
    setArmed(false);
    setError(null);
    setPending(true);
    try {
      const newToken = await regenerate();
      setResult(newToken);
    } catch {
      setError("Could not regenerate the token. The old token still works.");
    } finally {
      setPending(false);
    }
  }, [armed]);

  const copyToken = useCallback(() => {
    if (result) {
      copyToClipboard(result, setCopied);
    }
  }, [result]);

  return (
    <section className="ad-sec">
      <div className="ad-label danger">Danger</div>
      <button
        className={`ad-btn danger${armed ? "confirm" : ""}`}
        disabled={pending}
        onClick={doRegenerate}
        type="button"
      >
        <ArrowClockwiseIcon size={13} />
        {armed ? "Really regenerate?" : "Regenerate admin token"}
      </button>
      <p className="ad-hint">
        Invalidates the current token for every dashboard session. Agent keys
        keep working.
      </p>
      {result ? (
        <div className="ad-resultbox">
          New admin token
          <div className="ad-code">{result}</div>
          <div style={{ marginTop: 7 }}>
            <button className="ad-btn" onClick={copyToken} type="button">
              {copied ? <CheckIcon size={12} /> : <CopyIcon size={12} />}
              Copy token
            </button>
          </div>
          <p className="ad-hint">
            Saved to this browser. Anyone else on the dashboard must re-enter
            it.
          </p>
        </div>
      ) : null}
      {error ? <div className="ad-errorbox">{error}</div> : null}
    </section>
  );
}

function PublicUrlSection() {
  const current = state.value;
  const url = current?.public_url ?? "";
  const [copied, setCopied] = useState(false);

  const copyUrl = useCallback(() => {
    copyToClipboard(url, setCopied);
  }, [url]);

  return (
    <section className="ad-sec">
      <div className="ad-label">
        <BroadcastIcon size={13} />
        Public URL
      </div>
      <div className="ad-urlrow">
        <span className="ad-u">{url}</span>
        <button
          aria-label="Copy public URL"
          className={`ad-icbtn${copied ? "ok" : ""}`}
          onClick={copyUrl}
          type="button"
        >
          {copied ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
        </button>
      </div>
      <p className="ad-hint">
        Agents reach the relay here. Each key below authenticates one agent into
        one room.
      </p>
    </section>
  );
}

export function AdminDrawer() {
  if (!drawerOpen.value) {
    return null;
  }

  return (
    <aside aria-label="Admin" className="ad-root" data-testid="admin-drawer">
      <header className="ad-head">
        <GearSixIcon size={16} />
        <span className="ad-title">Admin</span>
        <span className="ad-sub mono">keys · token · relay</span>
        <button
          aria-label="Close admin drawer"
          className="ad-close"
          onClick={closeDrawer}
          type="button"
        >
          <XIcon size={16} />
        </button>
      </header>
      <div className="ad-body">
        <PublicUrlSection />
        <TokenSection />
        <MintKeyForm />
        <KeysSection />
        <RegenerateSection />
      </div>
    </aside>
  );
}
