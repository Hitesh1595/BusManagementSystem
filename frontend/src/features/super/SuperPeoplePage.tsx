import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import { Search, UserCog, UserPlus } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { Pagination } from "@/components/common/Pagination";
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
import { schoolsApi, usersApi } from "@/lib/api";
import type { ManagedUser, Role } from "@/lib/api/types";
import { qk } from "@/lib/query";
import { usePagination } from "@/lib/hooks/usePagination";

type RoleFilter = "all" | "school_admin" | "driver" | "parent";

export function SuperPeoplePage() {
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [role, setRole] = useState<RoleFilter>("all");
  const [school, setSchool] = useState<string>("all");
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    const id = setTimeout(() => setQ(search.trim()), 300);
    return () => clearTimeout(id);
  }, [search]);

  const schoolsQuery = useQuery({
    queryKey: qk.schools({ limit: 100 }),
    queryFn: () => schoolsApi.list({ limit: 100 }),
  });
  const schoolName = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of schoolsQuery.data?.items ?? []) map.set(s.id, s.name);
    return map;
  }, [schoolsQuery.data]);

  const { limit, offset, setOffset } = usePagination(25, `${role}:${school}:${q}`);
  const params = {
    role: role === "all" ? undefined : (role as Role),
    school: school === "all" ? undefined : school,
    q: q || undefined,
    limit,
    offset,
  };
  const list = useQuery({
    queryKey: qk.users(params),
    queryFn: () => usersApi.list(params),
    placeholderData: keepPreviousData,
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
      toast.success("Password reset — the user must sign in again.");
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
        title="People"
        description="Search users across every school. Provision a school's admin, add staff, or manage accounts."
        actions={
          <Button onClick={() => setAdding(true)}>
            <UserPlus className="size-4" />
            Add staff
          </Button>
        }
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or email"
            className="pl-9"
          />
        </div>
        <Select value={school} onValueChange={setSchool}>
          <SelectTrigger className="sm:w-52">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All schools</SelectItem>
            {(schoolsQuery.data?.items ?? []).map((s) => (
              <SelectItem key={s.id} value={s.id}>
                {s.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={role} onValueChange={(v) => setRole(v as RoleFilter)}>
          <SelectTrigger className="sm:w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All roles</SelectItem>
            <SelectItem value="school_admin">Admins</SelectItem>
            <SelectItem value="driver">Drivers</SelectItem>
            <SelectItem value="parent">Parents</SelectItem>
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
          title="No people found"
          description="Try a different search, school, or role."
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>School</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell className="font-medium">{u.full_name}</TableCell>
                    <TableCell className="text-muted-foreground">{u.email}</TableCell>
                    <TableCell>
                      <Badge variant="muted" className="capitalize">
                        {u.role.replace("_", " ")}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {u.school_id ? (schoolName.get(u.school_id) ?? "—") : "Platform"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {maskPhone(u.phone)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={u.is_active ? "success" : "muted"}>
                        {u.is_active ? "Active" : "Inactive"}
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

      {!list.isLoading && !list.isError && items.length > 0 ? (
        <Pagination
          total={list.data?.total ?? 0}
          limit={limit}
          offset={offset}
          onOffsetChange={setOffset}
          isFetching={list.isFetching}
        />
      ) : null}

      <AddStaffDialog
        open={adding}
        onOpenChange={setAdding}
        schools={(schoolsQuery.data?.items ?? []).map((s) => ({
          id: s.id,
          name: s.name,
        }))}
      />

      {/* Reset password */}
      <Dialog
        open={resetting !== null}
        onOpenChange={(o) => !resetMutation.isPending && !o && closeReset()}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset password</DialogTitle>
            <DialogDescription>
              Set a new password for {resetting?.full_name}
              {resetting?.school_id ? ` (${schoolName.get(resetting.school_id) ?? "—"})` : ""}.
              They'll be signed out everywhere and must use the new password.
            </DialogDescription>
          </DialogHeader>
          <form
            id="super-reset-form"
            onSubmit={(e) => {
              e.preventDefault();
              setTouched(true);
              if (canSubmit) resetMutation.mutate();
            }}
            className="space-y-4"
          >
            <Field
              label="New password"
              htmlFor="super-reset-pw"
              required
              error={touched && tooShort ? "At least 8 characters" : undefined}
            >
              <Input
                id="super-reset-pw"
                type="password"
                autoComplete="new-password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                autoFocus
              />
            </Field>
            <Field
              label="Confirm password"
              htmlFor="super-reset-confirm"
              required
              error={mismatch ? "Passwords don't match" : undefined}
            >
              <Input
                id="super-reset-confirm"
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
              Cancel
            </Button>
            <Button type="submit" form="super-reset-form" disabled={!canSubmit}>
              {resetMutation.isPending ? <Spinner /> : null}
              Reset password
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
