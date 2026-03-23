# Feature Specification: UX/UI Redesign — "Intelligent Warmth"

**Feature Branch**: `018-ux-redesign`
**Created**: 2026-03-19
**Status**: Draft
**Input**: Redesign The Embedinator's frontend from a plain top-nav utility app into a polished, personality-driven application with collapsible sidebar navigation, dark/light mode toggle, comprehensive design token system, and per-page redesign making the system's AI intelligence visible at every surface.

## Overview

The Embedinator's backend features a sophisticated 3-layer agentic RAG pipeline with hybrid search, cross-encoder reranking, meta-reasoning, 5-signal confidence scoring, and groundedness verification. None of this intelligence is visible in the current frontend — it presents as a generic utility app with a fixed top navbar, minimal styling, and no design cohesion.

This specification defines a complete UI/UX redesign that closes the gap between backend sophistication and frontend presentation. The redesign replaces the fixed top navigation with a collapsible sidebar, introduces a comprehensive design token system using the "Obsidian Violet" palette, adopts shadcn/ui as the component foundation, adds manual dark/light mode toggle, and redesigns all five pages to surface AI intelligence (confidence scores, citations, meta-reasoning status, stage timings) as first-class visual elements.

The guiding philosophy is **"Intelligent Warmth"**: the interface should feel crafted and comfortable while making the system's intelligence visible at every surface. Dark mode is the primary experience (developer audience), with an equally polished light theme. Complexity is revealed progressively — simple on first glance, detail on demand.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Layout Foundation & Theme System (Priority: P1)

A developer opens The Embedinator for the first time and sees a modern application with a collapsible sidebar, cohesive color palette, and a dark theme that feels crafted rather than generic. They toggle between dark and light modes and navigate between all five sections via the sidebar. They press Cmd+K to open a command palette for quick navigation.

**Why this priority**: The layout and theme system are the foundation that every other redesign depends on. No page can be redesigned until the sidebar, design tokens, and theme toggle are in place.

**Independent Test**: Can be fully tested by loading the app, verifying the sidebar renders with navigation links, toggling dark/light mode, collapsing the sidebar, and opening the Cmd+K palette — all without any page-specific redesign.

**Acceptance Scenarios**:

1. **Given** the app loads at any route, **When** the page renders, **Then** a collapsible sidebar appears on the left with navigation links (Chat, Collections, Documents, Settings, Observability), an app name/logo at the top, and a dark mode toggle in the footer area.
2. **Given** the user is on a desktop viewport (>= 768px), **When** they click the sidebar collapse toggle, **Then** the sidebar collapses to icon-only mode (~56px wide) and the content area expands to fill the freed space.
3. **Given** the user clicks the dark/light mode toggle, **When** the theme switches, **Then** all colors update to the opposite theme without a full-page flash, layout shift, or hydration error.
4. **Given** the user presses Cmd+K (or Ctrl+K on non-Mac), **When** the command palette opens, **Then** it displays a searchable list of commands including page navigation, "Create Collection", "Clear Chat", and "Toggle Dark Mode".
5. **Given** the user is on a mobile viewport (< 768px), **When** they tap the hamburger menu button, **Then** the sidebar slides in from the left as an overlay and can be dismissed by tapping outside or pressing Escape.

---

### User Story 2 — Intelligent Chat Experience (Priority: P2)

A developer uses the chat interface daily to query their document collections. They see streaming tokens appear with a blinking cursor, inline citation chips linking to source documents, a color-coded confidence badge that expands to show the 5-signal breakdown, and a meta-reasoning status indicator when the system activates deeper research strategies.

**Why this priority**: Chat is the primary user surface and the page that most directly reveals the system's AI intelligence. A polished chat experience is the single most impactful change for user perception.

**Independent Test**: Can be fully tested by sending a query, watching tokens stream, clicking a citation chip, expanding the confidence breakdown, and observing meta-reasoning status — all on the chat page alone.

**Acceptance Scenarios**:

