# Next.js DevTools MCP Server

next-devtools-mcp is a Model Context Protocol (MCP) server that provides Next.js development tools and utilities for AI coding assistants.

[What is an MCP Server?](https://www.anthropic.com/news/model-context-protocol)

## MCP Info
Attribute|Details|
|-|-|
**Docker Image**|[mcp/next-devtools-mcp](https://hub.docker.com/repository/docker/mcp/next-devtools-mcp)
**Author**|[kgprs](https://github.com/kgprs)
**Repository**|https://github.com/kgprs/next-devtools-mcp

## Image Building Info
Attribute|Details|
|-|-|
**Dockerfile**|https://github.com/kgprs/next-devtools-mcp/blob/9ed2aab35ef34d7e19707cf19fb49d6bfc1936f5/Dockerfile
**Commit**|`9ed2aab35ef34d7e19707cf19fb49d6bfc1936f5`
**Docker Image built by**|Docker Inc.
**Docker Scout Health Score**| ![Docker Scout Health Score](https://api.scout.docker.com/v1/policy/insights/org-image-score/badge/mcp/next-devtools-mcp)
**Verify Signature**|`COSIGN_REPOSITORY=mcp/signatures cosign verify mcp/next-devtools-mcp --key https://raw.githubusercontent.com/docker/keyring/refs/heads/main/public/mcp/latest.pub`
**Licence**|

## Available Tools (5)
Tools provided by this Server|Short Description
-|-
`browser_eval`|Automate and test web applications using Playwright browser automation.|
`enable_cache_components`|Complete Cache Components setup for Next.js 16.|
`nextjs_docs`|Search and retrieve Next.js official documentation.|
`nextjs_runtime`|Interact with a running Next.js development server's MCP endpoint to query runtime information, diagnostics, and internals.|
`upgrade_nextjs_16`|Guide through upgrading Next.js to version 16.|

---
## Tools Details

#### Tool: **`browser_eval`**
Automate and test web applications using Playwright browser automation.
This tool connects to playwright-mcp server and provides access to all Playwright capabilities.

CRITICAL FOR PAGE VERIFICATION:
When verifying pages in Next.js projects (especially during upgrades or testing), you MUST use browser automation to load pages
in a real browser instead of curl or simple HTTP requests. This is because:
- Browser automation actually renders the page and executes JavaScript (curl only fetches HTML)
- Detects runtime errors, hydration issues, and client-side problems that curl cannot catch
- Verifies the full user experience, not just HTTP status codes
- Captures browser console errors and warnings via console_messages action

IMPORTANT FOR NEXT.JS PROJECTS:
If working with a Next.js application, PRIORITIZE using the 'nextjs_runtime' tool instead of browser console log forwarding.
Next.js has built-in MCP integration that provides superior error reporting, build diagnostics, and runtime information
directly from the Next.js dev server. Only use browser_eval's console_messages action as a fallback when nextjs_runtime
tools are not available or when you specifically need to test client-side browser behavior that Next.js runtime cannot capture.

Available actions:
- start: Start browser automation (automatically installs if needed). Verbose logging is always enabled.
- navigate: Navigate to a URL
- click: Click on an element
- type: Type text into an element
- fill_form: Fill multiple form fields at once
- evaluate: Execute JavaScript in browser context
- screenshot: Take a screenshot of the page
- console_messages: Get browser console messages (for Next.js, prefer nextjs_runtime tool instead)
- close: Close the browser
- drag: Perform drag and drop
- upload_file: Upload files
- list_tools: List all available browser automation tools from the server

Note: The playwright-mcp server will be automatically installed if not present.
#### Tool: **`enable_cache_components`**
Complete Cache Components setup for Next.js 16.

Handles ALL steps for enabling and verifying Cache Components:
- Configuration: Updates cacheComponents flag (experimental in 16.0.0, stable in canary > 16), removes incompatible flags
- Dev Server: Starts dev server with MCP enabled (__NEXT_EXPERIMENTAL_MCP_SERVER=true)
- Error Detection: Loads all routes via browser automation, collects errors using Next.js MCP
- Automated Fixing: Adds Suspense boundaries, "use cache" directives, generateStaticParams, cacheLife profiles, cache tags
- Verification: Validates all routes work with zero errors

Key Features:
- One-time dev server start (no restarts needed)
- Automated error detection using Next.js MCP tools
- Browser-based testing with browser automation
- Fast Refresh applies fixes instantly
- Comprehensive fix strategies for all error types
- Support for "use cache", "use cache: private", Suspense boundaries
- Cache invalidation with cacheTag() and cacheLife() configuration

Requires:
- Next.js 16.0.0+ (stable or canary only - beta versions are NOT supported)
- Clean working directory preferred
- Browser automation installed (auto-installed if needed)

This tool embeds complete knowledge base for:
- Cache Components mechanics
- Error patterns and solutions
- Caching strategies (static vs dynamic)
- Advanced patterns (cacheLife, cacheTag, draft mode)
- Build behavior and prefetching
- Test-driven patterns from 125+ fixtures
#### Tool: **`nextjs_docs`**
Search and retrieve Next.js official documentation.
First searches MCP resources (Next.js 16 knowledge base) for latest information, then falls back to official Next.js documentation if nothing is found.
Provides access to comprehensive Next.js guides, API references, and best practices.
#### Tool: **`nextjs_runtime`**
Interact with a running Next.js development server's MCP endpoint to query runtime information, diagnostics, and internals.

WHEN TO USE THIS TOOL - Use proactively in these scenarios:

1. **Before implementing ANY changes to the app**: When asked to add, modify, or fix anything in the application:
   - "Add a loading state" â†’ Check current component structure and routes first
   - "Fix the navigation" â†’ Inspect existing routes and components
   - "Update the API endpoint" â†’ Query current routes and data flows
   - "Add error handling" â†’ Check runtime errors and component hierarchy
   - "Refactor the auth logic" â†’ Inspect current auth implementation and routes
   - "Optimize performance" â†’ Check runtime diagnostics and component tree
   Use this to understand where changes should be made and what currently exists.

2. **For diagnostic and investigation questions**:
   - "What's happening?" / "What's going on?" / "Why isn't this working?"
   - "Check the errors" / "See what's wrong"
   - "What routes are available?" / "Show me the routes"
   - "Clear the cache" / "Reset everything"
   - Questions about build status, compilation errors, or runtime diagnostics

3. **For agentic codebase search**: Use this as FIRST CHOICE for searching the currently running app. If not found, fallback to static codebase search tools.

KEY PRINCIPLE: If the request involves the running Next.js application (whether to investigate OR modify it), query the runtime FIRST to understand current state before proceeding.

Start by calling action='list_tools' to discover what runtime information is available, then use those tools to gather context.

REQUIREMENTS:
- Next.js 16 or later (MCP support was added in v16)
- If you're on Next.js 15 or earlier, use the 'upgrade-nextjs-16' MCP prompt to upgrade first

Next.js exposes an MCP (Model Context Protocol) endpoint at /_next/mcp when started with:
- For Next.js < 16: experimental.mcpServer: true in next.config.js, OR __NEXT_EXPERIMENTAL_MCP_SERVER=true environment variable
- For Next.js >= 16: MCP is enabled by default (no configuration needed)

This tool allows you to:
1. Discover running Next.js dev servers and their ports
2. List available MCP tools/functions exposed by the Next.js runtime
3. Call those tools to interact with Next.js internals (e.g., get errors,get route info, get logs, runtime diagnostics, etc.)

Typical workflow:
1. Use action='discover_servers' to find running Next.js servers (optional - auto-discovery will be attempted)
2. Use action='list_tools' with the discovered port to see available tools and their input schemas
3. Use action='call_tool' with port, toolName, and args (as an object, only if required) to invoke a specific tool

IMPORTANT: When calling tools:
- The 'args' parameter MUST be an object (e.g., {key: "value"}), NOT a string
- If a tool doesn't require arguments, OMIT the 'args' parameter entirely - do NOT pass {} or "{}"
- Check the tool's inputSchema from 'list_tools' to see what arguments are required

If the MCP endpoint is not available:
1. Check if you're running Next.js 16+ (if not, use the 'upgrade-nextjs-16' prompt)
2. For Next.js < 16: Ensure the dev server is started with __NEXT_EXPERIMENTAL_MCP_SERVER=true or experimental.mcpServer: true
3. For Next.js >= 16: MCP should be enabled by default - check if the dev server is running
#### Tool: **`upgrade_nextjs_16`**
Guide through upgrading Next.js to version 16.

CRITICAL: Runs the official codemod FIRST (requires clean git state) for automatic upgrades and fixes, then handles remaining issues manually. The codemod upgrades Next.js, React, and React DOM automatically.

Covers:
- Next.js version upgrade to 16
- Async API changes (params, searchParams, cookies, headers)
- Config migration (next.config changes)
- Image defaults and optimization
- Parallel routes and dynamic segments
- Deprecated API removals
- React 19 compatibility

The codemod requires:
- Clean git working directory (commit or stash changes first)
- Node.js 18+
- npm/pnpm/yarn/bun installed

After codemod runs, provides manual guidance for any remaining issues not covered by the codemod.
## Use this MCP Server

```json
{
  "mcpServers": {
    "next-devtools-mcp": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "mcp/next-devtools-mcp"
      ]
    }
  }
}