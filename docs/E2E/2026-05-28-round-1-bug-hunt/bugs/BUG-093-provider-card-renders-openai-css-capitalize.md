# BUG-093: Provider card renders "Openai" — CSS capitalize applied to raw provider.name

- **Severity**: COSMETIC
- **Layer**: Frontend
- **Discovered**: 2026-07-10T14:51:56Z in Phase 5 (P5-S1)
- **Phase scenario**: P5-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open Settings > Providers (with the P5-S1 out-of-band-seeded `openai` row present).
2. Observe the OpenAI card's title renders as "Openai" instead of "OpenAI".

## Expected
The provider display name should render as the correct brand casing "OpenAI".

## Actual
Renders "Openai" — first letter of each word capitalized, internal cap lost.

## Artifacts
- Screenshot: screenshots/BUG-093-openai-label.png (gitignored)
- Log excerpt: logs/BUG-093-css-capitalize-provider-name.log (gitignored)
- Trace: null

## Root-cause hypothesis
`frontend/components/ProviderHub.tsx:58` — `<CardTitle className="capitalize">{provider.name}</CardTitle>`. Tailwind's `capitalize` utility emits CSS `text-transform: capitalize`, which upcases the first letter of each word and has no concept of internal-cap brand names. The API correctly returns the canonical lowercase identifier `"openai"` (verified: `GET /api/providers` -> `'ollama'`, `'openai'`). The frontend renders an identifier directly as a display name.

Proof it is CSS, not JS: the DOM text node is lowercase `openai`; a search of `document.documentElement.outerHTML` for the literal string `Openai` returns ZERO matches; only `innerText` (which reflects computed CSS) renders it capitalized. This falsifies a `charAt(0).toUpperCase()` JS-transform hypothesis rather than merely being consistent with the CSS one.

Fix surface: `ProviderHub.tsx:58`. Replace `className="capitalize"` with a display-name map, e.g. `{ollama:'Ollama', openai:'OpenAI', anthropic:'Anthropic', openrouter:'OpenRouter'}`. Purely local.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Latent scope: `"ollama"` -> "Ollama" and `"anthropic"` -> "Anthropic" render correctly by coincidence (capitalize-safe names). `"openrouter"` will render as "Openrouter" the moment BUG-089 is fixed and that provider becomes reachable. A dormant display defect whose trigger is another bug's fix — the second such pairing found this phase, after BUG-091.

Layer = Frontend, deliberate contrast with BUG-092 (Backend). BUG-092: the backend withheld data the frontend needed (`provider_type` absent from ProviderDetailResponse) — the frontend could not have done better, blame upstream. BUG-093: the backend returns exactly the right value (a lowercase identifier); the frontend chose to render an identifier as a display name. Nothing upstream is wrong. Same rule — layer names the root cause and what must move first — opposite answers, because the causes genuinely differ.

Severity = COSMETIC, not MINOR. Zero functional impact, zero data impact, purely visual. Reserve MINOR for defects that assert something false about system state (BUG-090's "0 models" is MINOR because it is a lie about the system; "Openai" is ugly, not false).

Ruled out, not registered: the masked key field is `value="••••••••"` (`ProviderHub.tsx:84`) — a fixed 8-character literal (U+2022 x8). The real key is 33 chars. `grep -nE "repeat\(|\.length"` across the whole file returns ZERO hits. The mask provably cannot leak key length. frontend-inspector checked this specifically and correctly declined to file it.

Dedup-check performed: frontend-inspector independently grepped all registered bugs for `openai.{0,20}capitali|capitali.{0,20}openai|Openai\b|mask.{0,20}length|text-transform`. Only hits were incidental case-insensitive matches on "OpenAI" inside BUG-089's README-claim text — not this mechanism. Zero existing bug owns it. Also distinct from BUG-090 (model_count) and BUG-092 (key field for local provider), which are visible on the same card but have different root causes and different fix surfaces. New.
