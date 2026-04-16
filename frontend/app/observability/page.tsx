"use client";

import { useState, useEffect, type ComponentType } from "react";

export default function ObservabilityPage() {
  const [Client, setClient] = useState<ComponentType | null>(null);

  useEffect(() => {
    import("@/components/ObservabilityClient").then((mod) => {
      setClient(() => mod.default);
    });
  }, []);

  if (!Client) {
    return (
      <main className="mx-auto max-w-7xl space-y-10 px-4 py-8 sm:px-6 lg:px-8">
        <h1 className="text-2xl font-bold text-foreground">Observability</h1>
        <p className="text-muted-foreground">Loading dashboard...</p>
      </main>
    );
  }

  return <Client />;
}