1. **Given** the chat page loads with no prior messages, **When** no conversation exists, **Then** an empty state appears with a centered prompt and 3-4 suggested starter questions the user can click to begin.
2. **Given** the user sends a query, **When** tokens stream from the backend, **Then** each token appears incrementally with a blinking caret cursor at the insertion point, and a stage-status indicator shows which pipeline node is currently active (e.g., "Retrieving", "Reranking", "Generating").
3. **Given** the assistant response includes citations, **When** the response completes, **Then** citation chips appear as small labeled badges below the message. Clicking a chip expands a popover showing the full citation text, source document name, and relevance score.
4. **Given** the response includes a confidence score, **When** the response completes, **Then** a color-coded confidence badge appears (green >= 70, yellow 40-69, red < 40) that can be clicked/hovered to expand a popover showing the 5-signal breakdown.
5. **Given** the backend sends a `clarification` event, **When** the clarification arrives, **Then** a styled card appears in the message stream with the clarification question and a CTA button for the user to respond.
6. **Given** the user hovers over an assistant message, **When** the hover state activates, **Then** a "Copy" action button appears allowing the user to copy the message text to clipboard.

---

### User Story 3 — Collection Management (Priority: P3)

A developer manages their document collections through a visual card grid. They see collection statistics at a glance (document count, chunk count, embedding model), create new collections via a polished dialog, and quickly navigate to a collection's documents via card actions.

**Why this priority**: Collections are the organizational backbone. A clear, skimmable grid with quick stats and actions reduces the friction of daily document management.

**Independent Test**: Can be fully tested by viewing the collections grid, creating a new collection, using search/filter, and accessing quick actions on a collection card.

**Acceptance Scenarios**:

1. **Given** the user navigates to /collections, **When** collections exist, **Then** a responsive card grid renders (2 columns at medium viewport, 3 at large) with each card showing collection name, description snippet, document count, chunk count, and embedding model as small badges.
2. **Given** the collections are loading, **When** the data fetch is in progress, **Then** skeleton card placeholders animate in place of real cards.
3. **Given** no collections exist, **When** the page loads, **Then** an empty state appears with a message and a prominent CTA button to create the first collection.
4. **Given** the user clicks "Create Collection", **When** the dialog opens, **Then** a form appears with fields for name (required), description (optional), embedding model (selectable), and chunk profile (selectable).
5. **Given** the user types in the search/filter input, **When** the input value changes, **Then** the collection grid filters in real time to show only collections whose name or description matches the query.

---

### User Story 4 — Document Management & Ingestion (Priority: P4)

A developer views a collection's documents in a two-column layout, uploads new files via drag-and-drop, monitors ingestion progress, and previews document chunks in a scrollable panel.

**Why this priority**: Document management is the second most frequent workflow after chat. The two-column layout and upload progress tracking significantly improve the ingestion experience.

**Independent Test**: Can be fully tested by navigating to a document page, uploading a file, watching progress, and previewing chunks.

**Acceptance Scenarios**:

1. **Given** the user navigates to /documents/[id], **When** the page loads, **Then** a two-column layout appears with a document file list on the left and a chunk preview panel on the right.
2. **Given** the user drags a file over the upload zone, **When** the file hovers over the drop area, **Then** the drop zone visually highlights (border color change, background tint) to indicate it will accept the drop.
3. **Given** the user drops or selects a file, **When** the ingestion job starts, **Then** a progress bar appears for that file, updating as chunks are processed, and shows the final status (complete or failed) with a status badge.
4. **Given** the user clicks a document in the file list, **When** the document has been ingested, **Then** the right panel scrolls to show the document's chunks with their text content.

---

### User Story 5 — Settings & Provider Configuration (Priority: P5)

A developer configures their LLM providers, models, and inference parameters through a tabbed settings interface. Each provider shows its connection status, and API key management is clear and secure.

**Why this priority**: Settings are configured once and adjusted occasionally, making this lower priority than daily-use pages. However, a clear settings UX reduces friction for first-time setup and provider changes.

**Independent Test**: Can be fully tested by navigating to settings, switching tabs, adding a provider key, changing a model selection, and saving inference parameters.

**Acceptance Scenarios**:

1. **Given** the user navigates to /settings, **When** the page loads, **Then** a tabbed interface appears with sections for "Providers", "Models", "Inference", and "System".
2. **Given** the user views the Providers tab, **When** providers are listed, **Then** each provider appears as a card with its name, a colored status dot (green if key is set, gray if not), and buttons to set/delete the API key.
3. **Given** the user enters an API key and clicks save, **When** the save succeeds, **Then** a toast notification confirms success, the provider card status dot turns green, and the input field clears.
4. **Given** the user modifies inference parameters (confidence threshold, chunk sizes), **When** they click save, **Then** a toast confirms the save and the form reflects the persisted values.

