/**
 * STUB — filled in by the admin-drawer UI task. Prop-less: reads
 * `drawerOpen` from `state/ui.ts` and `agents`/`token` from
 * `state/store.ts`; calls `invite()`/`revoke()`/`regenerate()`/
 * `setToken()`; sets `drawerOpen.value = false` to close. The overlay
 * gating (mount only when open) is handled by `app.tsx` — this component
 * only needs to render its own content.
 * See the component contract in `app.tsx`.
 */

export function AdminDrawer() {
  return (
    <aside
      aria-label="Admin"
      className="flex h-full w-full flex-col bg-[var(--surface)] text-[var(--text)]"
      data-testid="admin-drawer"
    >
      <div className="p-3 text-[var(--muted)] text-xs">Admin drawer (stub)</div>
    </aside>
  );
}
