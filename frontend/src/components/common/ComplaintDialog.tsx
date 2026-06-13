import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { Field } from "@/components/common/Field";
import { complaintsApi } from "@/lib/api";
import { getErrorMessage } from "@/lib/api/client";
import type { ComplaintAgainst } from "@/lib/api/types";
import { queryClient } from "@/lib/query";

const AGAINST: { value: ComplaintAgainst; label: string }[] = [
  { value: "driver", label: "Driver" },
  { value: "route", label: "Route" },
  { value: "vehicle", label: "Vehicle" },
  { value: "general", label: "General" },
];

/** Raise a complaint (parent or driver). Optionally pre-link a trip. */
export function ComplaintDialog({
  open,
  onOpenChange,
  tripId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tripId?: string;
}) {
  const [against, setAgainst] = useState<ComplaintAgainst>("general");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");

  const reset = () => {
    setAgainst("general");
    setSubject("");
    setDescription("");
  };

  const mut = useMutation({
    mutationFn: () =>
      complaintsApi.create({
        against_type: against,
        trip_id: tripId ?? null,
        subject: subject.trim(),
        description: description.trim(),
      }),
    onSuccess: () => {
      toast.success("Complaint submitted — your school will review it.");
      void queryClient.invalidateQueries({ queryKey: ["complaints"] });
      reset();
      onOpenChange(false);
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const canSubmit = subject.trim().length > 0 && description.trim().length > 0;

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (mut.isPending) return;
        if (!o) reset();
        onOpenChange(o);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Report an issue</DialogTitle>
          <DialogDescription>
            Raise a complaint about a driver, route, vehicle, or the service in general.
          </DialogDescription>
        </DialogHeader>
        <form
          id="complaint-form"
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (canSubmit) mut.mutate();
          }}
        >
          <Field label="About" required>
            <Select value={against} onValueChange={(v) => setAgainst(v as ComplaintAgainst)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AGAINST.map((a) => (
                  <SelectItem key={a.value} value={a.value}>
                    {a.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Subject" htmlFor="complaint-subject" required>
            <Input
              id="complaint-subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              maxLength={200}
              autoFocus
            />
          </Field>
          <Field label="Details" htmlFor="complaint-desc" required>
            <Textarea
              id="complaint-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              placeholder="Describe what happened…"
            />
          </Field>
        </form>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={mut.isPending}
          >
            Cancel
          </Button>
          <Button type="submit" form="complaint-form" disabled={!canSubmit || mut.isPending}>
            {mut.isPending ? <Spinner /> : null}
            Submit
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
