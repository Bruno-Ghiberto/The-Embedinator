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
Citation chip rendering leaves a trailing punctuation character outside the chip wrapper element; likely a markdown-to-component transformation artifact where a period following the citation reference escapes the chip span.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Frontend-inspector finding. Capture: /tmp/spec30-captures/p3-s1-current-state.png. Cosmetic only; does not affect function or accessibility. Visible in demo context.
