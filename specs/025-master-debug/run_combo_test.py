#!/usr/bin/env python3
"""
Spec-25 Phase 4 — Model Combo Testing Script
Runs 5 standardized queries against the chat API, measures TTFT and total latency,
captures full response for manual scoring.

Usage:
    python3 run_combo_test.py --combo 1 --model qwen2.5:7b
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime

BACKEND = "http://localhost:8000"
COLLECTION_ID = "9d465858-672a-435b-bcfd-6b4bc6a5dc67"  # default: arcas

# 5 Standardized queries based on ARCA fiscal web services content
QUERIES = [
    {
        "id": "Q1",
        "archetype": "Factual",
        # Direct fact retrievable from WSSEG manual (R.G. 2668)
        "text": "¿Cuál es el nombre del web service y la resolución general que regula los seguros de caución electrónicos en ARCA?",
        "expected_keywords": ["WSSEG", "2.668", "caución"],
    },
    {
        "id": "Q2",
        "archetype": "Multi-hop",
        # Requires combining WSAA auth docs + WSFEV1 usage — cross-document
        "text": "Para utilizar WSFEV1 de facturación electrónica, ¿qué servicio de autenticación se debe invocar primero y qué credencial devuelve para las llamadas posteriores?",
        "expected_keywords": ["WSAA", "Ticket", "TA", "autenticación", "autorización"],
    },
    {
        "id": "Q3",
        "archetype": "Comparison",
        # Contrast WSFEV1 (electronic invoices) vs WSBFEV1 (electronic fiscal bonds)
        "text": "¿Cuál es la diferencia entre WSFEV1 y WSBFEV1? ¿Qué tipo de comprobantes maneja cada servicio?",
        "expected_keywords": ["WSFEV1", "WSBFEV1", "facturas", "bonos", "diferencia"],
    },
    {
        "id": "Q4",
        "archetype": "Out-of-domain",
        # Topic completely outside ARCA fiscal domain
        "text": "¿Cómo configuro un entorno virtual de Python e instalo Django para desarrollo web?",
        "expected_keywords": [],  # Should get low-confidence / no-result answer
    },
    {
        "id": "Q5",
        "archetype": "Vague",
        # Intentionally ambiguous — no specific context
        "text": "¿Cómo funciona el proceso de autorización?",
        "expected_keywords": [],  # Ambiguous — could refer to any of the web services
    },
]


def get_vram_mib():
    """Get current VRAM used in MiB."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return int(result.stdout.strip())
    except Exception:
        return -1


