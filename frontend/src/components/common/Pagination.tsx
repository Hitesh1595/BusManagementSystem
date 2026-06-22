import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PaginationProps {
  /** Total rows the server reports (the `total` from the list envelope). */
  total: number;
  /** Page size currently requested. */
  limit: number;
  /** Current zero-based offset. */
  offset: number;
  onOffsetChange: (offset: number) => void;
  /** Disable the controls while the next page is in flight. */
  isFetching?: boolean;
  className?: string;
}

/**
 * Shared list pagination: shows "Showing X–Y of N" (which also surfaces the
 * result count the API always returned but no page ever read) plus Prev/Next.
 * The nav is hidden when everything fits on one page, so it's safe to drop on
 * any list — small lists just show the count.
 */
export function Pagination({
  total,
  limit,
  offset,
  onOffsetChange,
  isFetching,
  className,
}: PaginationProps) {
  const { t } = useTranslation();
  if (total <= 0) return null;

  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  const canPrev = offset > 0;
  const canNext = offset + limit < total;
  const multiPage = total > limit;

  return (
    <div className={cn("flex items-center justify-between gap-3 pt-1", className)}>
      <p className="text-sm text-muted-foreground" aria-live="polite">
        {t("common.pagination.showing", "Showing {{from}}–{{to}} of {{total}}", {
          from,
          to,
          total,
        })}
      </p>
      {multiPage ? (
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onOffsetChange(Math.max(0, offset - limit))}
            disabled={!canPrev || isFetching}
            aria-label={t("common.pagination.prev", "Previous page")}
          >
            <ChevronLeft className="size-4" />
            {t("common.pagination.prevLabel", "Previous")}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onOffsetChange(offset + limit)}
            disabled={!canNext || isFetching}
            aria-label={t("common.pagination.next", "Next page")}
          >
            {t("common.pagination.nextLabel", "Next")}
            <ChevronRight className="size-4" />
          </Button>
        </div>
      ) : null}
    </div>
  );
}
