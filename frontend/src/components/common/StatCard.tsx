import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * Metric card used on dashboards. Optionally an icon (with accent tint when the
 * value is non-zero) and an optional `to` that wraps the card in a link.
 */
export function StatCard({
  icon: Icon,
  label,
  value,
  loading,
  accent,
  to,
}: {
  icon?: LucideIcon;
  label: string;
  value: number | string | undefined;
  loading?: boolean;
  accent?: "destructive" | "warning" | "default";
  to?: string;
}) {
  const card = (
    <Card className={cn(to && "transition-colors hover:border-primary/40 hover:bg-accent/40")}>
      <CardContent className="flex items-center gap-4 p-5">
        {Icon ? (
          <span
            className={cn(
              "inline-flex size-11 shrink-0 items-center justify-center rounded-xl",
              accent === "destructive" && value
                ? "bg-destructive/15 text-destructive"
                : accent === "warning" && value
                  ? "bg-warning/15 text-warning-foreground"
                  : "bg-secondary text-secondary-foreground",
            )}
          >
            <Icon className="size-5" />
          </span>
        ) : null}
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{label}</p>
          {loading ? (
            <Skeleton className="mt-1 h-7 w-10" />
          ) : (
            <p className="text-2xl font-bold tabular-nums">{value ?? 0}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );

  return to ? (
    <Link to={to} className="group block">
      {card}
    </Link>
  ) : (
    card
  );
}