def run_query(query_text: str, combo_id: int) -> dict:
    """Stream a query and return timing + full response."""
    payload = json.dumps(
        {
            "message": query_text,
            "collection_ids": [COLLECTION_ID],
        }
    )

    t_start = time.perf_counter()
    t_first_chunk = None
    chunks = []
    citations = []
    confidence = None
    full_text = ""

    # Use requests-like streaming via subprocess curl
    proc = subprocess.Popen(
        [
            "curl",
            "-sf",
            "-N",
            "-X",
            "POST",
            f"{BACKEND}/api/chat",
            "-H",
            "Content-Type: application/json",
            "-d",
            payload,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    vram_samples = []
    for raw_line in proc.stdout:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type", "")

        if event_type == "chunk" and t_first_chunk is None:
            t_first_chunk = time.perf_counter()

        if event_type == "chunk":
            token = event.get("content", event.get("text", ""))
            full_text += token
            chunks.append(token)

        elif event_type == "citations":
            citations = event.get("citations", [])

        elif event_type == "confidence":
            confidence = event.get("score", event.get("confidence"))

        elif event_type == "done":
            break

        # Sample VRAM during inference
        if len(vram_samples) < 5:
            vram_samples.append(get_vram_mib())

    proc.wait()
    t_end = time.perf_counter()

    ttft_ms = int((t_first_chunk - t_start) * 1000) if t_first_chunk else -1
    total_ms = int((t_end - t_start) * 1000)
    peak_vram = max(vram_samples) if vram_samples else -1
    chunk_count = len(chunks)
    tokens_per_sec = round(chunk_count / ((t_end - t_start) or 1), 1)

    return {
        "ttft_ms": ttft_ms,
        "total_ms": total_ms,
        "peak_vram_mib": peak_vram,
        "chunk_count": chunk_count,
        "tokens_per_sec": tokens_per_sec,
        "citation_count": len(citations),
        "citations": [c.get("document_name", c.get("filename", "?"))[:60] for c in citations[:5]],
        "confidence": confidence,
        "response_preview": full_text[:400],
        "response_full": full_text,
    }


def main():
    global COLLECTION_ID
    parser = argparse.ArgumentParser()
    parser.add_argument("--combo", type=int, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--embedding", default="nomic-embed-text")
    parser.add_argument("--collection", default=COLLECTION_ID, help="Collection UUID to query")
    args = parser.parse_args()

    print(f"\n{'=' * 70}")
    print(f"COMBO {args.combo}: {args.model} + {args.embedding}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 70}\n")

    # Override collection if specified
    COLLECTION_ID = args.collection

    idle_vram = get_vram_mib()
    print(f"Idle VRAM: {idle_vram} MiB")
    print(f"Collection: {COLLECTION_ID}\n")

    results = []
    for q in QUERIES:
        print(f"--- {q['id']} ({q['archetype']}) ---")
        print(f"Query: {q['text']}")
        result = run_query(q["text"], args.combo)
        results.append({"query": q, "result": result})

        print(
            f"TTFT: {result['ttft_ms']}ms | Total: {result['total_ms']}ms | "
            f"Peak VRAM: {result['peak_vram_mib']}MiB | Chunks: {result['chunk_count']} "
            f"({result['tokens_per_sec']} tok/s) | Citations: {result['citation_count']} | "
            f"Confidence: {result['confidence']}"
        )
        print(f"Response (first 300 chars):\n{result['response_preview'][:300]}")
        if result["citations"]:
            print(f"Sources: {', '.join(result['citations'])}")
        print()

        time.sleep(2)  # Brief pause between queries

    # Summary table
    print(f"\n{'=' * 70}")
    print(f"COMBO {args.combo} SUMMARY — {args.model} + {args.embedding}")
    print(f"{'=' * 70}")
    print(f"{'Query':<6} {'TTFT(ms)':<10} {'Total(ms)':<11} {'PeakVRAM':<10} {'Chunks':<8} {'Citations'}")
    for r in results:
        res = r["result"]
        print(
            f"{r['query']['id']:<6} {res['ttft_ms']:<10} {res['total_ms']:<11} "
            f"{res['peak_vram_mib']:<10} {res['chunk_count']:<8} {res['citation_count']}"
        )

    avg_ttft = int(sum(r["result"]["ttft_ms"] for r in results) / len(results))
    avg_total = int(sum(r["result"]["total_ms"] for r in results) / len(results))
    max_vram = max(r["result"]["peak_vram_mib"] for r in results)
    print(f"{'AVG':<6} {avg_ttft:<10} {avg_total:<11} {max_vram:<10}")
    print(f"\nIdle VRAM: {idle_vram} MiB | Peak during inference: {max_vram} MiB")

    # Save full results to JSON
    output = {
        "combo": args.combo,
        "llm": args.model,
        "embedding": args.embedding,
        "idle_vram_mib": idle_vram,
        "results": results,
        "avg_ttft_ms": avg_ttft,
        "avg_total_ms": avg_total,
        "peak_vram_mib": max_vram,
        "timestamp": datetime.now().isoformat(),
    }
    outfile = f"/tmp/combo{args.combo}_results.json"
    with open(outfile, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {outfile}")


if __name__ == "__main__":
    main()
