import { beforeAll, beforeEach, describe, expect, it } from "vitest";

// Vitest 4.1's jsdom environment forwards window globals via a static key
// list that omits `localStorage`/`sessionStorage` (they're prototype
// getters, not own properties, so they're missed by both the static list
// and the own-property scan). Pull it directly off the jsdom instance
// vitest exposes as `globalThis.jsdom` so the real Storage implementation
// backs the global `localStorage` used below and inside src/theme.ts.
beforeAll(() => {
  if (typeof globalThis.localStorage === "undefined") {
    const dom = (globalThis as { jsdom?: { window: Window } }).jsdom;
    if (dom?.window.localStorage) {
      Object.defineProperty(globalThis, "localStorage", {
        configurable: true,
        value: dom.window.localStorage,
      });
    }
  }
});

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("theme", () => {
  it("cycles auto->light->dark->auto and persists", async () => {
    const { cycleTheme } = await import("../src/theme");
    expect(cycleTheme()).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(cycleTheme()).toBe("dark");
    expect(localStorage.getItem("cc_theme")).toBe("dark");
    expect(cycleTheme()).toBe("auto");
  });

  it("applyTheme sets data-theme and persists to localStorage", async () => {
    const { applyTheme } = await import("../src/theme");
    applyTheme("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("cc_theme")).toBe("dark");

    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem("cc_theme")).toBe("light");
  });

  it("applyTheme('auto') sets data-theme to auto and persists", async () => {
    const { applyTheme } = await import("../src/theme");
    applyTheme("auto");
    expect(document.documentElement.getAttribute("data-theme")).toBe("auto");
    expect(localStorage.getItem("cc_theme")).toBe("auto");
  });

  it("currentTheme reads the persisted preference, defaulting to auto", async () => {
    const { currentTheme, applyTheme } = await import("../src/theme");
    expect(currentTheme()).toBe("auto");
    applyTheme("dark");
    expect(currentTheme()).toBe("dark");
  });

  it("currentTheme reflects a value already persisted in localStorage", async () => {
    localStorage.setItem("cc_theme", "light");
    const { currentTheme } = await import("../src/theme");
    expect(currentTheme()).toBe("light");
  });
});
