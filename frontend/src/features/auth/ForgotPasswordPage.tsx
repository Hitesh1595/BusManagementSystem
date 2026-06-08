import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, MailCheck, Send } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
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
import { authApi } from "@/lib/api/auth";

const schema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
});

type ForgotValues = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const { t } = useTranslation(["auth"]);
  const [sent, setSent] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "" },
  });

  const successMessage = t(
    "auth:forgot.success",
    "If that email exists, a reset link is on its way.",
  );

  const onSubmit = async (values: ForgotValues) => {
    // Always show the same message regardless of outcome to avoid leaking
    // which emails are registered.
    try {
      await authApi.forgotPassword(values.email);
    } catch {
      /* intentionally swallowed — never reveal account existence */
    } finally {
      setSent(true);
    }
  };

  if (sent) {
    return (
      <Card>
        <CardHeader>
          <div className="mb-2 flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
            <MailCheck className="size-6" />
          </div>
          <CardTitle>{t("auth:forgot.checkInbox", "Check your inbox")}</CardTitle>
          <CardDescription>{successMessage}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild variant="outline" size="lg" className="w-full">
            <Link to="/login">
              <ArrowLeft className="size-4" />
              {t("auth:forgot.backToLogin", "Back to sign in")}
            </Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("auth:forgot.title", "Reset your password")}</CardTitle>
        <CardDescription>
          {t(
            "auth:forgot.subtitle",
            "Enter your email and we’ll send you a link to reset your password.",
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
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

          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={isSubmitting}
          >
            <Send className="size-4" />
            {isSubmitting
              ? t("auth:forgot.submitting", "Sending…")
              : t("auth:forgot.submit", "Send reset link")}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          <Link
            to="/login"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            {t("auth:forgot.backToLogin", "Back to sign in")}
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
