import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Spinner } from "@/components/ui/spinner";
import { Wordmark } from "@/components/common/Brand";
import { AuthLayout } from "@/components/layout/AuthLayout";
import { homeForRole } from "@/components/layout/navConfig";
import { useAuthStore } from "@/stores/auth";
import type { Role } from "@/lib/api/types";

export function FullSplash() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <Wordmark className="scale-110" />
      <Spinner className="size-6 text-primary" />
    </div>
  );
}

/** Public routes (auth screens). Authenticated users are bounced to their home. */
export function PublicOnly() {
  const status = useAuthStore((s) => s.status);
  const user = useAuthStore((s) => s.user);
  if (status === "loading") return <FullSplash />;
  if (status === "authenticated" && user)
    return <Navigate to={homeForRole(user.role)} replace />;
  return (
    <AuthLayout>
      <Outlet />
    </AuthLayout>
  );
}

/** Gate a route subtree to one or more roles. */
export function RequireRole({ role }: { role: Role | Role[] }) {
  const status = useAuthStore((s) => s.status);
  const user = useAuthStore((s) => s.user);
  const location = useLocation();

  if (status === "loading") return <FullSplash />;
  if (status === "unauthenticated" || !user)
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;

  const roles = Array.isArray(role) ? role : [role];
  if (!roles.includes(user.role))
    return <Navigate to={homeForRole(user.role)} replace />;

  return <Outlet />;
}
