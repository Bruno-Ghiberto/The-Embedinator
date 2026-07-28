# BUG-123: UNCONFIRMED: proxy may hold client stream open after upstream socket dies

- **Severity**: MAJOR
- **Layer**: Infrastructure
- **Discovered**: 2026-07-28T14:08:27Z in Phase 7 (P7-S1)
- **Phase scenario**: P7-S1
- **BLOCKER-PATCHED**: no

## Steps to Reproduce
1. Open a chat stream through the Next.js proxy (browser → `localhost:3000` → `rewrites()` → backend `:8000`) and let it run.
2. `docker kill embedinator-backend` while the stream is open.
3. Observe on the PROXIED path: neither the application's reader nor an independent in-page `response.body.tee()` receives EOF — the TCP/HTTP response stays open for at least 189s though the upstream process is dead.
4. Repeat with the request issued DIRECT to `:8000`, bypassing the proxy (P7-S1d, `curl` client).
5. Observe on the DIRECT path: the client's stream terminates promptly on kill rather than hanging.

## Expected
When the upstream process dies, the downstream client's response is terminated so the client can observe EOF and run its terminal path.

## Actual
On the proxied path the downstream response appears to remain open indefinitely after upstream death (≥189s observed, no EOF on two independent readers). On the direct path the same backend death terminates the client stream promptly. The two observations are consistent with the proxy holding the downstream response open after the upstream socket dies — but this has NOT been isolated by a controlled experiment.

## Artifacts
- Screenshot: null
- Log excerpt: null
- Trace: traces/P7-S1-frontend-timeline.md (gitignored) — proxied observation, incl. the independent tee; traces/P7-S1d-mid-generation-kill.md — direct-to-:8000 observation

## Root-cause hypothesis
UNCONFIRMED — hypothesis only, deliberately not asserted. Candidate mechanism: the Next.js `rewrites()` proxy does not propagate upstream socket termination to the downstream client for a streaming response, so the client observes an open-but-silent connection instead of EOF. Evidence FOR: two independent readers saw no EOF for 189s on the proxied path (frontend-inspector), while a direct-to-`:8000` client terminated promptly under the same backend kill (team-lead, P7-S1d). Evidence AGAINST / limits: this is ONE observation on each path, gathered for other purposes; neither run was designed to isolate the proxy variable, no re-kill was performed to confirm reproducibility, and other differences existed between the runs (browser fetch reader vs `curl`, different turn states). Cross-ref BUG-054, which independently locates a separate defect in the same proxy layer (~30s idle timeout), making a shared proxy-configuration root cause plausible but unproven.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.1-defer
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/172
- **Rationale**: Registered UNCONFIRMED on two single observations that were not controlled for the proxy variable; it warrants a dedicated isolation probe in spec-31 rather than a v1.0 fix to a mechanism not yet established.

## Notes
Reporters: frontend-inspector (proxied observation, flagged by its author as a hypothesis needing corroboration and explicitly not re-killed to isolate) + team-lead (direct-to-`:8000` counter-observation at P7-S1d).

**Registered deliberately as UNCONFIRMED, per team-lead ruling.** The title carries the UNCONFIRMED marker so the qualification cannot be lost if the title is read in isolation — e.g. in an issue list or a summary table. This phase's binding standard is that a clean result counts only if the engineering behind it can be cited; the same discipline is applied in reverse here, and a defect is not asserted on evidence that has not isolated its variable.

**Why it is registered at all rather than dropped**: if confirmed it is a SECOND, INDEPENDENT defect from BUG-074. BUG-074 is that `api.ts:158-160` wedges when EOF arrives; this is that EOF may never arrive in the first place. Both were observed in the same 189s window. Fixing BUG-074 alone would therefore not resolve the observed hang, which is exactly the kind of conclusion that would be lost if this evidence were discarded.

**Recommended next step (spec-31)**: a dedicated probe — identical query and turn state, killed twice, once proxied and once direct, with EOF timing recorded on both — to isolate the proxy variable and either confirm or retract this record.
