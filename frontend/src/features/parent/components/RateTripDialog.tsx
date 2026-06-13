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
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { Field } from "@/components/common/Field";
import { RatingStars } from "@/components/common/RatingStars";
import { feedbackApi } from "@/lib/api";
import { getErrorMessage } from "@/lib/api/client";

export function RateTripDialog({
  open,
  onOpenChange,
  tripId,
  onRated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tripId: string;
  onRated?: () => void;
}) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");

  const reset = () => {
    setRating(0);
    setComment("");
  };

  const mut = useMutation({
    mutationFn: () =>
      feedbackApi.submit(tripId, { rating, comment: comment.trim() || undefined }),
    onSuccess: () => {
      toast.success("Thanks for your feedback!");
      reset();
      onOpenChange(false);
      onRated?.();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

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
          <DialogTitle>Rate this trip</DialogTitle>
          <DialogDescription>
            How was today's trip? Your rating helps the school keep service high.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <Field label="Your rating" required>
            <RatingStars value={rating} onChange={setRating} size="lg" />
          </Field>
          <Field label="Comment" htmlFor="rate-comment">
            <Textarea
              id="rate-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              placeholder="Anything to add? (optional)"
              maxLength={2000}
            />
          </Field>
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={mut.isPending}
          >
            Cancel
          </Button>
          <Button onClick={() => mut.mutate()} disabled={rating < 1 || mut.isPending}>
            {mut.isPending ? <Spinner /> : null}
            Submit
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
