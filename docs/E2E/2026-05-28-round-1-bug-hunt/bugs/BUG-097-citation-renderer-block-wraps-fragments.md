# BUG-097: Citation renderer block-wraps each text fragment, shattering every answer

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-07-10T15:22:13Z in Phase 5 (P5-S3)
- **Phase scenario**: P5-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open any chat answer containing two or more `[N]` citation markers.
2. Observe every span of text between markers renders as its own block paragraph.
3. Observe single words become isolated paragraphs.

## Expected
Citation markers should render as inline chips within continuous, naturally flowing text.

## Actual
Each text fragment between citation markers is independently wrapped in a block-level element, shattering the answer into a stack of disconnected paragraph blocks.

## Artifacts
- Screenshot: screenshots/BUG-097-citation-shatter.png (gitignored)
- Log excerpt: logs/BUG-097-citation-renderer-block-wrap.log (gitignored)
- Trace: null

## Root-cause hypothesis
`frontend/components/ChatMessageBubble.tsx:27-78` `renderWithCitations` splits the answer on `/\[(\d+)\]/g`, then pushes `<MarkdownRenderer content={parts[i]} />` (line ~50) for EACH text fragment. `frontend/components/MarkdownRenderer.tsx:36` unconditionally wraps its output in `<div className={className}>`, and react-markdown emits `<p>`/`<ul>` inside. Both are `display: block`.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/159
- **Rationale**: Each fragment between [N] markers is independently block-wrapped, isolating single words like "and" into their own paragraphs on every multi-citation answer — model-independent and deterministic, degrading the product's primary deliverable rather than a secondary surface.

## Notes
The chip is exonerated: `CitationHoverCard` renders an `<a>` with computed `display: inline-flex`, verified in the live DOM. The chip is inline. The wrappers around it are not.

The code states its own requirement and then violates it — ChatMessageBubble.tsx:46-52 reads: `// Text segment — render inline (no block-level markdown to avoid broken layout)` and the very next statement calls the block-level renderer. This is not an overlooked constraint. It is a considered one, written down, and contradicted one line later.

Not model-dependent — the decisive property. The split-and-independently-wrap architecture fragments the text regardless of content, so even zero-newline model output reproduces it, on every multi-citation answer, every time.

Live DOM proof (content-verified): seven direct-child block `<div>`s, with the single words "Passages" and "and" each isolated into their own paragraph — 15 `<div`, one literal `<p>Passages</p>`, one literal `<p>and</p>`, four `inline-flex` chips.

Severity MAJOR, not COSMETIC. BUG-093 makes a label ugly. BUG-097 degrades the primary product surface — the answer itself — on every multi-citation response, which the Phase 3 scenarios establish as the majority of real usage. Reserve COSMETIC for defects with no functional or readability impact.

Layer FRONTEND. Root cause and fix surface are both in ChatMessageBubble.tsx / MarkdownRenderer.tsx. The backend emits well-formed `[N]` markers. Fix: render fragments as genuinely inline spans, or give MarkdownRenderer an inline mode.

Dedup-check performed against all 71 existing bugs, plus a full read of BUG-086: BUG-086 = a MALFORMED `[N:1]` marker string that FAILS the regex and falls back to plain text — Backend layer, the model's fault. BUG-097 = a WELL-FORMED `[N]` marker, matched correctly by the regex, rendered through the correct inline chip, inside a broken layout architecture — Frontend layer, the renderer's fault. Different mechanism, different layer, different fix. New.