---

### User Story 6 — Observability & Performance Monitoring (Priority: P6)

A developer reviews system health, query performance, and trace details through an observability dashboard. They see service health cards, a stage-timing chart showing pipeline latency breakdown, a filterable trace table, and a slide-out panel with full trace details.

**Why this priority**: Observability is a power-user feature used for debugging and performance monitoring. Important for trust and transparency but lower frequency than chat or document management.

**Independent Test**: Can be fully tested by viewing health cards, examining charts, filtering the trace table, and clicking a trace to see its detail panel.

**Acceptance Scenarios**:

1. **Given** the user navigates to /observability, **When** the page loads, **Then** health status cards appear for each backend service (SQLite, Qdrant, Ollama) with a colored status dot (green=healthy, yellow=degraded, red=down, gray=unknown) and latency in milliseconds.
2. **Given** traces exist, **When** the stage timings chart renders, **Then** a horizontal bar chart shows pipeline stages (retrieval, rerank, compress, meta-reasoning, inference) with distinct colors per stage, and hovering a bar shows a tooltip with stage name and latency in ms.
3. **Given** the trace table is visible, **When** the user filters by session ID or confidence range, **Then** the table updates to show only matching traces with pagination controls.
4. **Given** the user clicks a trace row, **When** the detail panel opens, **Then** a slide-out panel appears from the right showing the full trace detail: stage timings, citations, confidence breakdown, query text, and response metadata.

---

### Edge Cases

- What happens when the sidebar is collapsed and the viewport is resized from desktop to mobile? The sidebar MUST switch to hidden/hamburger mode without rendering artifacts.
- What happens when the user toggles dark mode mid-stream while chat tokens are being received? The theme change MUST apply to already-rendered tokens and incoming tokens without interrupting the stream.
- What happens when a chart has no data (e.g., no traces yet)? Charts MUST display an empty state message rather than a blank or broken canvas.
- What happens when the command palette search matches no commands? The palette MUST show a "No results found" message rather than an empty list.
- What happens when the user rapidly toggles dark/light mode? The system MUST not produce flickering, stale-theme artifacts, or hydration errors.
- What happens when multiple browser tabs are open on /chat and the user sends messages in both? The last tab to write MUST win — no cross-tab synchronization is required. Users accept that only the most recently active tab's conversation is persisted.

## Requirements *(mandatory)*

### Functional Requirements

#### Area 1 — Layout & Navigation

- **FR-001**: The application MUST replace the current fixed top navigation bar with a collapsible left sidebar containing: app name/logo, navigation links with icons for all 5 routes (Chat, Collections, Documents, Settings, Observability), a dark/light mode toggle, and a system status indicator.
- **FR-002**: The sidebar MUST support two states on desktop (>= 768px): expanded (~240px, icons + labels) and collapsed (~56px, icons only). The sidebar MUST default to expanded on first visit. The user's collapse/expand preference MUST persist across browser sessions via localStorage so that returning users see the sidebar in the state they last chose.
- **FR-003**: On viewports below 768px, the sidebar MUST be hidden by default and accessible via a hamburger button that opens a slide-in overlay panel. The overlay MUST close when the user taps outside it or presses Escape.
- **FR-004**: The application MUST provide a command palette accessible via Cmd+K (macOS) or Ctrl+K (Windows/Linux). The palette MUST support searching and executing commands: navigate to any of the 5 pages, create a new collection, clear chat messages, and toggle dark mode.
- **FR-005**: Each content page MUST display a breadcrumb at the top of the content area showing the current navigation context (e.g., "Documents / collection-name").

#### Area 2 — Design Token System

- **FR-006**: The application MUST implement the "Obsidian Violet" color palette as CSS custom properties in the global stylesheet using the following token structure: background, surface, border, primary accent, text-primary, text-muted, success, warning, destructive. Dark mode values: background `#0d0c14`, surface `#15122a`, border `#2a2352`, accent `#a78bfa`, text-primary `#f5f3ff`, text-muted `#9785d4`, success `#34d399`, warning `#fbbf24`, destructive `#f87171`. Light mode values: background `#faf9ff`, surface `#f4f0ff`, border `#d1c4f5`, accent `#7c3aed`, text-primary `#1e1b4b`, text-muted `#6b52b5`, success `#059669`, warning `#d97706`, destructive `#dc2626`.
- **FR-007**: The application MUST define a consistent typography scale using the Inter font family with defined sizes for headings (h1-h4), body text, small text, and labels — all referenced via design tokens rather than hard-coded values.
- **FR-008**: The application MUST define consistent spacing tokens (e.g., page padding, card gaps, section margins) to maintain visual rhythm across all pages.

