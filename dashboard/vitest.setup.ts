/**
 * Vitest global setup: polyfills `localStorage` and `sessionStorage`.
 *
 * jsdom disables `window.localStorage`/`sessionStorage` for opaque-origin
 * documents, and even with a real origin configured, Vitest's jsdom
 * environment forwards `window` globals via a static key list that misses
 * both (they're prototype getters, not own properties). Rather than reach
 * into Vitest/jsdom internals, install a real, minimal `Storage`-backed
 * implementation directly.
 */

class MemStorage implements Storage {
  readonly #store = new Map<string, string>();

  get length(): number {
    return this.#store.size;
  }

  clear(): void {
    this.#store.clear();
  }

  getItem(key: string): string | null {
    return this.#store.has(key) ? (this.#store.get(key) as string) : null;
  }

  key(index: number): string | null {
    return Array.from(this.#store.keys())[index] ?? null;
  }

  removeItem(key: string): void {
    this.#store.delete(key);
  }

  setItem(key: string, value: string): void {
    this.#store.set(key, String(value));
  }
}

function hasWorkingStorage(value: unknown): value is Storage {
  if (!value) {
    return false;
  }
  try {
    const storage = value as Storage;
    const probeKey = "__vitest_setup_probe__";
    storage.setItem(probeKey, "1");
    storage.removeItem(probeKey);
    return true;
  } catch {
    return false;
  }
}

function installStorage(propertyName: "localStorage" | "sessionStorage"): void {
  const target = globalThis as Record<string, unknown>;

  if (!hasWorkingStorage(target[propertyName])) {
    Object.defineProperty(globalThis, propertyName, {
      configurable: true,
      value: new MemStorage(),
      writable: true,
    });
  }

  if (
    typeof window !== "undefined" &&
    !hasWorkingStorage(
      (window as unknown as Record<string, unknown>)[propertyName]
    )
  ) {
    Object.defineProperty(window, propertyName, {
      configurable: true,
      value: globalThis[propertyName],
      writable: true,
    });
  }
}

installStorage("localStorage");
installStorage("sessionStorage");
