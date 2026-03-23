"""Automated smoke test for The Embedinator.

FR-022, FR-023, FR-024: 13 checks covering health, API, ingestion, and chat.
Exit code: 0=all pass, 1=any fail, 2=script error.
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Run: pip install httpx", file=sys.stderr)
    sys.exit(2)


@dataclass
class SmokeCheck:
    name: str
    result: str = "PENDING"   # PASS | FAIL | SKIP
    elapsed_seconds: float = 0.0
    error_message: str = ""


async def run_smoke_tests(
    base_url: str,
    frontend_url: str,
    timeout: int,
    skip_chat: bool,
) -> list[SmokeCheck]:
    checks: list[SmokeCheck] = []
    ts = int(time.time())
    test_collection_id: str = ""
    test_job_id: str = ""

    async with httpx.AsyncClient(timeout=timeout) as client:

        # --- Check 1: Backend health ---
        check = SmokeCheck("Backend health")
        t0 = time.monotonic()
        try:
            resp = await client.get(f"{base_url}/api/health")
            if resp.status_code == 200:
                check.result = "PASS"
            else:
                check.result = "FAIL"
                check.error_message = f"HTTP {resp.status_code}"
        except Exception as exc:
            check.result = "FAIL"
            check.error_message = str(exc)
        check.elapsed_seconds = time.monotonic() - t0
        checks.append(check)

        # --- Check 2: Backend liveness ---
        check = SmokeCheck("Backend liveness")
        t0 = time.monotonic()
        try:
            resp = await client.get(f"{base_url}/api/health/live")
            if resp.status_code == 200:
                check.result = "PASS"
            else:
                check.result = "FAIL"
                check.error_message = f"HTTP {resp.status_code}"
        except Exception as exc:
            check.result = "FAIL"
            check.error_message = str(exc)
        check.elapsed_seconds = time.monotonic() - t0
        checks.append(check)

        # --- Check 3: Frontend health ---
        check = SmokeCheck("Frontend health")
        t0 = time.monotonic()
        try:
            resp = await client.get(f"{frontend_url}/healthz")
            if resp.status_code == 200:
                check.result = "PASS"
            else:
                check.result = "FAIL"
                check.error_message = f"HTTP {resp.status_code}"
        except Exception as exc:
            check.result = "FAIL"
            check.error_message = str(exc)
        check.elapsed_seconds = time.monotonic() - t0
        checks.append(check)

        # --- Check 4: Frontend serves HTML ---
        check = SmokeCheck("Frontend serves HTML")
        t0 = time.monotonic()
        try:
            resp = await client.get(f"{frontend_url}/")
            body = resp.text
            if "<html" in body or "__next" in body or "<!DOCTYPE" in body.lower():
                check.result = "PASS"
            else:
                check.result = "FAIL"
                check.error_message = "Response does not contain <html or __next"
        except Exception as exc:
            check.result = "FAIL"
            check.error_message = str(exc)
        check.elapsed_seconds = time.monotonic() - t0
        checks.append(check)

        # --- Check 5: Collections API ---
        check = SmokeCheck("Collections API")
        t0 = time.monotonic()
        try:
            resp = await client.get(f"{base_url}/api/collections")
            if resp.status_code == 200:
                data = resp.json()
                # Expect either a list or {"collections": [...]}
                if isinstance(data, list) or (isinstance(data, dict) and "collections" in data):
                    check.result = "PASS"
                else:
                    check.result = "FAIL"
                    check.error_message = f"Unexpected JSON structure: {type(data)}"
            else:
                check.result = "FAIL"
                check.error_message = f"HTTP {resp.status_code}"
        except Exception as exc:
            check.result = "FAIL"
            check.error_message = str(exc)
        check.elapsed_seconds = time.monotonic() - t0
        checks.append(check)

        # --- Check 6: Models API ---
        check = SmokeCheck("Models API")
        t0 = time.monotonic()
        try:
            resp = await client.get(f"{base_url}/api/models/llm")
            if resp.status_code == 200:
                check.result = "PASS"
            else:
                check.result = "FAIL"
                check.error_message = f"HTTP {resp.status_code}"
        except Exception as exc:
            check.result = "FAIL"
            check.error_message = str(exc)
        check.elapsed_seconds = time.monotonic() - t0
        checks.append(check)

        # --- Check 7: Settings API ---
        check = SmokeCheck("Settings API")
        t0 = time.monotonic()
        try:
            resp = await client.get(f"{base_url}/api/settings")
            if resp.status_code == 200:
                check.result = "PASS"
            else:
                check.result = "FAIL"
                check.error_message = f"HTTP {resp.status_code}"
        except Exception as exc:
            check.result = "FAIL"
            check.error_message = str(exc)
        check.elapsed_seconds = time.monotonic() - t0
        checks.append(check)

        # --- Check 8: Create collection ---
        check = SmokeCheck("Create collection")
        t0 = time.monotonic()
        try:
            collection_name = f"smoke-test-{ts}"
            resp = await client.post(
                f"{base_url}/api/collections",
                json={"name": collection_name, "description": "Smoke test collection"},
            )
            if resp.status_code == 201:
                data = resp.json()
                test_collection_id = data.get("id", "")
                if test_collection_id:
                    check.result = "PASS"
                else:
                    check.result = "FAIL"
                    check.error_message = "Response missing 'id' field"
            else:
                check.result = "FAIL"
                check.error_message = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:
            check.result = "FAIL"
            check.error_message = str(exc)
        check.elapsed_seconds = time.monotonic() - t0
        checks.append(check)

        # --- Check 9: Upload document ---
        check = SmokeCheck("Upload document")
        t0 = time.monotonic()
        if not test_collection_id:
            check.result = "FAIL"
            check.error_message = "No collection ID (check 8 failed)"
        else:
            # Find sample.md relative to this script
            script_dir = Path(__file__).parent
            sample_file = script_dir.parent / "tests" / "fixtures" / "sample.md"
            if not sample_file.exists():
                check.result = "FAIL"
                check.error_message = f"Fixture not found: {sample_file}"
            else:
                try:
                    with open(sample_file, "rb") as f:
                        resp = await client.post(
                            f"{base_url}/api/collections/{test_collection_id}/ingest",
                            files={"file": ("sample.md", f, "text/markdown")},
                        )
                    if resp.status_code in (200, 202):
                        data = resp.json()
                        test_job_id = data.get("job_id", "")
                        if test_job_id:
                            check.result = "PASS"
                        else:
                            check.result = "FAIL"
                            check.error_message = "Response missing 'job_id'"
                    else:
                        check.result = "FAIL"
                        check.error_message = f"HTTP {resp.status_code}: {resp.text[:200]}"
                except Exception as exc:
                    check.result = "FAIL"
                    check.error_message = str(exc)
        check.elapsed_seconds = time.monotonic() - t0
        checks.append(check)

        # --- Check 10: Ingestion complete ---
        check = SmokeCheck("Ingestion complete")
        t0 = time.monotonic()
        if not test_job_id or not test_collection_id:
            check.result = "FAIL"
            check.error_message = "No job_id (check 9 failed)"
        else:
            poll_url = f"{base_url}/api/collections/{test_collection_id}/ingest/{test_job_id}"
            deadline = time.monotonic() + 120  # 2 minutes
            final_status = None
            try:
                while time.monotonic() < deadline:
                    resp = await client.get(poll_url)
                    if resp.status_code == 200:
                        data = resp.json()
                        status = data.get("status", "")
                        if status in ("completed", "complete"):
                            final_status = "complete"
                            break
                        elif status == "failed":
                            final_status = "failed"
                            break
                    await asyncio.sleep(3)

                if final_status == "complete":
                    check.result = "PASS"
                elif final_status == "failed":
                    check.result = "FAIL"
                    check.error_message = "Ingestion job failed"
                else:
                    check.result = "FAIL"
                    check.error_message = "Timeout: ingestion did not complete within 2 minutes"
            except Exception as exc:
                check.result = "FAIL"
                check.error_message = str(exc)
        check.elapsed_seconds = time.monotonic() - t0
        checks.append(check)

        # --- Check 11: Chat response ---
        check = SmokeCheck("Chat response")
        t0 = time.monotonic()
        chat_ndjson_lines: list[dict] = []
        if skip_chat:
            check.result = "SKIP"
            check.error_message = "Skipped via --skip-chat"
        elif not test_collection_id:
            check.result = "FAIL"
            check.error_message = "No collection ID (check 8 failed)"
        else:
            try:
                chat_timeout = httpx.Timeout(timeout=60.0, connect=5.0)
                async with httpx.AsyncClient(timeout=chat_timeout) as chat_client:
                    async with chat_client.stream(
                        "POST",
                        f"{base_url}/api/chat",
                        json={
                            "message": "What topics are covered in this document?",
                            "collection_ids": [test_collection_id],
                            "session_id": f"smoke-test-{ts}",
                        },
                    ) as resp:
                        if resp.status_code == 200:
                            async for line in resp.aiter_lines():
                                line = line.strip()
                                if line:
                                    try:
                                        chat_ndjson_lines.append(json.loads(line))
                                    except json.JSONDecodeError:
                                        pass
                            if chat_ndjson_lines:
                                check.result = "PASS"
                            else:
                                check.result = "FAIL"
                                check.error_message = "No NDJSON lines received"
                        else:
                            check.result = "FAIL"
                            check.error_message = f"HTTP {resp.status_code}"
            except httpx.TimeoutException:
                check.result = "FAIL"
                check.error_message = "Timeout after 60s — no response received"
            except Exception as exc:
                check.result = "FAIL"
                check.error_message = str(exc)
        check.elapsed_seconds = time.monotonic() - t0
        checks.append(check)

        # --- Check 12: Chat has citation ---
        check = SmokeCheck("Chat has citation")
        t0 = time.monotonic()
        if skip_chat:
            check.result = "SKIP"
            check.error_message = "Skipped via --skip-chat"
        elif not chat_ndjson_lines:
            check.result = "FAIL"
            check.error_message = "No chat response (check 11 failed)"
        else:
            has_citation = False
            for event in chat_ndjson_lines:
                if event.get("type") in ("citation", "metadata"):
                    citations = event.get("citations", [])
                    if citations:
                        has_citation = True
                        break
            if has_citation:
                check.result = "PASS"
            else:
                check.result = "FAIL"
                check.error_message = "No citations found in NDJSON response"
        check.elapsed_seconds = time.monotonic() - t0
        checks.append(check)

        # --- Check 13: Cleanup ---
        check = SmokeCheck("Cleanup")
        t0 = time.monotonic()
        if not test_collection_id:
            check.result = "FAIL"
            check.error_message = "No collection to clean up"
        else:
            try:
                resp = await client.delete(f"{base_url}/api/collections/{test_collection_id}")
                if resp.status_code in (200, 204):
                    check.result = "PASS"
                else:
                    check.result = "FAIL"
                    check.error_message = f"HTTP {resp.status_code}"
            except Exception as exc:
                check.result = "FAIL"
                check.error_message = str(exc)
        check.elapsed_seconds = time.monotonic() - t0
        checks.append(check)

    return checks


def print_results(checks: list[SmokeCheck]) -> int:
    """Print results in contract format. Returns exit code."""
    print("\nThe Embedinator — Smoke Test")
    print("============================\n")

    total = len(checks)
    passed = sum(1 for c in checks if c.result == "PASS")
    failed = [i + 1 for i, c in enumerate(checks) if c.result == "FAIL"]

    for i, check in enumerate(checks, 1):
        symbol = {
            "PASS": "[PASS]",
            "FAIL": "[FAIL]",
            "SKIP": "[SKIP]",
            "PENDING": "[PEND]",
        }.get(check.result, "[????]")
        print(f"{symbol} {i:2d}. {check.name} ({check.elapsed_seconds:.2f}s)")
        if check.error_message:
            print(f"          Error: {check.error_message}")

    print("\n============================")
    if failed:
        non_skip = sum(1 for c in checks if c.result != "SKIP")
        print(f"Results: {passed}/{total} passed, {len(failed)} failed")
        print(f"Failed: {', '.join(str(n) for n in failed)}")
        return 1
    else:
        skipped = sum(1 for c in checks if c.result == "SKIP")
        if skipped:
            print(f"Results: {passed}/{total} passed ({skipped} skipped)")
        else:
            print(f"Results: {total}/{total} passed")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="The Embedinator — Automated Smoke Test",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Backend API base URL",
    )
    parser.add_argument(
        "--frontend-url",
        default="http://localhost:3000",
        help="Frontend base URL",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Per-check timeout in seconds",
    )
    parser.add_argument(
        "--skip-chat",
        action="store_true",
        help="Skip chat checks (useful when Ollama is downloading models)",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        default=True,
        help="Delete test data after run (default: True)",
    )
    args = parser.parse_args()

    try:
        checks = asyncio.run(
            run_smoke_tests(
                base_url=args.base_url.rstrip("/"),
                frontend_url=args.frontend_url.rstrip("/"),
                timeout=args.timeout,
                skip_chat=args.skip_chat,
            )
        )
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"Script error: {exc}", file=sys.stderr)
        sys.exit(2)

    exit_code = print_results(checks)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
