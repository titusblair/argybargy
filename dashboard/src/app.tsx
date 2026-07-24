/**
 * App shell — layout skeleton only. Renders the 2-pane grid (Sidebar +
 * ConversationPane) with AdminDrawer as a slide-over overlay. Mirrors the
 * locked mockup's structure (argy-dashboard-mockup.html): `#app` is a flex
 * row of sidebar + main; `#drawer` is a fixed slide-over from the right;
 * the sidebar collapses to an off-canvas drawer under ~640px.
 *
 * Startup side effects (applyTheme + FIXTURE seed / startPolling) live in
 * `main.tsx`, not here — this file only owns layout.
 *
 * ---------------------------------------------------------------------
 * COMPONENT CONTRACT (read this before filling in Sidebar / Conversation-
 * Pane / AdminDrawer):
 *
 * Each of the three region components is a PROP-LESS named export:
 *   export function Sidebar() { ... }
 *   export function ConversationPane() { ... }
 *   export function AdminDrawer() { ... }
 *
 * No props are threaded from app.tsx. Each component reads what it needs
 * directly from the shared signals and calls store actions directly:
 *
 *   - `src/state/store.ts`: `token`, `state`, `connection`, `view`,
 *     `agents` (computed) — and actions `setToken`, `poll`, `startPolling`,
 *     `say`, `invite`, `revoke`, `regenerate`.
 *   - `src/state/ui.ts`: `drawerOpen` (admin drawer open/closed — Sidebar
 *     sets it via its admin trigger, AdminDrawer reads it to know it's
 *     mounted/visible and sets it false to close) and `navOpen` (mobile
 *     off-canvas sidebar open/closed, <640px).
 *   - To switch rooms/DMs: set `view.value = { kind, room, agent? }`.
 *
 * Import Phosphor icons directly from "@phosphor-icons/react" in each
 * component file — there is no shared icons module, so the three UI tasks
 * never collide on one file.
 *
 * Because everything is signal-driven and prop-less, each task can build
 * out its component file in isolation without ever touching app.tsx or the
 * other two components.
 * ---------------------------------------------------------------------
 */

import { AdminDrawer } from "./components/AdminDrawer";
import { ConversationPane } from "./components/ConversationPane";
import { Sidebar } from "./components/Sidebar";
import { drawerOpen, navOpen } from "./state/ui";

// Stable handler references (module scope, not re-created per render) —
// each just flips one shared UI signal.
function closeNav() {
  navOpen.value = false;
}

function openNav() {
  navOpen.value = true;
}

function closeDrawer() {
  drawerOpen.value = false;
}

export function App() {
  return (
    <div className="flex h-dvh min-h-0 w-full overflow-hidden bg-[var(--bg)] text-[var(--text)]">
      {/* Mobile off-canvas scrim — closes the sidebar drawer on outside tap. */}
      {navOpen.value ? (
        <button
          aria-label="Close navigation"
          className="fixed inset-0 z-30 bg-[var(--scrim)] sm:hidden"
          onClick={closeNav}
          type="button"
        />
      ) : null}

      <div
        className={`fixed inset-y-0 left-0 z-30 w-[min(82vw,300px)] transform border-[var(--border-strong)] border-r transition-transform duration-200 ease-in-out sm:static sm:z-auto sm:w-64 sm:shrink-0 sm:translate-x-0 sm:border-[var(--border)] sm:border-r ${
          navOpen.value ? "translate-x-0" : "-translate-x-full sm:translate-x-0"
        }`}
      >
        <Sidebar />
      </div>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* Mobile header tab — the only thing app.tsx owns on small screens:
            a trigger to open the off-canvas sidebar. Region internals are
            the sidebar task's job; this button only flips navOpen. */}
        <div className="flex items-center border-[var(--border)] border-b px-3 py-2 sm:hidden">
          <button
            aria-label="Open navigation"
            className="rounded-md px-2 py-1 text-[var(--muted)] text-xs"
            data-testid="nav-trigger"
            onClick={openNav}
            type="button"
          >
            Menu
          </button>
        </div>

        <ConversationPane />
      </div>

      {/* Admin drawer — slide-over overlay, gated on drawerOpen. */}
      {drawerOpen.value ? (
        <>
          <button
            aria-label="Close admin drawer"
            className="fixed inset-0 z-40 bg-[var(--scrim)]"
            onClick={closeDrawer}
            type="button"
          />
          <div className="fixed inset-y-0 right-0 z-50 w-[min(430px,100vw)] border-[var(--border-strong)] border-l">
            <AdminDrawer />
          </div>
        </>
      ) : null}
    </div>
  );
}
