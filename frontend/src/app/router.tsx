import { useEffect } from "react";
import { createBrowserRouter, Outlet, RouterProvider } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { NotFound } from "@/components/common/NotFound";
import { useAuthStore } from "@/stores/auth";
import { PublicOnly, RequireRole } from "./guards";
import { LandingPage } from "@/features/marketing/LandingPage";
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

const router = createBrowserRouter([
  {
    element: <RootBoot />,
    children: [
      { path: "/", element: <LandingPage /> },
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
