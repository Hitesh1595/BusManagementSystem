import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Clock, Copy, KeyRound, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { CenteredSpinner, ErrorState } from "@/components/common/States";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { Field } from "@/components/common/Field";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Spinner } from "@/components/ui/spinner";
import { getErrorMessage } from "@/lib/api/client";
import { schoolsApi } from "@/lib/api";
import type { School, SchoolSettings } from "@/lib/api/types";
import { qk } from "@/lib/query";
import { useAuthStore } from "@/stores/auth";

function CopyButton({ value }: { value: string }) {
  const { t } = useTranslation("admin");
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
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
      {copied ? t("settings.copied", "Copied") : t("settings.copy", "Copy")}
    </Button>
  );
}

function SettingToggle({
  label,
  hint,
  checked,
  disabled,
  onToggle,
}: {
  label: string;
  hint: string;
  checked: boolean;
  disabled: boolean;
  onToggle: (next: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border px-4 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
      <Switch checked={checked} disabled={disabled} onCheckedChange={onToggle} />
    </div>
  );
}

export function SettingsPage() {
  const { t } = useTranslation("admin");
  const qc = useQueryClient();
  const schoolId = useAuthStore((s) => s.user?.school_id) ?? null;

  const school = useQuery({
    queryKey: schoolId ? qk.school(schoolId) : ["school", "none"],
    queryFn: () => schoolsApi.get(schoolId!),
    enabled: !!schoolId,
  });

  const [profile, setProfile] = useState({ name: "", address: "", phone: "", email: "" });
  const [regenOpen, setRegenOpen] = useState(false);

  useEffect(() => {
    if (school.data) {
      setProfile({
        name: school.data.name ?? "",
        address: school.data.address ?? "",
        phone: school.data.phone ?? "",
        email: school.data.email ?? "",
      });
    }
  }, [school.data]);

  const invalidate = () => {
    if (schoolId) qc.invalidateQueries({ queryKey: qk.school(schoolId) });
  };

  const profileMutation = useMutation({
    mutationFn: () =>
      schoolsApi.update(schoolId!, {
        name: profile.name.trim(),
        address: profile.address.trim() || undefined,
        phone: profile.phone.trim() || undefined,
        email: profile.email.trim() || undefined,
      }),
    onSuccess: (updated: School) => {
      qc.setQueryData(qk.school(schoolId!), updated);
      toast.success(t("settings.profileSaved", "School profile saved"));
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const settingsMutation = useMutation({
    mutationFn: (patch: SchoolSettings) => schoolsApi.updateSettings(schoolId!, patch),
    onSuccess: (updated: School) => {
      qc.setQueryData(qk.school(schoolId!), updated);
      toast.success(t("settings.settingSaved", "Setting updated"));
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const regenMutation = useMutation({
    mutationFn: () => schoolsApi.regenerateJoinCode(schoolId!),
    onSuccess: () => {
      toast.success(t("settings.joinRegenerated", "New join code generated"));
      invalidate();
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  if (!schoolId) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("settings.title", "School settings")} />
        <ErrorState message={t("settings.noSchool", "No school is linked to your account.")} />
      </div>
    );
  }

  if (school.isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("settings.title", "School settings")} />
        <CenteredSpinner />
      </div>
    );
  }

  if (school.isError || !school.data) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("settings.title", "School settings")} />
        <ErrorState onRetry={() => school.refetch()} />
      </div>
    );
  }

  const data = school.data;
  const settings = data.settings ?? {};

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("settings.title", "School settings")}
        description={t("settings.desc", "Profile, parent join code and preferences")}
      />

      {/* Join code */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <KeyRound className="size-5 text-primary" />
            {t("settings.joinTitle", "Parent join code")}
          </CardTitle>
          <CardDescription>
            {t(
              "settings.joinDesc",
              "Parents enter this code to self-register and link to your school.",
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="rounded-xl border border-dashed border-border bg-muted px-6 py-4 text-center sm:text-left">
            <span className="font-mono text-3xl font-bold tracking-[0.3em]">
              {data.join_code}
            </span>
          </div>
          <div className="flex gap-2">
            <CopyButton value={data.join_code} />
            <Button variant="outline" onClick={() => setRegenOpen(true)}>
              <RefreshCw className="size-4" />
              {t("settings.regenerate", "Regenerate")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Profile */}
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.profileTitle", "School profile")}</CardTitle>
          <CardDescription>
            {t("settings.profileDescText", "Shown to parents and on notifications.")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (profile.name.trim()) profileMutation.mutate();
            }}
            className="space-y-4"
          >
            <Field
              label={t("settings.fName", "School name")}
              htmlFor="s-name"
              required
            >
              <Input
                id="s-name"
                value={profile.name}
                onChange={(e) => setProfile((p) => ({ ...p, name: e.target.value }))}
              />
            </Field>
            <Field label={t("settings.fAddress", "Address")} htmlFor="s-address">
              <Input
                id="s-address"
                value={profile.address}
                onChange={(e) => setProfile((p) => ({ ...p, address: e.target.value }))}
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("settings.fPhone", "Phone")} htmlFor="s-phone">
                <Input
                  id="s-phone"
                  type="tel"
                  value={profile.phone}
                  onChange={(e) => setProfile((p) => ({ ...p, phone: e.target.value }))}
                />
              </Field>
              <Field label={t("settings.fEmail", "Email")} htmlFor="s-email">
                <Input
                  id="s-email"
                  type="email"
                  value={profile.email}
                  onChange={(e) => setProfile((p) => ({ ...p, email: e.target.value }))}
                />
              </Field>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-lg bg-muted px-4 py-2.5 text-sm text-muted-foreground">
              <span className="flex items-center gap-2">
                <Clock className="size-4" />
                {t("settings.timezone", "Timezone")}
              </span>
              <span className="font-medium text-foreground">{data.timezone}</span>
            </div>
            <div className="flex justify-end">
              <Button
                type="submit"
                disabled={profileMutation.isPending || !profile.name.trim()}
              >
                {profileMutation.isPending ? <Spinner /> : null}
                {t("settings.saveProfile", "Save profile")}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Preferences */}
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.prefsTitle", "Preferences")}</CardTitle>
          <CardDescription>
            {t("settings.prefsDesc", "Control privacy and automation for your school.")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <SettingToggle
            label={t("settings.driverPhoneLabel", "Show driver phone to parents")}
            hint={t(
              "settings.driverPhoneHint",
              "Parents can call the driver during a live trip.",
            )}
            checked={settings.driver_phone_visible === true}
            disabled={settingsMutation.isPending}
            onToggle={(next) => settingsMutation.mutate({ driver_phone_visible: next })}
          />
          <SettingToggle
            label={t("settings.autogenLabel", "Auto-generate daily trips")}
            hint={t(
              "settings.autogenHint",
              "Create morning and evening trips for active routes each day.",
            )}
            checked={settings.trip_autogen_enabled === true}
            disabled={settingsMutation.isPending}
            onToggle={(next) => settingsMutation.mutate({ trip_autogen_enabled: next })}
          />
        </CardContent>
      </Card>

      <ConfirmDialog
        open={regenOpen}
        onOpenChange={setRegenOpen}
        title={t("settings.regenTitle", "Regenerate join code?")}
        description={t(
          "settings.regenBody",
          "The current code will stop working immediately. Parents who haven't joined will need the new code.",
        )}
        confirmLabel={t("settings.regenerate", "Regenerate")}
        destructive
        onConfirm={async () => {
          await regenMutation.mutateAsync();
        }}
      />
    </div>
  );
}
