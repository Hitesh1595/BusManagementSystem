import { useState } from "react";
import { Star } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Star rating. Interactive when `onChange` is given; otherwise read-only
 * (supports fractional `value` for displaying an average).
 */
export function RatingStars({
  value,
  onChange,
  size = "md",
  className,
}: {
  value: number;
  onChange?: (value: number) => void;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const interactive = typeof onChange === "function";
  const shown = hover ?? value;
  const px = size === "lg" ? "size-8" : size === "sm" ? "size-4" : "size-6";

  return (
    <div
      className={cn("flex items-center gap-0.5", className)}
      role={interactive ? "radiogroup" : undefined}
    >
      {[1, 2, 3, 4, 5].map((n) => {
        const filled = shown >= n - 0.25; // fractional-friendly threshold
        const star = (
          <Star
            className={cn(
              px,
              filled ? "fill-warning text-warning" : "fill-transparent text-muted-foreground/40",
            )}
          />
        );
        if (!interactive) return <span key={n}>{star}</span>;
        return (
          <button
            key={n}
            type="button"
            aria-label={`${n} star${n > 1 ? "s" : ""}`}
            onClick={() => onChange!(n)}
            onMouseEnter={() => setHover(n)}
            onMouseLeave={() => setHover(null)}
            className="cursor-pointer transition-transform hover:scale-110"
          >
            {star}
          </button>
        );
      })}
    </div>
  );
}
