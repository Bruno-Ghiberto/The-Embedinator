# BUG-061: Citation click dead-ends on empty collection page; no source-passage view

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-06-18T18:45:00Z in Phase 3 (P3-S2)
- **Phase scenario**: P3-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Ask Q-001 ("¿Cuál es el objeto del Reglamento Técnico NAG-200?") in hunt-pdfs collection.
2. Wait for streamed response with inline [1] citation chip and "4 sources" collapsible.
3. Click any citation (inline [1] OR any of [1]-[4] in "4 sources").
4. Observe browser route: navigates to /documents/{document_id}.
5. Observe page content: "No documents yet. Upload a file to get started." + "Select a document to preview its chunks".

## Expected
Clicking a citation opens the cited source document with the relevant passage highlighted (US3 "click shows source / highlighted span").

## Actual
All 4 citation clicks dead-end on an empty collection page. Destinations (all return 200 []):
[1] /documents/9a674844…; [2] /documents/907ed763…; [3] /documents/a49b801e…; [4] /documents/2c04624d…
No document-detail or passage-highlight route exists anywhere in the app — US3 citation reachability is unimplementable as-is.

## Artifacts
- Screenshot: screenshots/BUG-061-citation-click-destination.png (gitignored)
- Log excerpt: logs/BUG-061-citation-payload.log (gitignored)
- Trace: null

## Root-cause hypothesis
ChatMessageBubble.handleCitationClick:124 calls router.push(`/documents/${citation.document_id}`). app/documents/[id]/page.tsx:28 treats the path segment as collection_id and calls getDocuments(collectionId) → GET /api/documents?collection_id={document_id} → 200 []. The document_id in the Citation payload is a parent-chunk UUID (research_nodes.py:593 Citation(document_id=chunk.parent_id)), never a collection_id. The Citation schema (schemas.py) has no collection_id field; the real hunt-pdfs collection (629d3d8b) is never in the payload. All 4 chips share the same broken handler. Spec-31 fix options: (A) add collection_id to Citation schema (BE+FE), route to /documents/${citation.collection_id}; (B) RECOMMENDED — intercepting route (.)documents/[id] opening a Radix Sheet/Dialog with the cited passage inline + new /api/citations/{passage_id} route handler, router.back() dismisses. Both require collection_id on Citation.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/139
- **Rationale**: Every citation click routes a parent-chunk UUID into a collection-id route and lands on "No documents yet" — US3 citation reachability, the product's headline verifiability claim, is 100% broken and the page falsely reports the collection as empty.

## Notes
Cross-ref BUG-042 (shared substrate: /documents/[id] page treats id as collection_id + raw-UUID breadcrumb) — distinct trigger (citation click) and root cause (wrong ID type in Citation schema); registered as separate bug. Cross-ref BUG-063 (GET /api/documents 200 [] for unknown collection_id masks the error — SWR never fires error branch, user sees misleading "No documents yet"). Session 931817be; backend trace 27bd5c78. Captures: /tmp/spec30-captures/p3-s2-frames/p3-s2-click-inline-1-destination.png, p3-s2-citation3-destination.png, p3-s2-citation4-destination.png, p3-s2-4sources-expanded.png, frame_018.jpg.

**UPDATE 2026-07-03 (P4-S1 cross-scenario repro)**: frontend-inspector confirmed the identical citation-click dead-end reproduces on a DECLINE answer, not just a grounded one — the citation chips shown alongside a P4-S1 out-of-scope decline (see BUG-081) route-push and dead-end the same way. Same root cause, no new fix surface; broadens confirmed impact to decline responses too.

[2026-07-10T12:22:13-03:00] ROOT CAUSE IDENTIFIED, contributed by log-analyst while auditing commit 01b253e for orphaned contracts during Phase 5 — a Phase-3 bug solved as a side effect of a Phase-5 investigation. BUG-061 records that clicking a citation dead-ends on an empty document page with no source-passage view. The missing piece is not a frontend routing bug: `GET /api/documents/{doc_id}` (backend/api/documents.py:23-40) returns ONLY the document metadata row and never fetches a single chunk. Meanwhile the storage layer already contains EXACTLY the capability that page requires, fully implemented and heavily unit-tested, with ZERO production callers: `SQLiteDB.get_parent_chunk()` (sqlite_db.py:389), `SQLiteDB.get_parent_chunks_batch()` (sqlite_db.py:398), `SQLiteDB.list_parent_chunks()` (sqlite_db.py:410). Team-lead independently verified all three: `grep -rn "\.<method>(" backend/ --include=*.py` excluding definitions returns 0 for each. (Note: the retrieval hot path reads parent chunks through a DIFFERENT reader, `backend/storage/parent_store.py`, so these three SQLiteDB methods are orphaned duplicates, not merely unused helpers.) This is the SAME disease as BUG-089 and the pending settings finding: a storage contract written and tested, never wired to a route. The fix for BUG-061 is therefore not "add a page" but "wire documents.py:23-40 to the parent-chunk methods that already exist." Severity UNCHANGED. Not a new registration — this is the missing half of an existing bug's root cause.
