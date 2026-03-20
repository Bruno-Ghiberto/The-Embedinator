"use client";

import React from "react";
import useSWR from "swr";
import { getHealth } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { HealthService, HealthStatus } from "@/lib/types";

// ─── Status dot color mapping ─────────────────────────────────────────────────

function statusDotClass(status: string): string {
  switch (status) {
    case "ok":
      return "bg-[var(--color-success)]";
    case "degraded":
      return "bg-[var(--color-warning)]";
    case "error":
      return "bg-[var(--color-destructive)]";
    default:
      return "bg-[var(--color-text-muted)]";
  }
}

// ─── ServiceCard ──────────────────────────────────────────────────────────────

interface ServiceCardProps {
  service: HealthService;
}

const ServiceCard = React.memo(function ServiceCard({ service }: ServiceCardProps) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="capitalize">{service.name}</span>
          <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--color-text-muted)]">
            <span
              className={cn("inline-block h-2 w-2 rounded-full", statusDotClass(service.status))}
              aria-label={`Status: ${service.status}`}
            />
            {service.status}
          </span>
        </CardTitle>
      </CardHeader>

      <CardContent>
        {service.latency_ms !== null ? (
          <p className="text-sm text-[var(--color-text-muted)]">
            Latency:{" "}
            <span className="font-medium text-[var(--color-text-primary)]">{service.latency_ms} ms</span>
          </p>
        ) : null}

        {service.status === "error" && service.error_message ? (
          <p className="mt-2 rounded bg-[var(--color-destructive)]/10 px-2 py-1 text-xs text-[var(--color-destructive)]">
            {service.error_message}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
});

// ─── HealthDashboard ─────────────────────────────────────────────────────────

export function HealthDashboard() {
  const {
    data: health,
    error,
    isLoading,
  } = useSWR<HealthStatus>("/api/health", getHealth, {
    refreshInterval: 30_000,
    revalidateOnFocus: false,
  });

  if (isLoading) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold text-[var(--color-text-primary)]">System Health</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {["sqlite", "qdrant", "ollama"].map((name) => (
            <Skeleton key={name} className="h-24 rounded-lg" />
          ))}
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold text-[var(--color-text-primary)]">System Health</h2>
        <p className="text-sm text-[var(--color-destructive)]">Failed to load health status.</p>
      </section>
    );
  }

  if (!health) {
    return null;
  }

  const overallColor =
    health.status === "healthy" ? "text-[var(--color-success)]" : "text-[var(--color-destructive)]";

  return (
    <section>
      <div className="mb-4 flex items-center gap-3">
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">System Health</h2>
        <span className={cn("text-sm font-medium capitalize", overallColor)}>
          {health.status}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {health.services.map((service) => (
          <ServiceCard key={service.name} service={service} />
        ))}
      </div>
    </section>
  );
}
