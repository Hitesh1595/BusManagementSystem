import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Wordmark } from "./Brand";

export function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4 text-center">
      <Wordmark />
      <p className="text-6xl font-black text-primary">404</p>
      <p className="text-muted-foreground">This page doesn't exist.</p>
      <Button asChild>
        <Link to="/">Go home</Link>
      </Button>
    </div>
  );
}
