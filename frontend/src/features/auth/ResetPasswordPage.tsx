import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, KeyRound, ShieldX } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";
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
import { getErrorMessage } from "@/lib/api/client";
import { authApi } from "@/lib/api/auth";

const schema = z
  .object({
    new_password: z.string().min(8, "Password must be at least 8 characters"),
    confirm: z.string().min(1, "Please confirm your password"),
  })
  .refine((v) => v.new_password === v.confirm, {
    message: "Passwords don’t match",
    path: ["confirm"],
  });

type ResetValues = z.infer<typeof schema>;

export default function ResetPasswordPage() {
  const { t } = useTranslation(["auth"]);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetValues>({
    resolver: zodResolver(schema),
    defaultValues: { new_password: "", confirm: "" },
  });

  if (!token) {
    return (
      <Card>
        <CardHeader>
          <div className="mb-2 flex size-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
            <ShieldX className="size-6" />
          </div>
          <CardTitle>{t("auth:reset.invalidTitle", "Invalid reset link")}</CardTitle>
          <CardDescription>
            {t(
              "auth:reset.invalidBody",
              "This password reset link is missing or invalid. Please request a new one.",
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button asChild size="lg" className="w-full">
            <Link to="/forgot-password">
              {t("auth:reset.requestNew", "Request a new link")}
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg" className="w-full">
            <Link to="/login">
              <ArrowLeft className="size-4" />
              {t("auth:reset.backToLogin", "Back to sign in")}
            </Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  const onSubmit = async (values: ResetValues) => {
    setFormError(null);
    try {
      await authApi.resetPassword(token, values.new_password);
      toast.success(
        t(
          "auth:reset.success",
          "Your password has been reset. Please sign in.",
        ),
      );
      navigate("/login", { replace: true });
    } catch (e) {
      const message = await getErrorMessage(e);
      setFormError(
        t(
          "auth:reset.failed",
          "We couldn’t reset your password. The link may have expired — please request a new one.",
        ),
      );
      toast.error(message);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("auth:reset.title", "Set a new password")}</CardTitle>
        <CardDescription>
          {t(
            "auth:reset.subtitle",
            "Choose a strong new password for your account.",
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {formError ? (
            <div
              role="alert"
              className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm font-medium text-destructive"
            >
              {formError}
            </div>
          ) : null}

          <Field
            label={t("auth:reset.newPassword", "New password")}
            htmlFor="new_password"
            error={errors.new_password?.message}
            hint={t("auth:reset.passwordHint", "At least 8 characters.")}
            required
          >
            <Input
              id="new_password"
              type="password"
              autoComplete="new-password"
              placeholder="••••••••"
              aria-invalid={!!errors.new_password}
              {...register("new_password")}
            />
          </Field>

          <Field
            label={t("auth:reset.confirmPassword", "Confirm new password")}
            htmlFor="confirm"
            error={errors.confirm?.message}
            required
          >
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              placeholder="••••••••"
              aria-invalid={!!errors.confirm}
              {...register("confirm")}
            />
          </Field>

          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={isSubmitting}
          >
            <KeyRound className="size-4" />
            {isSubmitting
              ? t("auth:reset.submitting", "Resetting…")
              : t("auth:reset.submit", "Reset password")}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          <Link
            to="/login"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            {t("auth:reset.backToLogin", "Back to sign in")}
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
