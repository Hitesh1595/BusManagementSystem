/**
 * Shared staff-management controls for the admin + super People screens:
 *   - <AddStaffDialog>  create a driver/admin (reveals a one-time temp password)
 *   - <StaffRowMenu>    per-row Edit · Activate/Deactivate · Reset password
 *
 * Both screens keep their own reset-password dialog; the row menu defers to it
 * via the `onReset` callback so that flow stays unchanged.
 */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Check, Copy, MoreHorizontal, Pencil, Power, PowerOff } from "lucide-react";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Field } from "@/components/common/Field";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { usersApi } from "@/lib/api";
import { getErrorMessage } from "@/lib/api/client";
import type { ManagedUser } from "@/lib/api/types";
import { queryClient } from "@/lib/query";

const invalidateUsers = () =>
  queryClient.invalidateQueries({ queryKey: ["users"] });

type StaffRole = "driver" | "school_admin";

function CopyInline({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard unavailable */
        }
      }}
    >
      {copied ? <Check className="size-4 text-success" /> : <Copy className="size-4" />}
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

export function AddStaffDialog({
  open,
  onOpenChange,
  schools,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** super_admin: pass the school list to show a school selector. Omit for school_admin. */
  schools?: { id: string; name: string }[];
}) {
  const [role, setRole] = useState<StaffRole>("driver");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [schoolId, setSchoolId] = useState("");
  const [created, setCreated] = useState<{ email: string; temp: string } | null>(null);

  const needsSchool = Array.isArray(schools);

  const reset = () => {
    setRole("driver");
    setEmail("");
    setFullName("");
    setPhone("");
    setSchoolId("");
    setCreated(null);
  };

  const createMut = useMutation({
    mutationFn: () =>
      usersApi.create({
        role,
        email: email.trim().toLowerCase(),
        full_name: fullName.trim(),
        phone: phone.trim() || undefined,
        school_id: needsSchool ? schoolId : undefined,
      }),
    onSuccess: (res) => {
      setCreated({ email: res.user.email, temp: res.temp_password });
      invalidateUsers();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const emailOk = /.+@.+\..+/.test(email.trim());
  const canSubmit =
    emailOk && fullName.trim().length > 0 && (!needsSchool || schoolId.length > 0);

  const closeAndReset = () => {
    reset();
    onOpenChange(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (createMut.isPending) return;
        if (!o) reset();
        onOpenChange(o);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add staff</DialogTitle>
          <DialogDescription>
            Create a driver or admin account. They'll receive a temporary password to
            sign in and change.
          </DialogDescription>
        </DialogHeader>

        {created ? (
          <div className="space-y-3">
            <p className="text-sm">
              Account created for <strong>{created.email}</strong>. Share this temporary
              password now — it won't be shown again:
            </p>
            <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 p-3">
              <code className="flex-1 break-all text-sm font-medium">{created.temp}</code>
              <CopyInline value={created.temp} />
            </div>
          </div>
        ) : (
          <form
            id="add-staff-form"
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (canSubmit) createMut.mutate();
            }}
          >
            <Field label="Role" required>
              <Select value={role} onValueChange={(v) => setRole(v as StaffRole)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="driver">Driver</SelectItem>
                  <SelectItem value="school_admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </Field>

            {needsSchool ? (
              <Field label="School" required>
                <Select value={schoolId} onValueChange={setSchoolId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a school" />
                  </SelectTrigger>
                  <SelectContent>
                    {schools!.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            ) : null}

            <Field label="Full name" htmlFor="staff-name" required>
              <Input
                id="staff-name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoFocus
              />
            </Field>
            <Field label="Email" htmlFor="staff-email" required>
              <Input
                id="staff-email"
                type="email"
                autoComplete="off"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
            <Field label="Phone" htmlFor="staff-phone">
              <Input
                id="staff-phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </Field>
          </form>
        )}

        <DialogFooter>
          {created ? (
            <Button onClick={closeAndReset}>Done</Button>
          ) : (
            <>
              <Button
                type="button"
                variant="outline"
                onClick={closeAndReset}
                disabled={createMut.isPending}
              >
                Cancel
              </Button>
              <Button type="submit" form="add-staff-form" disabled={!canSubmit || createMut.isPending}>
                {createMut.isPending ? <Spinner /> : null}
                Create
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function StaffRowMenu({
  user,
  onReset,
}: {
  user: ManagedUser;
  onReset: (user: ManagedUser) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [confirmingDeactivate, setConfirmingDeactivate] = useState(false);
  const [fullName, setFullName] = useState(user.full_name);
  const [phone, setPhone] = useState(user.phone ?? "");

  // super_admin accounts can't be managed through this screen.
  const manageable = user.role !== "super_admin";

  const updateMut = useMutation({
    mutationFn: () =>
      usersApi.update(user.id, {
        full_name: fullName.trim(),
        phone: phone.trim() || null,
      }),
    onSuccess: () => {
      toast.success("User updated");
      invalidateUsers();
      setEditing(false);
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const activateMut = useMutation({
    mutationFn: () => usersApi.activate(user.id),
    onSuccess: () => {
      toast.success("User activated");
      invalidateUsers();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="Actions">
            <MoreHorizontal className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          {manageable ? (
            <DropdownMenuItem
              onSelect={() => {
                setFullName(user.full_name);
                setPhone(user.phone ?? "");
                setEditing(true);
              }}
            >
              <Pencil className="size-4" />
              Edit
            </DropdownMenuItem>
          ) : null}

          {manageable ? (
            user.is_active ? (
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onSelect={() => setConfirmingDeactivate(true)}
              >
                <PowerOff className="size-4" />
                Deactivate
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem onSelect={() => activateMut.mutate()}>
                <Power className="size-4" />
                Activate
              </DropdownMenuItem>
            )
          ) : null}

          {manageable ? <DropdownMenuSeparator /> : null}

          <DropdownMenuItem onSelect={() => onReset(user)}>
            Reset password
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Edit */}
      <Dialog
        open={editing}
        onOpenChange={(o) => !updateMut.isPending && setEditing(o)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit {user.full_name}</DialogTitle>
            <DialogDescription>Update name and phone.</DialogDescription>
          </DialogHeader>
          <form
            id="edit-user-form"
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (fullName.trim().length > 0) updateMut.mutate();
            }}
          >
            <Field label="Full name" htmlFor="edit-name" required>
              <Input
                id="edit-name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoFocus
              />
            </Field>
            <Field label="Phone" htmlFor="edit-phone">
              <Input
                id="edit-phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </Field>
          </form>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setEditing(false)}
              disabled={updateMut.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="edit-user-form"
              disabled={updateMut.isPending || fullName.trim().length === 0}
            >
              {updateMut.isPending ? <Spinner /> : null}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Deactivate confirm */}
      <ConfirmDialog
        open={confirmingDeactivate}
        onOpenChange={setConfirmingDeactivate}
        title={`Deactivate ${user.full_name}?`}
        description="They'll be signed out everywhere and can't sign in until reactivated."
        confirmLabel="Deactivate"
        destructive
        onConfirm={async () => {
          try {
            await usersApi.deactivate(user.id);
            toast.success("User deactivated");
            invalidateUsers();
          } catch (e) {
            toast.error(await getErrorMessage(e));
          }
        }}
      />
    </>
  );
}
