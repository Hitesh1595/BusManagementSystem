import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Bus,
  ClipboardCheck,
  Lock,
  PlayCircle,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";

import { PageHeader } from "@/components/common/PageHeader";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { notificationsApi } from "@/lib/api/notifications";
import { getErrorMessage } from "@/lib/api/client";
import { useAuthStore } from "@/stores/auth";

/** Opt-out-able notification categories (default ON when the key is absent). */
type PrefKey = "trip_updates" | "bus_approaching" | "attendance";

function PrefRow({
  icon: Icon,
  label,
  hint,
  checked,
  disabled,
  locked,
  onToggle,
}: {
  icon: LucideIcon;
  label: string;
  hint: string;
  checked: boolean;
  disabled?: boolean;
  locked?: boolean;
  onToggle?: (next: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-border px-4 py-3">
      <div className="flex min-w-0 items-start gap-3">
        <Icon className="mt-0.5 size-5 shrink-0 text-muted-foreground" aria-hidden />
        <div className="min-w-0">
          <p className="text-sm font-medium">{label}</p>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>
      </div>
      {locked ? (
        <Lock className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      ) : (
        <Switch checked={checked} disabled={disabled} onCheckedChange={onToggle} />
      )}
    </div>
  );
}

export function SettingsPage() {
  const { t } = useTranslation("parent");
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  const prefs = (user?.notification_prefs ?? {}) as Record<string, unknown>;
  // Absent key = opted in; a category is muted only when explicitly set to false.
  const enabled = (key: PrefKey) => prefs[key] !== false;

  const mutation = useMutation({
    mutationFn: (patch: Record<string, boolean>) =>
      notificationsApi.updatePreferences(patch),
    onSuccess: (res) => {
      if (user) setUser({ ...user, notification_prefs: res.notification_prefs });
      toast.success(t("settings.saved", "Preferences updated"));
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const rows: { key: PrefKey; icon: LucideIcon; label: string; hint: string }[] = [
    {
      key: "trip_updates",
      icon: PlayCircle,
      label: t("settings.tripUpdatesLabel", "Trip updates"),
      hint: t(
        "settings.tripUpdatesHint",
        "When your child's bus starts and finishes its trip.",
      ),
    },
    {
      key: "bus_approaching",
      icon: Bus,
      label: t("settings.busApproachingLabel", "Bus approaching"),
      hint: t(
        "settings.busApproachingHint",
        "A heads-up when the bus is near your child's stop.",
      ),
    },
    {
      key: "attendance",
      icon: ClipboardCheck,
      label: t("settings.attendanceLabel", "Boarding & drop-off"),
      hint: t(
        "settings.attendanceHint",
        "When your child boards the bus and is dropped off.",
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("settings.title", "Settings")}
        description={t(
          "settings.desc",
          "Choose which updates you'd like to receive.",
        )}
      />

      <Card>
        <CardHeader>
          <CardTitle>
            {t("settings.notifTitle", "Notification preferences")}
          </CardTitle>
          <CardDescription>
            {t(
              "settings.notifDesc",
              "Turn off the updates you don't need. Critical safety alerts stay on.",
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {rows.map((r) => (
            <PrefRow
              key={r.key}
              icon={r.icon}
              label={r.label}
              hint={r.hint}
              checked={enabled(r.key)}
              disabled={mutation.isPending}
              onToggle={(next) => mutation.mutate({ [r.key]: next })}
            />
          ))}
          <PrefRow
            icon={ShieldAlert}
            label={t("settings.safetyLabel", "Safety alerts")}
            hint={t(
              "settings.safetyHint",
              "Child-safety alerts are always delivered and can't be turned off.",
            )}
            checked
            locked
          />
        </CardContent>
      </Card>
    </div>
  );
}