#### Area 3 — Dark/Light Mode

- **FR-009**: The application MUST support manual dark/light mode switching via a toggle control in the sidebar footer. The toggle MUST display a Sun icon in dark mode and a Moon icon in light mode.
- **FR-010**: The system MUST respect the user's operating system theme preference as the initial default on first visit. Subsequent manual toggles MUST be persisted and take priority over system preference.
- **FR-011**: Theme switching MUST NOT cause a full-page flash, layout shift, or hydration mismatch error on any page.

#### Area 4 — Chat Page

- **FR-012**: When no messages exist in the current session, the chat page MUST display an empty state with a centered greeting and 3-4 clickable suggested starter questions.
- **FR-013**: During token streaming, a blinking caret cursor MUST appear at the insertion point of the assistant's message. A stage-status indicator MUST show the currently active pipeline node (derived from NDJSON `status` events).
- **FR-014**: Citation data from the NDJSON stream MUST render as labeled chips below the assistant message. Each chip MUST be clickable to expand a popover showing the full citation text, source document name, and relevance score.
- **FR-015**: Confidence scores MUST render as a color-coded badge (green >= 70, yellow 40-69, red < 40). The badge MUST be clickable/hoverable to expand a popover displaying the 5-signal confidence breakdown.
- **FR-016**: When a `meta_reasoning` event is received, a small indicator MUST appear showing that meta-reasoning strategies were activated, with the list of strategies attempted.
- **FR-017**: When a `clarification` event is received during streaming, a styled card MUST appear in the message stream with the clarification question text and a response mechanism.
- **FR-018**: Assistant messages MUST show a "Copy to clipboard" action button on hover.
- **FR-019**: Chat messages MUST persist across page refreshes and new browser tabs via localStorage. When the user returns to the chat page, the most recent conversation MUST be rehydrated from stored data including message content, citations, confidence scores, and session ID. The user MUST be able to clear the stored conversation (e.g., via a "New Chat" action or the Cmd+K command palette "Clear Chat" command). Only the most recent conversation MUST be retained — when a new session starts, the previous conversation's stored data MUST be automatically evicted to prevent localStorage from accumulating unbounded data.

#### Area 5 — Collections Page

- **FR-020**: Collections MUST render as a responsive card grid: 1 column on mobile, 2 columns at medium viewport, 3 columns at large viewport. Each card MUST display the collection name, description (truncated), document count, chunk count, and embedding model as small badges.
- **FR-021**: The collections page MUST display a search/filter input that filters the collection grid in real time by matching against collection name and description.
- **FR-022**: Each collection card MUST provide a context menu with actions: "View Documents" (navigates to /documents/[id]) and "Delete" (with confirmation dialog).
- **FR-023**: While collections are loading, skeleton card placeholders MUST animate in place of real cards. When no collections exist, an empty state with a CTA to create the first collection MUST appear.
- **FR-024**: The "Create Collection" dialog MUST include fields for name (required), description (optional), embedding model (selectable from available models), and chunk profile (selectable).

#### Area 6 — Documents Page

- **FR-025**: The documents page MUST display a two-column layout on desktop: a file list table on the left and a chunk preview panel with scrollable content on the right. On mobile viewports (< 768px), the layout MUST stack vertically — file list on top (full width) and chunk preview below (full width).
- **FR-026**: The file upload area MUST provide a drag-and-drop zone that visually highlights on drag-over. After a file is dropped or selected, a progress indicator MUST track the ingestion job status, updating as chunks are processed.
- **FR-027**: Each document in the file list MUST display a status badge indicating its ingestion state: pending, processing, complete, or failed.

#### Area 7 — Settings Page

- **FR-028**: The settings page MUST organize configuration into tabbed sections: "Providers", "Models", "Inference", and "System".
- **FR-029**: The Providers tab MUST display each provider as a card with its name, connection status indicator (colored dot: green = key set, gray = no key), and controls to set or delete the API key. The API key input MUST support a show/hide toggle.
- **FR-030**: All save/delete actions MUST trigger toast notifications for success and error states. The notification system MUST replace the current custom toast implementation.

