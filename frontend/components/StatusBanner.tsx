"use client";

import { useState, useEffect, useRef } from "react";
import { AlertCircle, Clock, X, CheckCircle2 } from "lucide-react";
import { useBackendStatus } from "./BackendStatusProvider";
import { Button } from "@/components/ui/button";
import type { BackendHealthServiceStatus } from "@/lib/types";

function getBannerMessage(
  state: "unreachable" | "degraded" | "ready",
  services: BackendHealthServiceStatus[],
): string {
  if (state === "unreachable") return "Connecting to backend...";
  if (state === "degraded") {
    const ollama = services.find((s) => s.name === "ollama");
    const qdrant = services.find((s) => s.name === "qdrant");
    if (ollama?.status === "error") return "AI models are being downloaded...";
    if (qdrant?.status === "error") return "Vector database is starting up.";
    return "Some services are starting up...";
  }
  return "Backend connected";
}

export function StatusBanner() {
  const { state, services } = useBackendStatus();
  const [dismissed, setDismissed] = useState(false);
  const wasNotReadyRef = useRef(false);

  // Track if backend was ever NOT ready (to show "connected" message briefly)
  useEffect(() => {
    if (state !== "ready") {
      wasNotReadyRef.current = true;
      setDismissed(false);
    }
  }, [state]);

  // If backend was never down, don't show anything
  if (state === "ready" && !wasNotReadyRef.current) return null;

  // If dismissed, hide
  if (dismissed) return null;

  // If ready and was previously down, show dismissible success
  const isReady = state === "ready";
  const isUnreachable = state === "unreachable";

  const message = getBannerMessage(state, services);

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 border-b border-border px-4 py-2 text-sm"
      style={{
        backgroundColor: isReady
          ? "color-mix(in srgb, var(--primary) 8%, transparent)"
          : isUnreachable
            ? "color-mix(in srgb, var(--destructive) 12%, transparent)"
            : "color-mix(in srgb, var(--warning) 12%, transparent)",
        color: isReady
          ? "var(--primary)"
          : isUnreachable
            ? "var(--destructive)"
            : "var(--warning)",
      }}
    >
      {isReady ? (
        <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
      ) : isUnreachable ? (
        <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
      ) : (
        <Clock className="size-4 shrink-0" aria-hidden="true" />
      )}
      <span className="flex-1">{message}</span>
      {isReady && (
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => setDismissed(true)}
          aria-label="Dismiss status banner"
        >
          <X className="h-3 w-3" />
        </Button>
      )}
    </div>
  );
}
