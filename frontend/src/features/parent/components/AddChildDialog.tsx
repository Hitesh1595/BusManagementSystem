import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { UserPlus } from "lucide-react";
import { toast } from "sonner";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Field } from "@/components/common/Field";
import { GeocodeSearch } from "@/components/maps";
import { studentsApi } from "@/lib/api/students";
import { getErrorMessage } from "@/lib/api/client";
import type { LatLng } from "@/lib/api/types";

interface AddChildDialogProps {
  trigger?: ReactNode;
}

/** Dialog to register a new child under the signed-in parent. */
export function AddChildDialog({ trigger }: AddChildDialogProps) {
  const { t } = useTranslation("parent");
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  const [fullName, setFullName] = useState("");
  const [grade, setGrade] = useState("");
  const [section, setSection] = useState("");
  const [pickupAddress, setPickupAddress] = useState("");
  const [pickupLocation, setPickupLocation] = useState<LatLng | null>(null);
  const [touched, setTouched] = useState(false);

  const reset = () => {
    setFullName("");
    setGrade("");
    setSection("");
    setPickupAddress("");
    setPickupLocation(null);
    setTouched(false);
  };

  const mutation = useMutation({
    mutationFn: () =>
      studentsApi.create({
        full_name: fullName.trim(),
        grade: grade.trim() || null,
        section: section.trim() || null,
        pickup_address: pickupAddress.trim() || null,
        pickup_location: pickupLocation,
      }),
    onSuccess: () => {
      toast.success(t("addChild.success", "Child added"));
      void queryClient.invalidateQueries({ queryKey: ["students"] });
      reset();
      setOpen(false);
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!fullName.trim()) return;
    mutation.mutate();
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (mutation.isPending) return;
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        {trigger ?? (
          <Button>
            <UserPlus className="size-4" />
            {t("addChild.trigger", "Add child")}
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("addChild.title", "Add a child")}</DialogTitle>
          <DialogDescription>
            {t(
              "addChild.subtitle",
              "Register your child so you can request transport and track their bus.",
            )}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <Field
            label={t("addChild.name", "Full name")}
            htmlFor="child-name"
            required
            error={
              touched && !fullName.trim()
                ? t("addChild.nameRequired", "Name is required")
                : undefined
            }
          >
            <Input
              id="child-name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder={t("addChild.namePlaceholder", "e.g. Aarav Sharma")}
              autoFocus
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label={t("addChild.grade", "Grade")} htmlFor="child-grade">
              <Input
                id="child-grade"
                value={grade}
                onChange={(e) => setGrade(e.target.value)}
                placeholder={t("addChild.gradePlaceholder", "e.g. 5")}
              />
            </Field>
            <Field label={t("addChild.section", "Section")} htmlFor="child-section">
              <Input
                id="child-section"
                value={section}
                onChange={(e) => setSection(e.target.value)}
                placeholder={t("addChild.sectionPlaceholder", "e.g. A")}
              />
            </Field>
          </div>

          <Field
            label={t("addChild.pickup", "Pickup location (optional)")}
            hint={
              pickupLocation
                ? t("addChild.pickupSet", "Pickup location set. You can refine it later when requesting transport.")
                : t("addChild.pickupHint", "Search an address now, or add it later.")
            }
          >
            <GeocodeSearch
              placeholder={t("addChild.pickupPlaceholder", "Search your pickup address")}
              onSelect={(r) => {
                setPickupAddress(r.label);
                setPickupLocation({ lat: r.lat, lng: r.lng });
              }}
            />
          </Field>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={mutation.isPending}
            >
              {t("common.cancel", "Cancel")}
            </Button>
            <Button type="submit" disabled={mutation.isPending || !fullName.trim()}>
              {mutation.isPending ? <Spinner /> : <UserPlus className="size-4" />}
              {t("addChild.submit", "Add child")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
