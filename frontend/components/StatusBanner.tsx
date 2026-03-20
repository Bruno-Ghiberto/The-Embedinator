"use client";

import { AlertCircle, Clock } from "lucide-react";
import { useBackendStatus } from "./BackendStatusProvider";
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
  return "";
}

export function StatusBanner() {
  const { state, services } = useBackendStatus();

  if (state === "ready") return null;

  const message = getBannerMessage(state, services);
  const isUnreachable = state === "unreachable";

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 border-b border-[var(--color-border)] px-4 py-2 text-sm"
      style={{
        backgroundColor: isUnreachable
          ? "color-mix(in srgb, var(--color-destructive) 12%, transparent)"
          : "color-mix(in srgb, var(--color-warning) 12%, transparent)",
        color: isUnreachable
          ? "var(--color-destructive)"
          : "var(--color-warning)",
      }}
    >
      {isUnreachable ? (
        <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
      ) : (
        <Clock className="size-4 shrink-0" aria-hidden="true" />
      )}
      <span>{message}</span>
    </div>
  );
}
