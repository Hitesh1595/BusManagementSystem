import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Bus, Check, MapPin, Route as RouteIcon } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/common/PageHeader";
import { Field } from "@/components/common/Field";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MapView, DraggablePin, SchoolMarker, Recenter, GeocodeSearch } from "@/components/maps";
import { cn } from "@/lib/utils";
import { getErrorMessage } from "@/lib/api/client";
import { schoolsApi, vehiclesApi } from "@/lib/api";
import { routesApi } from "@/lib/api/routes";
import type { LatLng, ScheduleType, VehicleType } from "@/lib/api/types";
import { qk } from "@/lib/query";
import { useAuthStore } from "@/stores/auth";

const VEHICLE_TYPES: VehicleType[] = ["bus", "van", "minibus", "car", "other"];
const SCHEDULE_TYPES: ScheduleType[] = ["morning", "evening", "both"];

const STEPS = [
  { key: "profile", icon: MapPin },
  { key: "vehicle", icon: Bus },
  { key: "route", icon: RouteIcon },
] as const;

function Stepper({ step }: { step: number }) {
  const { t } = useTranslation("admin");
  const labels = [
    t("setup.step1", "School"),
    t("setup.step2", "Vehicle"),
    t("setup.step3", "Route"),
  ];
  return (
    <div className="flex items-center justify-center gap-2 sm:gap-4">
      {STEPS.map((s, i) => {
        const done = i < step;
        const active = i === step;
        const Icon = s.icon;
        return (
          <div key={s.key} className="flex items-center gap-2 sm:gap-4">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "inline-flex size-9 items-center justify-center rounded-full border text-sm font-semibold transition-colors",
                  done && "border-success bg-success/15 text-success",
                  active && "border-primary bg-primary text-primary-foreground",
                  !done && !active && "border-border bg-muted text-muted-foreground",
                )}
              >
                {done ? <Check className="size-4" /> : <Icon className="size-4" />}
              </span>
              <span
                className={cn(
                  "hidden text-sm font-medium sm:inline",
                  active ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {labels[i]}
              </span>
            </div>
            {i < STEPS.length - 1 ? (
              <span className={cn("h-px w-6 sm:w-10", done ? "bg-success" : "bg-border")} />
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

export function SetupWizard() {
  const { t } = useTranslation("admin");
  const navigate = useNavigate();
  const qc = useQueryClient();
  const schoolId = useAuthStore((s) => s.user?.school_id) ?? null;

  const [step, setStep] = useState(0);

  // ---- Step 1: profile ----
  const school = useQuery({
    queryKey: schoolId ? qk.school(schoolId) : ["school", "none"],
    queryFn: () => schoolsApi.get(schoolId!),
    enabled: !!schoolId,
  });

  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [location, setLocation] = useState<LatLng | null>(null);

  useEffect(() => {
    if (school.data) {
      setName(school.data.name ?? "");
      setAddress(school.data.address ?? "");
      setLocation(school.data.school_location ?? null);
    }
  }, [school.data]);

  const profileMutation = useMutation({
    mutationFn: () =>
      schoolsApi.update(schoolId!, {
        name: name.trim(),
        address: address.trim() || undefined,
        school_location: location,
      }),
    onSuccess: (updated) => {
      qc.setQueryData(qk.school(schoolId!), updated);
      toast.success(t("setup.profileSaved", "School profile saved"));
      setStep(1);
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  // ---- Step 2: vehicle ----
  const [vehicle, setVehicle] = useState({
    plate_number: "",
    vehicle_type: "bus" as VehicleType,
    capacity: "",
  });

  const vehicleMutation = useMutation({
    mutationFn: () =>
      vehiclesApi.create({
        plate_number: vehicle.plate_number.trim().toUpperCase(),
        vehicle_type: vehicle.vehicle_type,
        capacity: Number(vehicle.capacity),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vehicles"] });
      toast.success(t("setup.vehicleAdded", "Vehicle added"));
      setStep(2);
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  // ---- Step 3: route ----
  const [route, setRoute] = useState({
    name: "",
    schedule_type: "both" as ScheduleType,
  });

  const routeMutation = useMutation({
    mutationFn: () =>
      routesApi.create({
        name: route.name.trim(),
        schedule_type: route.schedule_type,
      }),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ["routes"] });
      toast.success(t("setup.routeCreated", "Route created — now add stops"));
      navigate(`/admin/routes/${created.id}`);
    },
    onError: async (e) => toast.error(await getErrorMessage(e)),
  });

  const mapCenter = location ?? school.data?.school_location ?? null;

  const renderStep = () => {
    if (step === 0) {
      return (
        <Card>
          <CardHeader>
            <CardTitle>{t("setup.profileTitle", "School profile")}</CardTitle>
            <CardDescription>
              {t(
                "setup.profileDesc",
                "Set your school name and mark its location on the map — buses use it as the drop-off point.",
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label={t("setup.fName", "School name")} htmlFor="w-name" required>
              <Input
                id="w-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("setup.namePlaceholder", "Springfield Public School")}
              />
            </Field>
            <Field label={t("setup.fAddress", "Address")} htmlFor="w-address">
              <Input
                id="w-address"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
            </Field>
            <Field
              label={t("setup.fLocation", "School location")}
              hint={t("setup.locationHint", "Search an address or drag the pin to fine-tune.")}
            >
              <div className="space-y-2">
                <GeocodeSearch
                  placeholder={t("setup.searchPlaceholder", "Search your school address…")}
                  onSelect={(r) => {
                    setLocation({ lat: r.lat, lng: r.lng });
                    if (!address) setAddress(r.label.split(",").slice(0, 3).join(", "));
                  }}
                />
                <div className="h-[40vh] w-full overflow-hidden rounded-xl border border-border">
                  <MapView center={mapCenter} zoom={15}>
                    <Recenter point={location} zoom={16} />
                    {location ? (
                      <DraggablePin point={location} onMove={(p) => setLocation(p)} />
                    ) : (
                      school.data?.school_location && (
                        <SchoolMarker location={school.data.school_location} />
                      )
                    )}
                  </MapView>
                </div>
                {location ? (
                  <p className="text-xs text-muted-foreground">
                    {t("setup.coords", "Pin: {{lat}}, {{lng}}", {
                      lat: location.lat.toFixed(5),
                      lng: location.lng.toFixed(5),
                    })}
                  </p>
                ) : null}
              </div>
            </Field>
          </CardContent>
          <CardFooter className="justify-between">
            <Button variant="ghost" onClick={() => setStep(1)}>
              {t("setup.skip", "Skip")}
            </Button>
            <Button
              onClick={() => profileMutation.mutate()}
              disabled={!name.trim() || profileMutation.isPending}
            >
              {profileMutation.isPending ? <Spinner /> : null}
              {t("setup.saveContinue", "Save & continue")}
              <ArrowRight className="size-4" />
            </Button>
          </CardFooter>
        </Card>
      );
    }

    if (step === 1) {
      const capNum = Number(vehicle.capacity);
      const valid = vehicle.plate_number.trim() && capNum > 0;
      return (
        <Card>
          <CardHeader>
            <CardTitle>{t("setup.vehicleTitle", "Add a vehicle")}</CardTitle>
            <CardDescription>
              {t("setup.vehicleDesc", "Add at least one bus or van. You can add more later.")}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label={t("setup.fPlate", "Plate number")} htmlFor="w-plate" required>
              <Input
                id="w-plate"
                value={vehicle.plate_number}
                onChange={(e) => setVehicle((v) => ({ ...v, plate_number: e.target.value }))}
                placeholder="MH12AB1234"
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("setup.fType", "Type")} htmlFor="w-type">
                <Select
                  value={vehicle.vehicle_type}
                  onValueChange={(v) =>
                    setVehicle((s) => ({ ...s, vehicle_type: v as VehicleType }))
                  }
                >
                  <SelectTrigger id="w-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {VEHICLE_TYPES.map((vt) => (
                      <SelectItem key={vt} value={vt} className="capitalize">
                        {vt}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label={t("setup.fCapacity", "Capacity")} htmlFor="w-capacity" required>
                <Input
                  id="w-capacity"
                  type="number"
                  min={1}
                  value={vehicle.capacity}
                  onChange={(e) => setVehicle((v) => ({ ...v, capacity: e.target.value }))}
                  placeholder="40"
                />
              </Field>
            </div>
          </CardContent>
          <CardFooter className="justify-between">
            <Button variant="ghost" onClick={() => setStep(0)}>
              <ArrowLeft className="size-4" />
              {t("setup.back", "Back")}
            </Button>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setStep(2)}>
                {t("setup.skip", "Skip")}
              </Button>
              <Button
                onClick={() => vehicleMutation.mutate()}
                disabled={!valid || vehicleMutation.isPending}
              >
                {vehicleMutation.isPending ? <Spinner /> : null}
                {t("setup.addContinue", "Add & continue")}
                <ArrowRight className="size-4" />
              </Button>
            </div>
          </CardFooter>
        </Card>
      );
    }

    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("setup.routeTitle", "Create your first route")}</CardTitle>
          <CardDescription>
            {t(
              "setup.routeDesc",
              "Name your route. Next you'll add stops on the map in the route editor.",
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field label={t("setup.fRouteName", "Route name")} htmlFor="w-route" required>
            <Input
              id="w-route"
              value={route.name}
              onChange={(e) => setRoute((r) => ({ ...r, name: e.target.value }))}
              placeholder={t("setup.routeNamePlaceholder", "North Zone — Sector 12")}
            />
          </Field>
          <Field label={t("setup.fSchedule", "Schedule")} htmlFor="w-schedule">
            <Select
              value={route.schedule_type}
              onValueChange={(v) => setRoute((r) => ({ ...r, schedule_type: v as ScheduleType }))}
            >
              <SelectTrigger id="w-schedule">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SCHEDULE_TYPES.map((s) => (
                  <SelectItem key={s} value={s} className="capitalize">
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
        </CardContent>
        <CardFooter className="justify-between">
          <Button variant="ghost" onClick={() => setStep(1)}>
            <ArrowLeft className="size-4" />
            {t("setup.back", "Back")}
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => navigate("/admin")}>
              {t("setup.done", "Done")}
            </Button>
            <Button
              onClick={() => routeMutation.mutate()}
              disabled={!route.name.trim() || routeMutation.isPending}
            >
              {routeMutation.isPending ? <Spinner /> : null}
              {t("setup.createAddStops", "Create & add stops")}
              <ArrowRight className="size-4" />
            </Button>
          </div>
        </CardFooter>
      </Card>
    );
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader
        title={t("setup.title", "Set up your school")}
        description={t("setup.subtitle", "Three quick steps to get buses on the map")}
      />
      <Stepper step={step} />
      {renderStep()}
    </div>
  );
}
