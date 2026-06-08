import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Wordmark } from "@/components/common/Brand";

/** Centered card layout for the auth screens with a subtle indigo hero glow. */
export function AuthLayout({ children }: { children: ReactNode }) {
  const { t } = useTranslation(["auth", "common"]);
  return (
    <div className="bg-hero-glow flex min-h-screen flex-col items-center justify-center bg-muted/20 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <Wordmark className="scale-110" />
          <p className="text-sm text-muted-foreground">
            {t("auth:brand.sub", "Live GPS, attendance and child-safety alerts.")}
          </p>
        </div>
        {children}
        <p className="mt-8 text-center text-xs text-muted-foreground">
          {t("common:app.tagline")}
        </p>
      </div>
    </div>
  );
}
