import { zodResolver } from "@hookform/resolvers/zod";
import { UserPlus } from "lucide-react";
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
  join_code: z
    .string()
    .min(1, "School join code is required")
    .transform((v) => v.trim().toUpperCase()),
  full_name: z.string().min(1, "Your full name is required"),
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  phone: z
    .string()
    .optional()
    .transform((v) => (v && v.trim() ? v.trim() : undefined)),
});

type RegisterValues = z.infer<typeof schema>;

export default function RegisterPage() {
  const { t } = useTranslation(["auth"]);
  const navigate = useNavigate();
  const registerUser = useAuthStore((s) => s.register);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      join_code: "",
      full_name: "",
      email: "",
      password: "",
      phone: "",
    },
  });

  const onSubmit = async (values: RegisterValues) => {
    setFormError(null);
    try {
      const user = await registerUser({
        join_code: values.join_code,
        full_name: values.full_name,
        email: values.email,
        password: values.password,
        ...(values.phone ? { phone: values.phone } : {}),
      });
      toast.success(
        t("auth:register.created", "Account created. Welcome to YatraTrack!"),
      );
      navigate(homeForRole(user.role), { replace: true });
    } catch (e) {
      const parsed = await parseApiError(e);
      let message = parsed.message;
      if (parsed.status === 404 || parsed.code === "invalid_join_code") {
        message = t(
          "auth:register.badCode",
          "That school join code wasn’t recognised. Please check it with your school.",
        );
      } else if (parsed.status === 409) {
        message = t(
          "auth:register.emailTaken",
          "An account with this email already exists. Try signing in instead.",
        );
      }
      setFormError(message);
      toast.error(message);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("auth:register.title", "Create your account")}</CardTitle>
        <CardDescription>
          {t(
            "auth:register.subtitle",
            "Parents can self-register with the join code provided by their school.",
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
            label={t("auth:fields.joinCode", "School join code")}
            htmlFor="join_code"
            error={errors.join_code?.message}
            hint={t(
              "auth:register.joinCodeHint",
              "Ask your school for this code.",
            )}
            required
          >
            <Input
              id="join_code"
              autoCapitalize="characters"
              autoComplete="off"
              placeholder="ABC123"
              className="uppercase tracking-wider"
              aria-invalid={!!errors.join_code}
              {...register("join_code")}
            />
          </Field>

          <Field
            label={t("auth:fields.fullName", "Full name")}
            htmlFor="full_name"
            error={errors.full_name?.message}
            required
          >
            <Input
              id="full_name"
              type="text"
              autoComplete="name"
              placeholder="Priya Sharma"
              aria-invalid={!!errors.full_name}
              {...register("full_name")}
            />
          </Field>

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
            hint={t(
              "auth:register.passwordHint",
              "At least 8 characters.",
            )}
            required
          >
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              placeholder="••••••••"
              aria-invalid={!!errors.password}
              {...register("password")}
            />
          </Field>

          <Field
            label={t("auth:fields.phone", "Phone (optional)")}
            htmlFor="phone"
            error={errors.phone?.message}
          >
            <Input
              id="phone"
              type="tel"
              autoComplete="tel"
              inputMode="tel"
              placeholder="+91 98765 43210"
              aria-invalid={!!errors.phone}
              {...register("phone")}
            />
          </Field>

          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={isSubmitting}
          >
            <UserPlus className="size-4" />
            {isSubmitting
              ? t("auth:register.submitting", "Creating account…")
              : t("auth:register.submit", "Create account")}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          {t("auth:register.haveAccount", "Already have an account?")}{" "}
          <Link
            to="/login"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            {t("auth:register.signIn", "Sign in")}
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
