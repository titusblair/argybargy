/**
 * STUB — filled in by the sidebar UI task. Prop-less: reads `agents`,
 * `view`, `connection` from `state/store.ts` and `navOpen`/`drawerOpen`
 * from `state/ui.ts` directly; sets `view.value` to switch rooms/DMs.
 * See the component contract in `app.tsx`.
 */

export function Sidebar() {
  return (
    <aside
      aria-label="Workspace"
      className="flex h-full w-full flex-col bg-[var(--rail)] text-[var(--text)]"
      data-testid="sidebar"
    >
      <div className="p-3 text-[var(--muted)] text-xs">Sidebar (stub)</div>
    </aside>
  );
}
