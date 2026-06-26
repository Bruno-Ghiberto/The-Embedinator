# BUG-058: Sidebar lists duplicate-title and empty 'New Chat' orphan conversations

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-06-18T16:57:00Z in Phase 3 (P3-S1)
- **Phase scenario**: P3-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open the frontend chat UI.
2. Send at least one message in a conversation.
3. Inspect the sidebar conversation list.
4. Observe: two conversations with the same title, plus a "New Chat" entry with 0 messages.

## Expected
Sidebar shows a deduplicated list of conversations; "New Chat" entries with no messages are not persisted or are cleaned up on next load.

## Actual
Sidebar shows 2 conversations with identical titles and 1 "New Chat" orphan with 0 messages. localStorage-backed store does not deduplicate by title or remove zero-message sessions.

## Artifacts
- Screenshot: screenshots/BUG-058-sidebar-orphans.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
Conversation list is appended on each session init without checking for duplicate titles or zero-message cleanup; localStorage state accumulates stale entries across sessions.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Frontend-inspector finding. Pilot screenshot: /home/brunoghiberto/Pictures/Screenshots/Screenshot From 2026-06-18 13-51-49.png. localStorage-driven; no server-side dedup. Low UX impact but creates visual clutter for demo use.
