# Good First Issues

Descriptions for issues to create after the repository goes public.
Each issue should be labeled `good first issue`.

---

## 1. Add CSV ingestion support to the Rust worker

**Labels:** `good first issue`, `enhancement`, `ingestion`

**Description:**
The Rust ingestion worker (`ingestion-worker/`) currently supports PDF, Markdown, and plain text files. Add support for CSV files so that users can upload tabular data and have it chunked and indexed for retrieval.

**What needs to be done:**
1. Create a new `csv.rs` module in `ingestion-worker/src/`
2. Parse CSV rows and group them into logical chunks (e.g., N rows per chunk with the header row prepended)
3. Register the new format in `main.rs` so that `.csv` files are routed to the CSV parser
4. Add unit tests for the new parser

**Acceptance criteria:**
- A `.csv` file can be ingested via the upload endpoint
- Each chunk contains the CSV header row plus a configurable number of data rows
- Existing PDF/Markdown/text ingestion is unchanged
- Unit tests pass for edge cases (empty CSV, single row, missing headers)

**Relevant files:**
- `ingestion-worker/src/main.rs` — entry point and format dispatch
- `ingestion-worker/src/text.rs` — reference for how plain text parsing works
- `ingestion-worker/src/types.rs` — shared output types
- `backend/ingestion/pipeline.py` — Python orchestrator that invokes the Rust binary

---

## 2. Improve port conflict error message in embedinator.sh

**Labels:** `good first issue`, `enhancement`, `dx`

**Description:**
When a user runs `./embedinator.sh` and port 3000 or 8000 is already in use, Docker Compose fails with a generic error. The launcher script should detect port conflicts before starting services and display a helpful error message telling the user which port is occupied and how to free it.

**What needs to be done:**
1. Add a port availability check in `embedinator.sh` before calling `docker compose up`
2. Check ports 3000, 6333, 8000, and 11434
3. If any port is in use, print a clear message: "Port XXXX is already in use. Stop the process using it or set SERVICE_PORT=YYYY in .env"
4. Add the equivalent check in `embedinator.ps1` for Windows

**Acceptance criteria:**
- Running the launcher with an occupied port prints a specific error instead of a Docker Compose stack trace
- The error message names the conflicting port and suggests a resolution
- The check runs before any Docker commands execute
- Both `embedinator.sh` and `embedinator.ps1` have the check

**Relevant files:**
- `embedinator.sh` — macOS/Linux launcher
- `embedinator.ps1` — Windows PowerShell launcher
- `.env.example` — documents configurable port variables

---

## 3. Add collection search/filter on the collections page

**Labels:** `good first issue`, `enhancement`, `frontend`

**Description:**
The collections page shows all collections in a card grid. As users create more collections, they need a way to search or filter the list. Add a search input that filters collections by name in real time.

**What needs to be done:**
1. Add a search input component above the collection grid on the collections page
2. Filter the displayed collections client-side as the user types
3. Show a "No collections match" empty state when the filter returns zero results
4. Ensure the search input is accessible (proper label, keyboard navigation)

**Acceptance criteria:**
- A search box appears above the collections grid
- Typing in the search box filters collections by name (case-insensitive)
- Clearing the search box shows all collections again
- Empty state message appears when no collections match
- The component is keyboard-accessible

**Relevant files:**
- `frontend/app/collections/page.tsx` — collections page
- `frontend/hooks/useCollections.ts` — SWR hook for fetching collections
- `frontend/components/CollectionCard.tsx` — individual collection card

---

## 4. Add API pagination to the documents list endpoint

**Labels:** `good first issue`, `enhancement`, `backend`

**Description:**
The `GET /api/documents` endpoint currently returns all documents at once. For repositories with hundreds of documents, this causes slow responses and excessive memory usage. Add offset/limit pagination.

**What needs to be done:**
1. Add `offset` (default: 0) and `limit` (default: 50) query parameters to the documents endpoint
2. Update the SQLite query in the storage layer to use `LIMIT` and `OFFSET`
3. Return a response envelope with `items`, `total`, `offset`, and `limit` fields
4. Update the frontend documents page to paginate (or load more on scroll)
5. Add unit tests for the pagination parameters

**Acceptance criteria:**
- `GET /api/documents?limit=10&offset=0` returns the first 10 documents
- Response includes `total` count for the frontend to calculate pages
- Default behavior (no params) returns the first 50 documents
- Negative or non-integer values are rejected with 422
- Existing API clients that don't pass pagination params continue to work

**Relevant files:**
- `backend/api/documents.py` — documents route handler
- `backend/storage/sqlite_db.py` — SQLite storage layer
- `frontend/app/documents/page.tsx` — documents page
- `tests/unit/api/` — API unit tests

---

## 5. Add keyboard shortcuts to the chat interface

**Labels:** `good first issue`, `enhancement`, `frontend`

**Description:**
The chat interface currently only supports clicking the send button. Add keyboard shortcuts for common actions: Enter to send a message, Shift+Enter for a new line, and Escape to clear the input.

**What needs to be done:**
1. Update the chat input component to handle keyboard events
2. Enter sends the message (if not empty)
3. Shift+Enter inserts a newline (for multi-line messages)
4. Escape clears the input field
5. Add a small hint below the input showing the shortcuts

**Acceptance criteria:**
- Pressing Enter sends the message
- Pressing Shift+Enter creates a new line without sending
- Pressing Escape clears the input
- A subtle hint displays the keyboard shortcuts
- Existing click-to-send functionality still works

**Relevant files:**
- `frontend/app/chat/page.tsx` — chat page
- `frontend/components/ChatPanel.tsx` — chat panel component

---

## 6. Add health check retry with backoff in the launcher

**Labels:** `good first issue`, `enhancement`, `dx`

**Description:**
The launcher scripts wait for services to become healthy, but the retry logic uses a fixed delay. Implement exponential backoff with jitter so the script converges faster on fast machines and doesn't hammer slow ones.

**What needs to be done:**
1. Replace the fixed `sleep` interval in the health check loop with exponential backoff
2. Start at 1 second, double each iteration, cap at 15 seconds
3. Add a small random jitter (0-1 second) to prevent thundering herd if multiple services start simultaneously
4. Keep the overall timeout the same

**Acceptance criteria:**
- Health check retries use increasing delays instead of a fixed interval
- Maximum delay between retries is capped at 15 seconds
- Overall timeout behavior is unchanged
- The script still logs each retry attempt clearly

**Relevant files:**
- `embedinator.sh` — macOS/Linux launcher (health check loop)
- `embedinator.ps1` — Windows PowerShell launcher (health check loop)

---

## 7. Add dark mode screenshot to the README

**Labels:** `good first issue`, `documentation`

**Description:**
The README currently references screenshots in `docs/images/`. If you'd like to contribute better screenshots of the application (especially with realistic data loaded), this is a great way to help.

**What needs to be done:**
1. Run the application with `./embedinator.sh`
2. Upload a few sample documents and ask some questions to generate realistic data
3. Capture screenshots of: chat (light mode), chat (dark mode), collections page, observability dashboard
4. Optimize images (PNG, reasonable resolution ~1200px wide)
5. Replace the placeholder images in `docs/images/`

**Acceptance criteria:**
- Screenshots show the application with realistic conversations and data
- At least one screenshot shows dark mode
- Images are reasonably sized (under 500KB each)
- README renders correctly on GitHub with the new images

**Relevant files:**
- `docs/images/` — screenshot storage directory
- `README.md` — references the screenshots
