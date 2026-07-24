import { render } from "preact";
import { App } from "./app";
import { FIXTURE } from "./state/fixture";
import { startPolling, state } from "./state/store";
import "./styles.css";
import { applyTheme, currentTheme } from "./theme";

applyTheme(currentTheme());

// Dev: seed FIXTURE so the UI renders data without a live server (also what
// the Playwright specs for the sidebar/conversation/drawer tasks rely on —
// see playwright.config.ts, which runs the dev server for that reason).
// Prod: poll the real /admin/state endpoint.
if (import.meta.env.DEV) {
  state.value = FIXTURE;
} else {
  startPolling();
}

const root = document.getElementById("app");

if (!root) {
  throw new Error("Missing #app root element");
}

render(<App />, root);
