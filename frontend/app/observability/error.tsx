"use client";

import { useEffect } from "react";

export default function ObservabilityError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Observability error boundary caught:", error);
  }, [error]);

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="text-2xl font-bold text-foreground">Observability</h1>
      <div className="rounded-lg border border-border bg-background p-6">
        <h2 className="mb-2 text-lg font-semibold">Something went wrong</h2>
        <p className="mb-4 text-sm text-muted-foreground">
          The observability dashboard encountered an error loading.
        </p>
        <button
          onClick={() => reset()}
          className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
        >
          Try again
        </button>
      </div>
    </main>
  );
}
