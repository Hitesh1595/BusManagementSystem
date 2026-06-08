import { useEffect } from "react";
import {
  createBrowserRouter,
  Navigate,
  Outlet,
  RouterProvider,
} from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { NotFound } from "@/components/common/NotFound";
import { homeForRole } from "@/components/layout/navConfig";
import { useAuthStore } from "@/stores/auth";
import { FullSplash, PublicOnly, RequireRole } from "./guards";
import { authRoutes } from "@/features/auth/routes";
import { parentRoutes } from "@/features/parent/routes";
import { driverRoutes } from "@/features/driver/routes";
import { adminRoutes } from "@/features/admin/routes";
import { superRoutes } from "@/features/super/routes";

/** Restores the session once, then renders the routed app. */
function RootBoot() {
  const bootstrap = useAuthStore((s) => s.bootstrap);
  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);
  return <Outlet />;
}

/** "/" → role home or login. */
function RootRedirect() {
  const status = useAuthStore((s) => s.status);
  const user = useAuthStore((s) => s.user);
  if (status === "loading") return <FullSplash />;
  if (user) return <Navigate to={homeForRole(user.role)} replace />;
  return <Navigate to="/login" replace />;
}

const router = createBrowserRouter([
  {
    element: <RootBoot />,
    children: [
      { path: "/", element: <RootRedirect /> },
      { element: <PublicOnly />, children: authRoutes },
      {
        path: "/parent",
        element: <RequireRole role="parent" />,
        children: [{ element: <AppLayout />, children: parentRoutes }],
      },
      {
        path: "/driver",
        element: <RequireRole role="driver" />,
        children: [{ element: <AppLayout />, children: driverRoutes }],
      },
      {
        path: "/admin",
        element: <RequireRole role="school_admin" />,
        children: [{ element: <AppLayout />, children: adminRoutes }],
      },
      {
        path: "/super",
        element: <RequireRole role="super_admin" />,
        children: [{ element: <AppLayout />, children: superRoutes }],
      },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
