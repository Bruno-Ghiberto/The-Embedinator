import { Skeleton } from "@/components/ui/skeleton";

export default function ObservabilityLoading() {
  return (
    <main className="mx-auto max-w-7xl space-y-10 px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="text-2xl font-bold text-foreground">Observability</h1>
      <section>
        <h2 className="mb-4 text-lg font-semibold text-foreground">
          System Health
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 rounded-lg" />
          ))}
        </div>
      </section>
      <section>
        <h2 className="mb-4 text-lg font-semibold text-foreground">
          Query Analytics
        </h2>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Skeleton className="h-[300px] rounded-lg" />
          <Skeleton className="h-[300px] rounded-lg" />
        </div>
      </section>
      <Skeleton className="h-[300px] w-full rounded-lg" />
      <section>
        <h2 className="mb-4 text-lg font-semibold text-foreground">
          Query Traces
        </h2>
        <Skeleton className="h-40 w-full rounded-lg" />
      </section>
      <section>
        <h2 className="mb-4 text-lg font-semibold text-foreground">
          Collection Statistics
        </h2>
        <Skeleton className="h-40 w-full rounded-lg" />
      </section>
    </main>
  );
}
