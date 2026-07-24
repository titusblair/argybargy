/**
 * Shared cross-component UI state — the layout shell and the three region
 * components (Sidebar, ConversationPane, AdminDrawer) read/write these
 * directly. Keep this minimal: only signals that more than one component
 * needs to coordinate through belong here.
 */

import { signal } from "@preact/signals";

/** Admin drawer slide-over open/closed. Sidebar's admin trigger sets it. */
export const drawerOpen = signal(false);

/** Mobile off-canvas sidebar open/closed (<640px). The header's hamburger/tab sets it. */
export const navOpen = signal(false);
