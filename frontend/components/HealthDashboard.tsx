"use client";

import React from "react";
import useSWR from "swr";
import { getHealth } from "@/lib/api";
import type { HealthService, HealthStatus } from "@/lib/types";

// ─── ServiceCard ──────────────────────────────────────────────────────────────

interface ServiceCardProps {
  service: HealthService;
}

const ServiceCard = React.memo(function ServiceCard({ service }: ServiceCardProps) {
  const isOk = service.status === "ok";

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold capitalize text-gray-700">{service.name}</h3>
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
            isOk
              ? "bg-green-100 text-green-800"
              : "bg-red-100 text-red-800"
          }`}
        >
          {service.status}
        </span>
      </div>

      {service.latency_ms !== null ? (
        <p className="mt-2 text-sm text-gray-500">
          Latency:{" "}
          <span className="font-medium text-gray-800">{service.latency_ms} ms</span>
        </p>
      ) : null}

      {service.status === "error" && service.error_message ? (
        <p className="mt-2 rounded bg-red-50 px-2 py-1 text-xs text-red-700">
          {service.error_message}
        </p>
      ) : null}
    </div>
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
        <h2 className="mb-4 text-lg font-semibold text-gray-900">System Health</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {["sqlite", "qdrant", "ollama"].map((name) => (
            <div
              key={name}
              className="h-24 animate-pulse rounded-lg bg-gray-100"
            />
          ))}
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section>
        <h2 className="mb-4 text-lg font-semibold text-gray-900">System Health</h2>
        <p className="text-sm text-red-600">Failed to load health status.</p>
      </section>
    );
  }

  if (!health) {
    return null;
  }

  const overallColor =
    health.status === "healthy" ? "text-green-600" : "text-red-600";

  return (
    <section>
      <div className="mb-4 flex items-center gap-3">
        <h2 className="text-lg font-semibold text-gray-900">System Health</h2>
        <span className={`text-sm font-medium capitalize ${overallColor}`}>
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
