import { zodResolver } from "@hookform/resolvers/zod";
import { LogIn } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
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
import { parseApiError } from "@/lib/api/client";
import { homeForRole } from "@/components/layout/navConfig";
import { useAuthStore } from "@/stores/auth";

const schema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type LoginValues = z.infer<typeof schema>;

export default function LoginPage() {
  const { t } = useTranslation(["auth"]);
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (values: LoginValues) => {
    setFormError(null);
    try {
      const user = await login(values);
      toast.success(t("auth:login.welcome", "Welcome back!"));
      navigate(homeForRole(user.role), { replace: true });
    } catch (e) {
      const parsed = await parseApiError(e);
      let message = parsed.message;
      if (parsed.status === 423) {
        message = t(
          "auth:login.locked",
          "Your account is temporarily locked after too many failed attempts. Please try again in about 15 minutes.",
        );
      } else if (parsed.status === 401) {
        message = t(
          "auth:login.invalid",
          "Incorrect email or password. Please try again.",
        );
      }
      setFormError(message);
      toast.error(message);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("auth:login.title", "Sign in")}</CardTitle>
        <CardDescription>
          {t(
            "auth:login.subtitle",
            "Welcome back. Sign in to track your school bus.",
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
            label={t("auth:fields.email", "Email")}
            htmlFor="email"
            error={errors.email?.message}
            required
          >
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              aria-invalid={!!errors.email}
              {...register("email")}
            />
          </Field>

          <Field
            label={t("auth:fields.password", "Password")}
            htmlFor="password"
            error={errors.password?.message}
            required
          >
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              aria-invalid={!!errors.password}
              {...register("password")}
            />
          </Field>

          <div className="flex justify-end">
            <Link
              to="/forgot-password"
              className="text-sm font-medium text-primary underline-offset-4 hover:underline"
            >
              {t("auth:login.forgot", "Forgot password?")}
            </Link>
          </div>

          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={isSubmitting}
          >
            <LogIn className="size-4" />
            {isSubmitting
              ? t("auth:login.submitting", "Signing in…")
              : t("auth:login.submit", "Sign in")}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          {t("auth:login.newParent", "New parent?")}{" "}
          <Link
            to="/register"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            {t("auth:login.createAccount", "Create an account")}
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
