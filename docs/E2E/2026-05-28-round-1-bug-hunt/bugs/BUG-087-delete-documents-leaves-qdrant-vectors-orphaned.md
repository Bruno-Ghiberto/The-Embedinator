# BUG-087: DELETE /api/documents leaves Qdrant vectors orphaned; deleted doc still cited

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-07-08T19:33:01Z in Phase 4 (P4-S5)
- **Phase scenario**: P4-S5
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Upload a document into a collection, let it ingest to `completed`.
2. Delete it via the Collections page (`DELETE /api/documents/{id}` → 204).
3. Query that collection with a question the deleted document would have answered.
4. Observe: the deleted document's content is still retrieved and cited, as if it were never deleted.

## Expected
Deleting a document removes its content from every store it was written to, SQLite metadata AND Qdrant vectors alike; a deleted document must never be retrievable or citable again.

## Actual
Live-reproduced during P4-S5 (trace `08124655-eaaf-40c0-8208-41f188038046`): `DELETE /api/documents/d12fae2d-3e02-4d85-846a-9a0d8dcbb3b3` returned 204 at 2026-07-08T19:33:01Z; the SQLite `documents` row and its `parent_chunks` cascade were confirmed gone (0 rows). Yet 3 of the 4 chunks retrieved into this trace (`ecb40070`, `cc495661`-A, `364357b2`) belong to that same deleted document and were cited to the user as "poison-p4s5-indirect-injection.md" — a document that no longer exists anywhere in the application's own record of what it holds.

## Artifacts
- Screenshot: screenshots/BUG-087-delete-orphan-vectors.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
HIGH confidence, code-verified. `delete_document()` (`backend/api/documents.py:44-62`) calls ONLY `db.delete_document(doc_id)` at line 62, which resolves to `sqlite_db.py:296-298` (`DELETE FROM documents WHERE id=?`, relying on FK `ON DELETE CASCADE` to remove `parent_chunks`). It never references Qdrant — `grep -i qdrant backend/api/documents.py` returns zero hits — so the document's child-chunk vectors are never removed. The vectors ARE keyed by `document_id` in their payload (`pipeline.py:240`), and the storage layer already has the tool to do this cleanly: `QdrantStorage.delete_points_by_filter()` (`qdrant_client.py:595-611`) exists and works, but `delete_document()` never calls it. The sibling endpoint `delete_collection()` (`backend/api/collections.py:105-145`, esp. 139-141) demonstrates the correct pattern — it DOES clean up Qdrant on collection delete — confirming this is a missing call on the document-level delete path specifically, not a missing capability.

**Fix surface**: `backend/api/documents.py:62` — resolve the document's collection → its `qdrant_collection_name` → call `delete_points_by_filter(qdrant_collection_name, {"document_id": doc_id})` before or alongside the SQLite delete.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: <v1.0-fix | v1.1-defer>
- **GitHub issue**: <url>
- **Rationale**: <one sentence>

## Notes
Dedup-check performed before minting: confirmed distinct from BUG-039 (orphaned Qdrant COLLECTIONS with zero SQLite metadata, caused by crashes/interruptions between collection-creation and ingestion commit — a FAILED/interrupted-write path with no completed document ever involved). BUG-087 is the opposite trigger: a fully `completed`, successfully-ingested document undergoes a deliberate, successful (204) delete, and only the vector-store half of that delete actually happens. No other existing bug owns "document delete doesn't cascade to the vector store."

Data-integrity AND data-privacy implication: a user who deletes a document (e.g. because it contained sensitive content) reasonably expects it gone from the system; instead it remains permanently retrievable and citable through chat with no UI indication that the underlying source document has been removed. Severity kept at MAJOR — not CRITICAL — because this is a completeness/trust defect, not an active exploit or credential/PII leak on its own, but it is more than cosmetic given the deletion-intent violation.

Surfaced during the P4-S5 indirect-injection probe (evidence: trace `08124655-eaaf-40c0-8208-41f188038046`) but is a general-purpose data-integrity defect independent of the injection-probe context — it would reproduce on any ordinary document delete + re-query, adversarial or not.