#### Area 8 — Observability Page

- **FR-031**: The observability page MUST display health status cards for each backend service (SQLite, Qdrant, Ollama), each showing a colored status dot (green/yellow/red/gray), service name, and latency in milliseconds.
- **FR-032**: A stage-timings chart MUST display pipeline stages as horizontal bars, ordered: retrieval, rerank, compress, meta-reasoning, inference. Each stage MUST use a distinct color. Hovering a bar MUST show a tooltip with the stage name and latency in milliseconds.
- **FR-033**: The trace table MUST support pagination and filtering by session ID, collection ID, and confidence score range. Clicking a trace row MUST open a slide-out detail panel from the right.
- **FR-034**: The trace detail panel MUST display: query text, response metadata, stage timings, citations, confidence breakdown, and reasoning steps when available.

#### Area 9 — Cross-Cutting Concerns

- **FR-035**: All icon-only buttons throughout the application MUST display a tooltip on hover/focus showing the button's purpose.
- **FR-036**: All pages MUST be usable at three breakpoints: mobile (375px), tablet (768px), and desktop (1280px+). No content MUST be inaccessible at any breakpoint.
- **FR-037**: All interactive elements MUST be reachable via keyboard (Tab navigation). All modals, slide-out panels, and popovers MUST close on Escape.
- **FR-038**: Every section that loads data asynchronously MUST display animated skeleton placeholders during the loading state.

### Key Entities

- **Design Token**: A named CSS custom property (e.g., `--color-background`, `--color-accent`) that defines a visual attribute (color, spacing, typography size) and changes value based on the active theme (dark/light).
- **Component Library Entry**: A reusable UI primitive (Button, Card, Badge, etc.) from the shadcn/ui registry, installed into `components/ui/` and styled via design tokens. Each entry replaces or wraps a hand-built component.
- **Theme Preference**: A user-controlled setting (dark, light, or system) stored in the browser and applied on every page load without flash.

### Component Migration Map

| Current Component | Migration Strategy |
|-------------------|--------------------|
| Navigation.tsx | **Replaced** by new SidebarNav component using shadcn Sidebar |
| Toast.tsx | **Replaced** by shadcn Sonner (toast notifications) |
| ChatPanel.tsx | **Retained + restyled** — new message bubble design, citation chips (Badge), confidence badge (Badge + Popover) |
| ChatInput.tsx | **Retained + restyled** — uses shadcn Textarea + Button |
| ChatSidebar.tsx | **Retained + restyled** — uses shadcn Select for model/collection selection |
| ModelSelector.tsx | **Retained + restyled** — uses shadcn Select |
| ConfidenceIndicator.tsx | **Retained + restyled** — migrates from raw Radix Tooltip to shadcn Badge + Tooltip + Popover |
| CitationTooltip.tsx | **Retained + restyled** — migrates to shadcn Badge + Popover |
| CollectionCard.tsx | **Retained + restyled** — uses shadcn Card + Badge + DropdownMenu |
| CollectionList.tsx | **Retained + restyled** — grid layout with shadcn Card children |
| CollectionStats.tsx | **Retained + restyled** — uses shadcn Badge |
| CreateCollectionDialog.tsx | **Retained + restyled** — migrates to shadcn Dialog + Input + Select |
| DocumentList.tsx | **Retained + restyled** — uses shadcn Table + Badge |
| DocumentUploader.tsx | **Retained + restyled** — uses shadcn Progress, retains react-dropzone |
| ProviderHub.tsx | **Retained + restyled** — uses shadcn Card + Input + Button |
| HealthDashboard.tsx | **Retained + restyled** — uses shadcn Card |
| TraceTable.tsx | **Retained + restyled** — uses shadcn Table |
| LatencyChart.tsx | **Retained + restyled** — restyled for design tokens (retains recharts) |
| StageTimingsChart.tsx | **Retained + restyled** — restyled for design tokens (retains recharts) |
| ConfidenceDistribution.tsx | **Retained + restyled** — restyled for design tokens (retains recharts) |
| MetricsTrends.tsx | **Retained + restyled** — restyled for design tokens (retains recharts) |
| *(New)* SidebarNav.tsx | **New** — shadcn Sidebar compound component |
| *(New)* CommandPalette.tsx | **New** — shadcn Command in Dialog |
| *(New)* ThemeToggle.tsx | **New** — dark/light mode toggle using useTheme hook |
| *(New)* Breadcrumb.tsx | **New** — shadcn Breadcrumb for page context |

