# Spec-09 09-implement.md Improvement (2026-03-16)

## What Changed
Restructured `Docs/PROMPTS/spec-09-frontend/09-implement.md` for maximum orchestrator clarity:

1. **Agent Teams Orchestration Protocol moved to TOP** — Now at line 5, immediately after the title with heading `## AGENT TEAMS ORCHESTRATION PROTOCOL — READ THIS FIRST` and a blockquote marking it MAXIMUM PRIORITY. Previously buried at line ~805.

2. **Spawn pattern updated** — Now includes mandatory Vercel skill read:
   ```
   Read your instruction file at Docs/PROMPTS/spec-09-frontend/agents/A<N>-<name>.md FIRST.
   Also read `.claude/skills/vercel-react-best-practices/SKILL.md` and apply the relevant rules
   to every component and hook you write. Then execute all assigned tasks.
   ```

3. **New `## Vercel React Best Practices — MANDATORY` section** — At line 88, immediately after the orchestration protocol. Contains:
   - Skill path pointers (SKILL.md, AGENTS.md, rules/)
   - 11 high-impact rules table (bundle-dynamic-imports, bundle-barrel-imports, async-parallel, rerender-*, client-swr-dedup, rendering-conditional-render)
   - Per-agent rule responsibility matrix (A1–A7)

## File Structure After Change
```
1.  # Spec 09: Frontend Architecture -- Implementation Context
5.  ## AGENT TEAMS ORCHESTRATION PROTOCOL — READ THIS FIRST  ← MOVED HERE
88. ## Vercel React Best Practices — MANDATORY               ← NEW
127. ## Implementation Scope
... (Code Specifications, Configuration, Error Handling)
... ## Testing Protocol
... ## Key Code Patterns
... ## Done Criteria
```

## Skill Location
`.claude/skills/vercel-react-best-practices/`
- `SKILL.md` — quick reference, 62 rules in 8 categories
- `AGENTS.md` — full compiled rules (>25K tokens)
- `rules/<rule-name>.md` — individual rule files

## Key Rules Applied to This Implementation
| Rule | Impact | Applies To |
|------|--------|------------|
| `bundle-dynamic-imports` | CRITICAL | LatencyChart, ConfidenceDistribution (recharts, ssr:false) |
| `bundle-barrel-imports` | CRITICAL | Radix UI direct imports |
| `async-parallel` | CRITICAL | Independent fetches |
| `rerender-use-ref-transient-values` | MEDIUM | useStreamChat buffer |
| `rerender-functional-setstate` | MEDIUM | useStreamChat token accumulation |
| `rerender-memo` | MEDIUM | ChatMessage, CitationTooltip, CollectionCard |
| `rerender-no-inline-components` | MEDIUM | All components |
| `rerender-derived-state-no-effect` | MEDIUM | Confidence tier derivation |
| `client-swr-dedup` | MEDIUM-HIGH | useModels, useCollections |
| `rendering-conditional-render` | MEDIUM | All conditional JSX |
