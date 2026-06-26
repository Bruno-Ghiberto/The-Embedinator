# BUG-060: Citation [1] chip is non-semantic StyledText, not a focusable link

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-06-18T16:57:00Z in Phase 3 (P3-S1)
- **Phase scenario**: P3-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Send a query that returns at least one citation (Q-001 in hunt-pdfs confirmed).
2. Inspect the DOM node for the [1] citation chip.
3. Observe: node is a StyledText (span-like) element, not an anchor or button.
4. Attempt keyboard navigation — chip is not focusable via Tab.

## Expected
Citation chip is rendered as a focusable, semantic interactive element (button or anchor with role) so keyboard users can access citation detail.

## Actual
Citation [1] chip is a StyledText node — not keyboard-focusable, no accessible role, violates WCAG 2.4.3 (Focus Order) and 4.1.2 (Name, Role, Value).

## Artifacts
- Screenshot: screenshots/BUG-060-citation-a11y.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
Citation chip component renders as a styled span rather than a button/anchor; no tabIndex, role, or keyboard handler attached.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Frontend-inspector finding. Accessibility gap — citation chips are the primary navigation surface for grounded answers; keyboard and screen-reader users cannot access them. WCAG 2.1 AA failure. Linked to BUG-048 (trace_id not surfaced) — both represent incomplete interactive affordances on the chat output surface.
