import { AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";

export function CenteredSpinner({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-muted-foreground">
      <Spinner className="size-6" />
      {label ? <span className="text-sm">{label}</span> : null}
    </div>
  );
}

export function CardListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border p-4">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="mt-3 h-3 w-2/3" />
        </div>
      ))}
    </div>
  );
}

export function ErrorState({
  message = "Couldn't load this. Please try again.",
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <AlertTriangle className="size-7 text-destructive" />
      <p className="text-sm text-muted-foreground">{message}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}

/** Render loading/error/empty/data for a TanStack Query result in one place. */
export function QueryState<T>({
  isLoading,
  isError,
  data,
  onRetry,
  loading,
  empty,
  isEmpty,
  children,
}: {
  isLoading: boolean;
  isError: boolean;
  data: T | undefined;
  onRetry?: () => void;
  loading?: ReactNode;
  empty?: ReactNode;
  isEmpty?: (data: T) => boolean;
  children: (data: T) => ReactNode;
}) {
  if (isLoading) return <>{loading ?? <CardListSkeleton />}</>;
  if (isError || data === undefined)
    return <ErrorState onRetry={onRetry} />;
  if (empty && isEmpty?.(data)) return <>{empty}</>;
  return <>{children(data)}</>;
}
