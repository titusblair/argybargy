import { beforeEach, describe, expect, it } from "vitest";

// `localStorage` is polyfilled globally by vitest.setup.ts.

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("theme", () => {
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
