import { useTranslation } from "react-i18next";
import { Check, UserX, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn, initials } from "@/lib/utils";

export type Mark = "boarded" | "absent" | null;

interface StudentAttendanceRowProps {
  name: string;
  /** Current driver selection for this student (null = not yet chosen). */
  mark: Mark;
  /** Parent pre-marked absent — greyed, no toggle. */
  parentAbsent?: boolean;
  /** Already submitted/locked for this stop. */
  locked?: boolean;
  onChange?: (mark: Exclude<Mark, null>) => void;
}

/**
 * One student row with BIG Boarded / Absent toggle buttons (driver screen).
 * Parent-pre-absent students render greyed and are not toggleable.
 */
export function StudentAttendanceRow({
  name,
  mark,
  parentAbsent,
  locked,
  onChange,
}: StudentAttendanceRowProps) {
  const { t } = useTranslation("driver");

  if (parentAbsent) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-border bg-muted/40 p-3 opacity-70">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-semibold text-muted-foreground">
          {initials(name)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-muted-foreground line-through">
            {name}
          </p>
          <p className="text-xs text-muted-foreground">
            {t("run.absentByParent", "Absent (marked by parent)")}
          </p>
        </div>
        <UserX className="size-5 shrink-0 text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-3 sm:flex-row sm:items-center">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-secondary text-sm font-semibold text-secondary-foreground">
          {initials(name)}
        </span>
        <p className="min-w-0 flex-1 truncate text-base font-medium">{name}</p>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:flex sm:w-auto">
        <Button
          type="button"
          size="lg"
          variant={mark === "boarded" ? "success" : "outline"}
          disabled={locked}
          aria-pressed={mark === "boarded"}
          onClick={() => onChange?.("boarded")}
          className={cn("min-h-14", mark !== "boarded" && "text-success")}
        >
          <Check className="size-5" />
          {t("run.boarded", "Boarded")}
        </Button>
        <Button
          type="button"
          size="lg"
          variant={mark === "absent" ? "destructive" : "outline"}
          disabled={locked}
          aria-pressed={mark === "absent"}
          onClick={() => onChange?.("absent")}
          className={cn("min-h-14", mark !== "absent" && "text-destructive")}
        >
          <X className="size-5" />
          {t("run.absent", "Absent")}
        </Button>
      </div>
    </div>
  );
}
