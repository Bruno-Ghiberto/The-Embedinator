import { Skeleton } from "@/components/ui/skeleton";

export default function ChatLoading() {
  return (
    <div className="flex flex-1 flex-col min-h-0 p-4 space-y-4">
      <Skeleton className="h-10 w-full" />
      <div className="flex-1 space-y-3">
        <Skeleton className="h-16 w-3/4 rounded-2xl" />
        <Skeleton className="h-24 w-2/3 rounded-2xl ml-auto" />
        <Skeleton className="h-20 w-3/4 rounded-2xl" />
      </div>
      <Skeleton className="h-12 w-full rounded-lg" />
    </div>
  );
}
