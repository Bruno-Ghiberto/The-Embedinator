# BUG-059: Orphaned '.' glyph rendered below [1] citation chip

- **Severity**: COSMETIC
- **Layer**: Frontend
- **Discovered**: 2026-06-18T16:57:00Z in Phase 3 (P3-S1)
- **Phase scenario**: P3-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Send a query that returns at least one citation (Q-001 in hunt-pdfs confirmed).
2. Observe the rendered answer containing the [1] citation chip inline.
3. Inspect visually below the [1] chip — a stray "." glyph appears beneath it.

## Expected
No extraneous glyph below the citation chip; clean inline rendering.

## Actual
A standalone "." character is rendered below the [1] citation chip; visible in the DOM as a text node orphan adjacent to the chip container.

## Artifacts
- Screenshot: screenshots/BUG-059-orphan-glyph.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
CONFIRMED 2026-07-03 (pinned via P3-S5 3rd occurrence, trace 80c47266): the raw model text ends a sentence immediately after the citation marker in the SAME text run, e.g. "...doméstico [3]." — the citation-chip renderer swaps the "[3]" token for an interactive chip component but leaves the trailing "." as a separate plain-text DOM node, which renders detached/below the chip instead of inline immediately after it. Not a markdown-transform escape as originally hypothesized — it is the chip-swap boundary splitting a single text run into chip + orphaned-punctuation-node.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Frontend-inspector finding. Capture: /tmp/spec30-captures/p3-s1-current-state.png. Cosmetic only; does not affect function or accessibility. Visible in demo context.
3rd occurrence confirmed P3-S5 (2026-07-03, per Lead's occurrence count): orphaned "." below the [3] chip on Q-007 (NAG-204, collection nag-corpus-spec28), trace 80c47266 — same mechanism as the original P3-S1 occurrence (below [1]). Recurrence across P3-S1 and P3-S5, on two different collections, confirms the defect is systemic to the chip-swap renderer, not query- or collection-specific.

4th occurrence confirmed P4-S2 (2026-07-03): orphaned "." glyph re-confirmed under the [1] and [4] chips on the ambiguous "¿Es seguro?" answer. Same mechanism, further confirming the defect is chip-renderer-systemic rather than tied to any specific phase, query, or collection.
