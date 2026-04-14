# MCP Reference — Complete Tool Catalog

All MCP servers available in this environment, including all sub-servers routed through the Docker MCP Gateway.

---

## Table of Contents

- [MCP\_DOCKER Gateway](#mcp_docker-gateway) *(9 sub-servers, 76 tools)*
  - [1. docker](#1-docker)
  - [2. fetch](#2-fetch)
  - [3. filesystem](#3-filesystem-reference)
  - [4. gemini-api-docs](#4-gemini-api-docs)
  - [5. mcp-api-gateway](#5-mcp-api-gateway)
  - [6. next-devtools-mcp](#6-next-devtools-mcp)
  - [7. redis](#7-redis)
  - [8. rust-mcp-filesystem](#8-rust-mcp-filesystem)
  - [9. sonarqube](#9-sonarqube)
- [Direct MCP Servers](#direct-mcp-servers)
  - [browser-tools](#browser-tools)
  - [chrome-devtools](#chrome-devtools)
  - [context7](#context7)
  - [engram](#engram)
  - [gitnexus](#gitnexus)
  - [mcp-chart](#mcp-chart)
  - [playwright](#playwright)
  - [sequential-thinking](#sequential-thinking)
  - [serena](#serena)
  - [langchain-docs](#langchain-docs)
  - [shadcn-ui](#shadcn-ui)
  - [claude\_ai\_Canva](#claude_ai_canva)
  - [claude\_ai\_Gmail](#claude_ai_gmail)
  - [claude\_ai\_Google\_Calendar](#claude_ai_google_calendar)
  - [claude\_ai\_Google\_Drive](#claude_ai_google_drive)
  - [claude\_ai\_Notion](#claude_ai_notion)

---

## MCP_DOCKER Gateway

**Connection:** `docker mcp gateway run` (stdio)
**Config:** `.mcp.json` at project root
**Management:** `docker mcp server list` / `docker mcp tools ls`

The Docker MCP Gateway aggregates 9 containerized MCP servers into a single connection. All 76 tools are exposed under the `mcp__MCP_DOCKER__*` prefix in Claude Code.

---

### 1. `docker`

**Image:** `mcp/docker` | **Author:** Docker Inc.
**Purpose:** Full Docker CLI access — manage containers, images, volumes, networks, and compose stacks directly from Claude.

| Tool | Description |
|------|-------------|
| `docker` | Execute any Docker CLI command (run, ps, build, compose, logs, exec, etc.) |

---

### 2. `fetch`

**Image:** `mcp/fetch` | **Author:** modelcontextprotocol | **License:** Other
**Purpose:** Fetch any URL and return its contents as markdown or raw HTML. Grants internet access for retrieving up-to-date documentation, APIs, or web pages.

| Tool | Description |
|------|-------------|
| `fetch` | Fetch a URL and optionally extract contents as markdown. Params: `url` (required), `max_length`, `raw` (get raw HTML), `start_index` (for paginated reads) |

---

### 3. `filesystem` (Reference)

**Image:** `mcp/filesystem` | **Author:** modelcontextprotocol | **License:** MIT
**Purpose:** Standard filesystem server with configurable allowed paths. Covers the core read/write/edit/navigate operations. *(Note: `rust-mcp-filesystem` below is a higher-performance superset of this server.)*

| Tool | Description |
|------|-------------|
| `create_directory` | Create a directory or nested path (silent if already exists) |
| `directory_tree` | Recursive JSON tree of files and directories |
| `edit_file` | Line-based edits with git-style diff output. Supports `dryRun` preview |
| `get_file_info` | File/directory metadata: size, timestamps, permissions, type |
| `list_allowed_directories` | List all directories this server is permitted to access |
| `list_directory` | Detailed directory listing with `[FILE]` / `[DIR]` prefixes |
| `move_file` | Move or rename files/directories across allowed paths |
| `read_file` | Read complete file contents |
| `read_multiple_files` | Read multiple files simultaneously (efficient batch read) |
| `search_files` | Recursively search by filename pattern (case-insensitive partial match) |
| `write_file` | Create or fully overwrite a file |

---

### 4. `gemini-api-docs`

**Image:** `mcp/gemini-api-docs` | **Author:** Google
**Purpose:** Search and retrieve Google Gemini API documentation, including the current model catalog.

| Tool | Description |
|------|-------------|
| `get_current_model` | Shortcut to retrieve the canonical "Gemini Models" documentation page |
| `search_documentation` | Keyword search across Gemini API documentation and knowledge base |

---

### 5. `mcp-api-gateway`

**Image:** `mcp/api-gateway` | **Author:** rflpazini | **Config:** Required (API definitions via env vars)
**Purpose:** Universal gateway to integrate any REST API using only Docker/env configuration. Load an API's Swagger/OpenAPI spec and execute its endpoints without writing integration code. Also exposes meta-tools for managing the MCP gateway itself.

**API Execution:**

| Tool | Description |
|------|-------------|
| `execute_api` | Execute any configured API endpoint. Params: `api_name`, `method`, `path`, `data` (body), `headers`, `params` (query) |
| `get_api_info` | List all configured APIs and their available endpoints. Optional `api_name` filter |

**Gateway Meta-tools** *(built into the gateway layer):*

| Tool | Description |
|------|-------------|
| `mcp-add` | Add a new MCP server to the session |
| `mcp-config-set` | Set configuration for an MCP server |
| `mcp-exec` | Execute a tool that exists in the current session |
| `mcp-find` | Search the Docker MCP catalog by name/description for servers to add |
| `mcp-remove` | Remove an MCP server from the registry and reload config |
| `get_capability_page` | Retrieve a documentation page by exact title (omit arg to get full page list) |
| `code-mode` | Create a JavaScript-enabled tool combining multiple MCP server tools |

---

### 6. `next-devtools-mcp`

**Image:** `mcp/next-devtools-mcp` | **Author:** kgprs
**Purpose:** Next.js-specific development tools — documentation lookup, runtime introspection of a running dev server, browser automation for page verification, and upgrade guidance.

| Tool | Description |
|------|-------------|
| `browser_eval` | Playwright browser automation for testing Next.js pages. Actions: `start`, `navigate`, `click`, `type`, `fill_form`, `evaluate`, `screenshot`, `console_messages`, `close`, `drag`, `upload_file`, `list_tools`. Prefer `nextjs_runtime` for Next.js-specific diagnostics |
| `enable_cache_components` | Fully automated Cache Components setup for Next.js 16: config updates, dev server start, error detection, Suspense boundary fixes, verification |
| `nextjs_docs` | Search Next.js official documentation (searches MCP resources first, falls back to official docs) |
| `nextjs_runtime` | Interact with a running Next.js dev server's MCP endpoint (`/_next/mcp`). Use for: route inspection, error detection, build diagnostics, runtime state. **Use this before making any changes to a running Next.js app.** Actions: `discover_servers`, `list_tools`, `call_tool` |
| `upgrade_nextjs_16` | Step-by-step guide for upgrading to Next.js 16, runs official codemod first (requires clean git state). Covers async API changes, config migration, React 19 compatibility |

---

### 7. `redis`

**Image:** `mcp/redis` | **Author:** redis | **License:** MIT | **Secrets:** configured
**Purpose:** Full Redis database access — all data structures, pub/sub, streams, JSON, vector search (Redis 8), and documentation lookup.

**Strings & Keys:**

| Tool | Description |
|------|-------------|
| `get` | Get a string value by key |
| `set` | Set a string value with optional TTL |
| `delete` | Delete a key |
| `expire` | Set TTL on a key (seconds) |
| `rename` | Rename a key |
| `type` | Get the data type stored at a key |
| `scan_keys` | Non-blocking SCAN iteration (returns partial results + cursor) |
| `scan_all_keys` | Collect ALL matching keys via full SCAN iteration (use with caution on large DBs) |
| `dbsize` | Total number of keys in the database |
| `info` | Redis server info and statistics (section: default/memory/cpu/etc.) |
| `client_list` | List connected clients |

**Hashes:**

| Tool | Description |
|------|-------------|
| `hset` | Set a field in a hash (with optional TTL) |
| `hget` | Get a single hash field value |
| `hgetall` | Get all fields and values from a hash |
| `hdel` | Delete a field from a hash |
| `hexists` | Check if a field exists in a hash |

**Lists:**

| Tool | Description |
|------|-------------|
| `lpush` | Push value onto the left of a list (with optional TTL) |
| `rpush` | Push value onto the right of a list (with optional TTL) |
| `lpop` | Remove and return the first element |
| `rpop` | Remove and return the last element |
| `lrange` | Get a range of elements |
| `llen` | Get list length |
| `lrem` | Remove elements by value (count controls head/tail/all direction) |

**Sets:**

| Tool | Description |
|------|-------------|
| `sadd` | Add a value to a set (with optional TTL) |
| `smembers` | Get all members of a set |
| `srem` | Remove a value from a set |

**Sorted Sets:**

| Tool | Description |
|------|-------------|
| `zadd` | Add a member with score (with optional TTL) |
| `zrange` | Get a range of members (optionally with scores) |
| `zrem` | Remove a member |

**Pub/Sub:**

| Tool | Description |
|------|-------------|
| `publish` | Publish a message to a channel |
| `subscribe` | Subscribe to a channel |
| `unsubscribe` | Unsubscribe from a channel |

**Streams:**

| Tool | Description |
|------|-------------|
| `xadd` | Add an entry to a stream (with optional TTL) |
| `xrange` | Read entries from a stream |
| `xdel` | Delete an entry from a stream |

**JSON (RedisJSON):**

| Tool | Description |
|------|-------------|
| `json_set` | Set a JSON document or value at a path (with optional TTL) |
| `json_get` | Get a JSON value at a path |
| `json_del` | Delete a JSON value at a path |

**Vector Search (Redis 8 / RediSearch):**

| Tool | Description |
|------|-------------|
| `create_vector_index_hash` | Create an HNSW vector similarity index on hash fields (COSINE/L2/IP distance) |
| `set_vector_in_hash` | Store a float32 vector as a binary field in a hash |
| `get_vector_from_hash` | Retrieve and decode a vector from a hash |
| `get_indexes` | List all RediSearch indexes |
| `get_index_info` | Get schema and stats for a specific index (FT.INFO) |
| `get_indexed_keys_number` | Count keys indexed by a given index |
| `vector_search_hash` | KNN vector similarity search on hash-stored vectors |
| `hybrid_search` | Combined filter + KNN search (pre-filter by metadata, then rank by vector similarity — standard RAG pattern) |
| `search_redis_documents` | Search the Redis documentation knowledge base for concepts, use cases, and patterns |

---

### 8. `rust-mcp-filesystem`

**Image:** `mcp/rust-mcp-filesystem` | **Author:** rust-mcp-stack | **License:** MIT | **Config:** Required
**Purpose:** High-performance async filesystem server built in Rust. Read-only by default with restricted directory access. Superset of the reference `filesystem` server — adds partial reads, media files, ZIP, duplicate detection, regex content search, and size-aware filtering. Optimized for large files and token efficiency.

| Tool | Description |
|------|-------------|
| `read_text_file` | Read a complete text file. Optional `with_line_numbers` flag for precise targeting |
| `read_file_lines` | Read a slice of a file: `offset` (0-based) + optional `limit`. Ideal for large file pagination |
| `head_file` | Read first N lines of a file |
| `tail_file` | Read last N lines of a file |
| `read_multiple_text_files` | Batch read multiple text files simultaneously |
| `read_media_file` | Read an image or audio file, returns Base64 + MIME type. Optional `max_bytes` guard |
| `read_multiple_media_files` | Batch read multiple media files as Base64 |
| `write_file` | Create or fully overwrite a file |
| `edit_file` | Line-based edits with diff output. Supports `dryRun` and `replaceAll` |
| `create_directory` | Create directory or nested path |
| `list_directory` | List directory contents with `[FILE]` / `[DIR]` prefixes |
| `list_directory_with_sizes` | Same as above but includes file sizes |
| `directory_tree` | Recursive JSON tree view. Optional `max_depth` limit |
| `move_file` | Move or rename files/directories |
| `get_file_info` | File/directory metadata (size, timestamps, permissions) |
| `list_allowed_directories` | List directories the server can access |
| `search_files` | Glob-pattern file search with optional `min_bytes`/`max_bytes` size filters |
| `search_files_content` | Search file contents by text or regex, returns file path + line + column + preview. Supports size filtering |
| `calculate_directory_size` | Recursively sum size of a directory. Output: human-readable or bytes |
| `find_duplicate_files` | Find duplicate files by content hash. Supports glob filter, size range, text/JSON output |
| `find_empty_directories` | Recursively find empty directories (ignores OS metadata files) |
| `unzip_file` | Extract a ZIP archive to a target directory |
| `zip_directory` | Compress a directory into a ZIP (with optional glob filter) |
| `zip_files` | Compress a list of files into a ZIP |

---

### 9. `sonarqube`

**Image:** `mcp/sonarqube` | **Author:** SonarSource | **Secrets:** set (partial config — needs `SONARQUBE_URL` + `SONARQUBE_TOKEN`)
**Purpose:** Code quality and security analysis via SonarQube Cloud/Server. Analyze code snippets, inspect issues, check quality gates, query metrics, and manage webhooks.

**Analysis:**

| Tool | Description |
|------|-------------|
| `analyze_code_snippet` | Analyze a code snippet or file for quality/security issues. Params: `language`, `code_snippet` |
| `analyze_file_list` | Analyze a list of files (by absolute path) in the current working directory |
| `toggle_automatic_analysis` | Enable or disable SonarQube for IDE background analysis |

**Issues & Projects:**

| Tool | Description |
|------|-------------|
| `search_sonar_issues_in_projects` | Search issues across projects. Filter by severity (INFO/LOW/MEDIUM/HIGH/BLOCKER), PR, page |
| `change_sonar_issue_status` | Change issue status via transition (e.g., confirm, resolve, reopen) |
| `search_my_sonarqube_projects` | List accessible SonarQube projects (paginated) |
| `search_dependency_risks` | Find SCA (software composition analysis) dependency vulnerabilities in a project |

**Quality Gates & Rules:**

| Tool | Description |
|------|-------------|
| `list_quality_gates` | List all quality gates |
| `get_project_quality_gate_status` | Get quality gate pass/fail status for a project, branch, or PR |
| `show_rule` | Get full details of a SonarQube rule by key |
| `list_rule_repositories` | List available rule repositories (filter by language or search query) |
| `list_languages` | List all supported programming languages |

**Metrics & Source:**

| Tool | Description |
|------|-------------|
| `get_component_measures` | Get metrics for a project (lines of code, complexity, coverage, violations, etc.) |
| `search_metrics` | Search available metric keys |
| `get_raw_source` | Get source code as raw text from SonarQube (requires "See Source Code" permission) |
| `get_scm_info` | Get SCM/blame info for a source file |

**System:**

| Tool | Description |
|------|-------------|
| `get_system_health` | Health status: GREEN / YELLOW / RED |
| `get_system_status` | Server state: status, version, ID |
| `get_system_logs` | Server logs (access/app/ce/deprecation/es/web). Requires admin |
| `ping_system` | Liveness check — returns "pong" |
| `get_system_info` | Full system config: JVM, database, search indexes, settings. Requires admin |

**Webhooks & Portfolios:**

| Tool | Description |
|------|-------------|
| `create_webhook` | Create a webhook for an org or project (with optional HMAC secret) |
| `list_webhooks` | List webhooks for an org or project |
| `list_portfolios` | List portfolios with filtering and pagination |
| `list_enterprises` | List enterprises (SonarQube Cloud only) |

---

## Direct MCP Servers

These servers connect directly to Claude Code (not via Docker MCP Gateway).

---

### `browser-tools`

**Purpose:** Browser state inspection and auditing tools. Reads from a connected browser session — does not control the browser (use `playwright` or `chrome-devtools` for interaction).

| Tool | Description |
|------|-------------|
| `getConsoleLogs` | Retrieve browser console log messages |
| `getConsoleErrors` | Retrieve browser console errors |
| `getNetworkLogs` | Retrieve all network requests |
| `getNetworkErrors` | Retrieve failed network requests |
| `getSelectedElement` | Get details of the currently selected DOM element |
| `takeScreenshot` | Capture a screenshot of the current page |
| `wipeLogs` | Clear all captured console and network logs |
| `runAccessibilityAudit` | Run a WCAG accessibility audit on the current page |
| `runPerformanceAudit` | Run a Lighthouse performance audit |
| `runSEOAudit` | Run an SEO audit |
| `runBestPracticesAudit` | Run a web best practices audit |
| `runNextJSAudit` | Run a Next.js-specific audit |
| `runAuditMode` | Run all audits in sequence |
| `runDebuggerMode` | Enable debugger mode for step-by-step inspection |

---

### `chrome-devtools`

**Purpose:** Full Chrome DevTools Protocol (CDP) control — navigate pages, interact with DOM, capture network/console data, run Lighthouse audits, and take memory/performance snapshots.

**Navigation & Pages:**

| Tool | Description |
|------|-------------|
| `new_page` | Open a new browser tab |
| `navigate_page` | Navigate to a URL |
| `list_pages` | List all open tabs |
| `select_page` | Switch focus to a specific tab |
| `close_page` | Close a tab |
| `resize_page` | Resize the browser viewport |
| `emulate` | Emulate a device (mobile, tablet, etc.) |

**Interaction:**

| Tool | Description |
|------|-------------|
| `click` | Click on an element (by selector or coordinates) |
| `hover` | Hover over an element |
| `drag` | Drag from one element/position to another |
| `fill` | Fill a single input field |
| `fill_form` | Fill multiple form fields at once |
| `type_text` | Type text into the focused element |
| `press_key` | Press a keyboard key |
| `select_page` | Select a tab by title or URL |
| `handle_dialog` | Accept or dismiss browser dialogs (alert, confirm, prompt) |
| `upload_file` | Upload a file to a file input element |
| `wait_for` | Wait for a selector, URL, or condition |

**Capture & Inspection:**

| Tool | Description |
|------|-------------|
| `take_screenshot` | Screenshot of a page or element |
| `take_snapshot` | DOM snapshot of the current page |
| `evaluate_script` | Execute JavaScript in the page context |
| `list_console_messages` | List all captured console messages |
| `get_console_message` | Get a specific console message by index |
| `list_network_requests` | List all network requests |
| `get_network_request` | Get details of a specific network request |

**Performance & Memory:**

| Tool | Description |
|------|-------------|
| `performance_start_trace` | Start recording a performance trace |
| `performance_stop_trace` | Stop the trace and return results |
| `performance_analyze_insight` | Analyze a specific performance insight from a trace |
| `take_memory_snapshot` | Capture a heap memory snapshot |
| `lighthouse_audit` | Run a full Lighthouse audit (performance, accessibility, SEO, best practices) |

---

### `context7`

**Purpose:** Retrieve up-to-date library documentation and code examples by library name. Resolves library IDs and fetches current docs — useful when built-in training knowledge may be stale.

| Tool | Description |
|------|-------------|
| `resolve-library-id` | Resolve a library name to its context7 ID (e.g., "next.js" → `/vercel/next.js`) |
| `query-docs` | Fetch documentation pages for a resolved library ID. Returns current docs + code examples |

---

### `engram`

**Purpose:** Persistent cross-session memory. Save and retrieve observations, decisions, architecture choices, and discoveries that should survive context compaction and session restarts.

**Namespace:** `mcp__plugin_engram_engram__*` — installed via the Claude Code plugin at `/home/brunoghiberto/Documents/Repo Tools/engram/plugin/claude-code/.mcp.json` with `--tools=agent` (11-tool core profile). Admin tools (`mem_delete`, `mem_stats`, `mem_timeline`) are **not exposed** by default. To enable them, edit the plugin's `.mcp.json` and change `"--tools=agent"` to `"--tools=agent,admin"`.

| Tool | Description |
|------|-------------|
| `mem_save` | Save a memory entry with topic key and content |
| `mem_search` | Search memory by keyword or topic |
| `mem_context` | Get all memories relevant to current work context |
| `mem_get_observation` | Retrieve a specific observation by ID |
| `mem_update` | Update an existing memory entry |
| `mem_suggest_topic_key` | Suggest a topic key for organizing a new memory |
| `mem_session_start` | Mark the start of a coding session |
| `mem_session_end` | Mark the end of a session |
| `mem_session_summary` | Generate a summary of the current session |
| `mem_save_prompt` | Save a prompt template to memory |
| `mem_capture_passive` | Passively capture context without explicit save |

---

### `gitnexus`

**Purpose:** Code intelligence graph for the indexed repository. Understand execution flows, assess impact before edits, safely rename symbols, and explore relationships between code symbols. **Required before any symbol modification** (per project guidelines).

| Tool | Description |
|------|-------------|
| `query` | Find execution flows and symbols by concept/keyword. Returns process-grouped results ranked by relevance |
| `context` | 360-degree view of a symbol: all callers, callees, and execution flow participation |
| `impact` | Blast radius analysis before editing. Reports direct callers (d=1 WILL BREAK), indirect deps (d=2 LIKELY AFFECTED), transitive (d=3 MAY NEED TESTING) |
| `detect_changes` | Pre-commit scope check — verify your changes only affect expected symbols. Scope: `staged`, `all`, `compare` |
| `rename` | Safe multi-file symbol rename using the call graph. Always run with `dry_run: true` first |
| `cypher` | Execute custom Cypher graph queries against the code knowledge graph |
| `list_repos` | List all repositories indexed by GitNexus |

---

### `mcp-chart`

**Purpose:** Generate data visualizations and diagrams as images or interactive charts directly from structured data.

| Tool | Description |
|------|-------------|
| `generate_line_chart` | Line chart for time series or trend data |
| `generate_bar_chart` | Horizontal bar chart |
| `generate_column_chart` | Vertical column chart |
| `generate_area_chart` | Area chart (stacked or overlapping) |
| `generate_pie_chart` | Pie or donut chart |
| `generate_scatter_chart` | Scatter plot for correlations |
| `generate_histogram_chart` | Distribution histogram |
| `generate_boxplot_chart` | Box and whisker plot for statistical distributions |
| `generate_violin_chart` | Violin plot for distribution shape |
| `generate_waterfall_chart` | Waterfall chart for cumulative values |
| `generate_funnel_chart` | Funnel chart for conversion flows |
| `generate_radar_chart` | Radar/spider chart for multi-axis comparison |
| `generate_dual_axes_chart` | Chart with two Y-axes for different scales |
| `generate_sankey_chart` | Sankey diagram for flow/allocation between nodes |
| `generate_treemap_chart` | Treemap for hierarchical proportional data |
| `generate_venn_chart` | Venn diagram for set relationships |
| `generate_liquid_chart` | Liquid fill gauge chart |
| `generate_word_cloud_chart` | Word cloud from frequency data |
| `generate_network_graph` | Network/graph diagram for node-edge relationships |
| `generate_mind_map` | Mind map for hierarchical concept mapping |
| `generate_flow_diagram` | Flowchart / process diagram |
| `generate_organization_chart` | Org chart / hierarchy diagram |
| `generate_fishbone_diagram` | Ishikawa/fishbone diagram for root cause analysis |
| `generate_spreadsheet` | Render data as a formatted spreadsheet table |
| `generate_pin_map` | Geographic map with pin markers |
| `generate_path_map` | Geographic map with path/route overlay |
| `generate_district_map` | Choropleth / district-shaded map |

---

### `playwright`

**Purpose:** Full browser automation via Playwright — navigate, interact, capture, and test web applications. More low-level than `chrome-devtools`; best for scripted E2E flows.

| Tool | Description |
|------|-------------|
| `browser_navigate` | Navigate to a URL |
| `browser_navigate_back` | Go back in browser history |
| `browser_snapshot` | Capture accessibility tree snapshot of the page |
| `browser_take_screenshot` | Screenshot (full page or viewport) |
| `browser_click` | Click an element by selector or accessibility role |
| `browser_hover` | Hover over an element |
| `browser_drag` | Drag from one element to another |
| `browser_type` | Type into a focused element |
| `browser_fill_form` | Fill multiple form fields at once |
| `browser_press_key` | Press a keyboard key or chord |
| `browser_select_option` | Select an option from a `<select>` element |
| `browser_file_upload` | Upload a file to a file input |
| `browser_handle_dialog` | Accept or dismiss a browser dialog |
| `browser_evaluate` | Execute JavaScript in page context and return result |
| `browser_run_code` | Run a code block in the browser context |
| `browser_console_messages` | Get all captured browser console messages |
| `browser_network_requests` | Get all captured network requests |
| `browser_wait_for` | Wait for a selector, URL, or network idle |
| `browser_tabs` | List open browser tabs |
| `browser_close` | Close the browser |
| `browser_resize` | Resize the viewport |

---

### `sequential-thinking`

**Purpose:** Structured step-by-step reasoning for complex multi-part problems. Breaks tasks into a chain of explicit thought steps, each building on the previous, with support for revision and branching.

| Tool | Description |
|------|-------------|
| `sequentialthinking` | Execute a sequential thinking chain. Provide `thought`, `nextThoughtNeeded`, `thoughtNumber`, `totalThoughts`. Supports `isRevision`, `revisesThought`, `branchFromThought`, `branchId`, `needsMoreThoughts` |

---

### `serena`

**Purpose:** Semantic code intelligence for efficient codebase exploration and editing. Understands symbols, their relationships, and call graphs — avoids reading entire files by working at the symbol level.

**Project & Config:**

| Tool | Description |
|------|-------------|
| `activate_project` | Activate the current project for Serena analysis |
| `get_current_config` | Get current Serena configuration |
| `check_onboarding_performed` | Check if onboarding has been completed |
| `onboarding` | Run Serena onboarding for a new project |
| `initial_instructions` | Get initial instructions and context for the project |

**Symbol Navigation:**

| Tool | Description |
|------|-------------|
| `get_symbols_overview` | Get an overview of all symbols in a file or directory |
| `find_symbol` | Find a symbol by `name_path` and `relative_path`. Use `include_body=True` to read implementation, `depth=1` for top-level children |
| `find_referencing_symbols` | Find all symbols that reference a given symbol (callers, importers) |
| `find_file` | Find a file by name pattern |
| `list_dir` | List directory contents |
| `search_for_pattern` | Regex/text pattern search across the codebase |

**Symbol Editing:**

| Tool | Description |
|------|-------------|
| `replace_symbol_body` | Replace the complete body/definition of a symbol |
| `insert_after_symbol` | Insert new code after a symbol (use last top-level symbol to append to file) |
| `insert_before_symbol` | Insert new code before a symbol (use first top-level symbol to prepend to file) |
| `rename_symbol` | Rename a symbol across the codebase |

**Memory:**

| Tool | Description |
|------|-------------|
| `list_memories` | List all Serena memory entries |
| `read_memory` | Read a specific memory entry |
| `write_memory` | Write a new memory entry |
| `edit_memory` | Edit an existing memory entry |
| `delete_memory` | Delete a memory entry |
| `rename_memory` | Rename a memory entry |

---

### `langchain-docs`

**Connection:** HTTP — `https://docs.langchain.com/mcp`
**Purpose:** Search and retrieve up-to-date LangChain documentation. Use this to look up LangChain / LangGraph APIs, classes, integrations, and conceptual guides when built-in training knowledge may be stale.

| Tool | Description |
|------|-------------|
| `search_docs_by_lang_chain` | Keyword or semantic search across the LangChain documentation. Returns relevant pages, code examples, and API references |
| `query_docs_filesystem_docs_by_lang_chain` | Query the filesystem-backed LangChain docs index (structured doc retrieval by path/section) |

---

### `shadcn-ui`

**Purpose:** Browse, search, and get detailed documentation and code examples for shadcn/ui components.

| Tool | Description |
|------|-------------|
| `list_shadcn_components` | List all available shadcn/ui components |
| `search_components` | Search components by name or description |
| `get_component_details` | Get full documentation for a component (props, usage, variants) |
| `get_component_examples` | Get code examples for a component |

---

### `claude_ai_Canva`

**Purpose:** Create, edit, and manage Canva designs directly — generate designs from prompts, edit elements, export, and organize in folders.

| Tool | Description |
|------|-------------|
| `generate-design` | Generate a new design from a text prompt |
| `generate-design-structured` | Generate a design with structured parameters |
| `get-design` | Get design metadata |
| `get-design-content` | Get the content/elements of a design |
| `get-design-pages` | Get pages in a multi-page design |
| `get-design-thumbnail` | Get a thumbnail image of a design |
| `create-design-from-candidate` | Create a design from a candidate/template |
| `start-editing-transaction` | Begin an editing transaction |
| `perform-editing-operations` | Apply editing operations within a transaction |
| `commit-editing-transaction` | Commit and save editing changes |
| `cancel-editing-transaction` | Cancel and discard editing changes |
| `resize-design` | Resize a design to new dimensions |
| `export-design` | Export a design (PDF, PNG, etc.) |
| `get-export-formats` | List available export formats |
| `import-design-from-url` | Import an existing design from a URL |
| `search-designs` | Search designs in the user's account |
| `create-folder` | Create a folder |
| `search-folders` | Search folders |
| `list-folder-items` | List items in a folder |
| `move-item-to-folder` | Move a design to a folder |
| `list-brand-kits` | List available brand kits |
| `get-assets` | Get brand or design assets |
| `upload-asset-from-url` | Upload an asset from a URL |
| `comment-on-design` | Add a comment to a design |
| `list-comments` | List comments on a design |
| `list-replies` | List replies to a comment |
| `reply-to-comment` | Reply to a comment |
| `get-presenter-notes` | Get presenter notes from a design |
| `request-outline-review` | Request an outline review |
| `resolve-shortlink` | Resolve a Canva shortlink to full URL |

---

### `claude_ai_Gmail`

**Purpose:** Read and draft Gmail messages — search threads, read emails, create drafts. Does not send emails.

| Tool | Description |
|------|-------------|
| `gmail_get_profile` | Get the authenticated user's Gmail profile |
| `gmail_list_labels` | List all Gmail labels |
| `gmail_search_messages` | Search messages with Gmail query syntax (e.g., `from:x subject:y`) |
| `gmail_read_message` | Read a specific message by ID |
| `gmail_read_thread` | Read a full conversation thread |
| `gmail_list_drafts` | List draft messages |
| `gmail_create_draft` | Create a new draft message |

---

### `claude_ai_Google_Calendar`

**Purpose:** Read and manage Google Calendar events — view, create, update, delete events and suggest meeting times.

| Tool | Description |
|------|-------------|
| `list_calendars` | List all calendars in the account |
| `list_events` | List events from a calendar (with date/search filters) |
| `get_event` | Get a specific event by ID |
| `create_event` | Create a new calendar event |
| `update_event` | Update an existing event |
| `delete_event` | Delete an event |
| `respond_to_event` | Accept, decline, or tentatively accept an invitation |
| `suggest_time` | Suggest available meeting times |

---

### `claude_ai_Google_Drive`

**Purpose:** Google Drive access — currently only auth tools are registered. Full Drive operations require completing authentication first.

| Tool | Description |
|------|-------------|
| `authenticate` | Start the Google Drive OAuth authentication flow |
| `complete_authentication` | Complete the OAuth flow with the returned auth code |

> **Note:** Only auth tools are exposed until authentication is completed. Extended Drive operations (list files, read/write, share, etc.) are not currently available in this session.

---

### `claude_ai_Notion`

**Purpose:** Read and write Notion pages, databases, and comments — search content, create/update pages, manage views and data sources.

| Tool | Description |
|------|-------------|
| `notion-search` | Search across all Notion content |
| `notion-fetch` | Fetch a specific page or database by ID or URL |
| `notion-create-pages` | Create new pages (in a database or as subpages) |
| `notion-update-page` | Update page content or properties |
| `notion-duplicate-page` | Duplicate an existing page |
| `notion-move-pages` | Move pages to a different parent |
| `notion-create-database` | Create a new database |
| `notion-update-data-source` | Update a database schema or properties |
| `notion-create-view` | Create a new database view |
| `notion-update-view` | Update an existing database view |
| `notion-get-comments` | Get comments on a page or block |
| `notion-create-comment` | Add a comment to a page or block |
| `notion-get-teams` | Get teams/workspaces the user belongs to |
| `notion-get-users` | Get users in the workspace |

---

## Quick Reference — When to Use What

| Need | Use |
|------|-----|
| Run Docker commands | `MCP_DOCKER` → `docker` |
| Fetch a web page / URL | `MCP_DOCKER` → `fetch` |
| Read/write local files (standard) | `MCP_DOCKER` → `filesystem` |
| Read/write local files (advanced: partial reads, media, ZIP) | `MCP_DOCKER` → `rust-mcp-filesystem` |
| Redis data operations | `MCP_DOCKER` → `redis` |
| Vector/semantic search in Redis | `MCP_DOCKER` → `redis` (hybrid_search, vector_search_hash) |
| Call any REST API via Swagger spec | `MCP_DOCKER` → `mcp-api-gateway` |
| Manage MCP gateway servers | `MCP_DOCKER` → gateway meta-tools (mcp-add, mcp-find, mcp-remove) |
| Next.js docs / runtime introspection | `MCP_DOCKER` → `next-devtools-mcp` |
| Next.js browser page verification | `MCP_DOCKER` → `next-devtools-mcp` → `browser_eval` |
| Code quality / security analysis | `MCP_DOCKER` → `sonarqube` |
| Gemini API documentation | `MCP_DOCKER` → `gemini-api-docs` |
| Browser automation (scripted flows) | `playwright` |
| Browser state inspection / audits | `browser-tools` |
| Full CDP browser control | `chrome-devtools` |
| Library documentation (up-to-date) | `context7` |
| Persistent cross-session memory | `engram` |
| Code impact analysis before edits | `gitnexus` → `impact` |
| Understand how code works | `gitnexus` → `query` / `context` |
| Safe symbol rename | `gitnexus` → `rename` |
| Read code by symbol (token-efficient) | `serena` → `find_symbol` / `get_symbols_overview` |
| Edit a full function/class body | `serena` → `replace_symbol_body` |
| Generate charts / visualizations | `mcp-chart` |
| Complex multi-step reasoning | `sequential-thinking` |
| LangChain / LangGraph documentation | `langchain-docs` → `search_docs_by_lang_chain` |
| shadcn/ui component reference | `shadcn-ui` |
| Canva design creation/editing | `claude_ai_Canva` |
| Gmail read/draft | `claude_ai_Gmail` |
| Google Calendar management | `claude_ai_Google_Calendar` |
| Google Drive (auth only currently) | `claude_ai_Google_Drive` |
| Notion read/write | `claude_ai_Notion` |
