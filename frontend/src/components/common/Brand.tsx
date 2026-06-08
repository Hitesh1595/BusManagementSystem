import { Bus } from "lucide-react";
import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm",
        className,
      )}
    >
      <Bus className="size-5" />
    </span>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <Logo />
      <span className="text-lg font-bold tracking-tight">
        Yatra<span className="text-primary">Track</span>
      </span>
    </span>
  );
}
