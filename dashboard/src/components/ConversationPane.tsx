/**
 * STUB — filled in by the conversation UI task. Prop-less: reads `state`,
 * `view`, `agents` from `state/store.ts` directly; calls `say()` to send.
 * See the component contract in `app.tsx`.
 */

export function ConversationPane() {
  return (
    <main
      aria-label="Conversation"
      className="flex h-full min-w-0 flex-1 flex-col bg-[var(--bg)] text-[var(--text)]"
      data-testid="conversation-pane"
    >
      <div className="p-3 text-[var(--muted)] text-xs">Conversation (stub)</div>
    </main>
  );
}