## Non-Functional Requirements

- **NFR-001**: Theme switching MUST complete without any Cumulative Layout Shift (CLS) — the page layout MUST NOT reflow or jump when switching between dark and light modes.
- **NFR-002**: All interactive elements (buttons, links, form controls, cards, tooltips) MUST meet WCAG 2.1 Level AA requirements: minimum 4.5:1 contrast ratio for normal text, 3:1 for large text, visible focus indicators, and appropriate ARIA labels.
- **NFR-003**: The redesign MUST NOT introduce any new charting or animation libraries. All charts MUST continue to use recharts (already installed), and all transitions MUST use CSS-only animations.
- **NFR-004**: All pages MUST render their initial meaningful content (above the fold) within 2 seconds on a typical broadband connection, with skeleton loaders displayed within 200ms for any async data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The collapsible sidebar renders on all 5 pages. Clicking the collapse toggle switches between expanded (icons + labels) and collapsed (icon-only) states. On mobile viewports, the sidebar opens as a slide-in overlay via a hamburger button.
- **SC-002**: The dark/light mode toggle switches the application's color scheme between the Obsidian Violet dark palette and light palette. The user's choice persists across page reloads and browser sessions. No flash of wrong theme occurs on page load.
- **SC-003**: All 5 pages (Chat, Collections, Documents, Settings, Observability) render without hydration errors, console errors, or layout shift in both dark and light modes.
- **SC-004**: On the Chat page, streaming tokens appear incrementally with a visible cursor. Citation chips render as clickable badges that expand to show full citation details. The confidence badge displays the correct color tier (green/yellow/red) and expands to show the 5-signal breakdown.
- **SC-005**: The Cmd+K command palette opens, accepts search input, filters available commands, and executes the selected command (navigate to page, toggle theme, create collection).
- **SC-006**: The Observability page's stage-timing chart displays bars for each pipeline stage with distinct colors, and hovering any bar shows a tooltip with stage name and latency in ms.
- **SC-007**: All skeleton loaders appear during data loading for every async section: collections grid, documents list, trace table, settings form, health dashboard, and chat history.
- **SC-008**: All interactive elements are reachable via Tab key. All modals, drawers, and popovers close on Escape. All icon-only buttons display a tooltip describing their action.

## Clarifications

### Session 2026-03-19

- Q: What should happen when localStorage chat storage accumulates over time (~5MB limit)? → A: Keep only the most recent conversation; auto-evict previous conversation data when a new session starts.
- Q: How should multi-tab chat conflicts be handled when both tabs write to localStorage? → A: Last-write-wins; no cross-tab synchronization required.
- Q: How should the documents page two-column layout adapt on mobile (375px)? → A: Stack vertically — file list on top, chunk preview below, both full width.

## Assumptions

- The "Obsidian Violet" color palette (Palette A) has been selected by the user as the design direction. All design token values in FR-006 reflect this choice.
- CSS-only transitions are used for all animations (no Framer Motion or other animation libraries), per the project's non-goals. CSS `transition-*` utilities from Tailwind are sufficient for hover states, theme transitions, and sidebar collapse animations.
- The existing 5 custom hooks (useStreamChat, useCollections, useModels, useTraces, useMetrics) and `lib/api.ts` API client remain unchanged. No new API endpoints are needed.
- The existing `lib/types.ts` interfaces (18 types) remain unchanged — no data contract modifications.
- Existing Radix UI primitives already in `package.json` (@radix-ui/react-tooltip, dialog, select) will be superseded by shadcn/ui wrappers which use the same underlying Radix components, avoiding version conflicts.

## Out of Scope

- Backend changes — no new API endpoints, no schema migrations, no server-side code modifications
- New routes — the same 5 routes remain (/chat, /collections, /documents/[id], /settings, /observability)
- Authentication or user management — The Embedinator operates on a trusted local network model
- Internationalization / localization
- Rewriting existing hooks or API client logic
- New charting libraries (recharts remains the sole chart library)
- Creating new test files — existing Playwright and Vitest tests are updated only if they break
