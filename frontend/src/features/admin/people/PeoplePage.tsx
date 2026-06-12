import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Search, UserCog, UserPlus } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { AddStaffDialog, StaffRowMenu } from "@/components/common/StaffControls";
import { EmptyState } from "@/components/common/EmptyState";
import { CardListSkeleton, ErrorState } from "@/components/common/States";
import { Field } from "@/components/common/Field";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { maskPhone } from "@/lib/format";
import { getErrorMessage } from "@/lib/api/client";
import { usersApi } from "@/lib/api";
import type { ManagedUser } from "@/lib/api/types";
import { qk } from "@/lib/query";

type RoleFilter = "all" | "school_admin" | "driver" | "parent";

export function PeoplePage() {
  const { t } = useTranslation("admin");

  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [role, setRole] = useState<RoleFilter>("all");
  const [adding, setAdding] = useState(false);

  // Debounce the search box into the query param.
  useEffect(() => {
    const id = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(id);
  }, [search]);

  const params = {
    role: role === "all" ? undefined : role,
    q: q || undefined,
    limit: 100,
  };
  const list = useQuery({
    queryKey: qk.users(params),
    queryFn: () => usersApi.list(params),
  });

  // ---- Reset password ----
  const [resetting, setResetting] = useState<ManagedUser | null>(null);
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [touched, setTouched] = useState(false);

  const closeReset = () => {
    setResetting(null);
    setPw("");
    setConfirm("");
    setTouched(false);
  };

  const resetMutation = useMutation({
    mutationFn: () => usersApi.resetPassword(resetting!.id, pw),
    onSuccess: () => {
      toast.success(
        t("people.resetDone", "Password reset — the user must sign in again."),
      );
      closeReset();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const tooShort = pw.length < 8;
  const mismatch = confirm.length > 0 && pw !== confirm;
  const canSubmit = !tooShort && pw === confirm && !resetMutation.isPending;

  const items = list.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("people.title", "People")}
        description={t(
          "people.desc",
          "Admins, drivers, and parents in your school. Add staff, edit, or deactivate accounts.",
        )}
        actions={
          <Button onClick={() => setAdding(true)}>
            <UserPlus className="size-4" />
            {t("people.add", "Add staff")}
          </Button>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("people.searchPlaceholder", "Search by name or email")}
            className="pl-9"
          />
        </div>
        <Select value={role} onValueChange={(v) => setRole(v as RoleFilter)}>
          <SelectTrigger className="sm:w-44">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("people.allRoles", "All people")}</SelectItem>
            <SelectItem value="school_admin">{t("people.admins", "Admins")}</SelectItem>
            <SelectItem value="driver">{t("people.drivers", "Drivers")}</SelectItem>
            <SelectItem value="parent">{t("people.parents", "Parents")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {list.isLoading ? (
        <CardListSkeleton rows={5} />
      ) : list.isError ? (
        <ErrorState onRetry={() => list.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={UserCog}
          title={t("people.emptyTitle", "No people found")}
          description={t(
            "people.emptyBody",
            "Drivers you create and parents who self-register will appear here.",
          )}
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("people.colName", "Name")}</TableHead>
                  <TableHead>{t("people.colEmail", "Email")}</TableHead>
                  <TableHead>{t("people.colRole", "Role")}</TableHead>
                  <TableHead>{t("people.colPhone", "Phone")}</TableHead>
                  <TableHead>{t("people.colStatus", "Status")}</TableHead>
                  <TableHead className="text-right">
                    {t("people.colActions", "Actions")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell className="font-medium">{u.full_name}</TableCell>
                    <TableCell className="text-muted-foreground">{u.email}</TableCell>
                    <TableCell>
                      <Badge variant="muted" className="capitalize">
                        {u.role}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {maskPhone(u.phone)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={u.is_active ? "success" : "muted"}>
                        {u.is_active
                          ? t("people.active", "Active")
                          : t("people.inactive", "Inactive")}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <StaffRowMenu
                        user={u}
                        onReset={(usr) => {
                          setPw("");
                          setConfirm("");
                          setTouched(false);
                          setResetting(usr);
                        }}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <AddStaffDialog open={adding} onOpenChange={setAdding} />

      {/* Reset password */}
      <Dialog
        open={resetting !== null}
        onOpenChange={(o) => !resetMutation.isPending && !o && closeReset()}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("people.resetTitle", "Reset password")}</DialogTitle>
            <DialogDescription>
              {t(
                "people.resetDesc",
                "Set a new password for {{name}}. They'll be signed out everywhere and must use the new password.",
                { name: resetting?.full_name ?? "" },
              )}
            </DialogDescription>
          </DialogHeader>
          <form
            id="reset-pw-form"
            onSubmit={(e) => {
              e.preventDefault();
              setTouched(true);
              if (canSubmit) resetMutation.mutate();
            }}
            className="space-y-4"
          >
            <Field
              label={t("people.newPassword", "New password")}
              htmlFor="reset-pw"
              required
              error={touched && tooShort ? t("people.pwTooShort", "At least 8 characters") : undefined}
            >
              <Input
                id="reset-pw"
                type="password"
                autoComplete="new-password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                autoFocus
              />
            </Field>
            <Field
              label={t("people.confirmPassword", "Confirm password")}
              htmlFor="reset-confirm"
              required
              error={mismatch ? t("people.pwMismatch", "Passwords don't match") : undefined}
            >
              <Input
                id="reset-confirm"
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            </Field>
          </form>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={closeReset}
              disabled={resetMutation.isPending}
            >
              {t("common.cancel", "Cancel")}
            </Button>
            <Button type="submit" form="reset-pw-form" disabled={!canSubmit}>
              {resetMutation.isPending ? <Spinner /> : null}
              {t("people.reset", "Reset password")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
