import { Wrench } from "lucide-react";
import { PageHeader } from "./PageHeader";
import { EmptyState } from "./EmptyState";

/** Temporary stand-in used by foundation route stubs before a feature lands. */
export function Placeholder({ title }: { title: string }) {
  return (
    <div className="space-y-6">
      <PageHeader title={title} />
      <EmptyState
        icon={Wrench}
        title="Coming together"
        description="This screen is being built."
      />
    </div>
  );
}
