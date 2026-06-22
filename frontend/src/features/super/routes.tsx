import type { RouteObject } from "react-router-dom";
import { SuperDashboard } from "./SuperDashboard";
import { SuperPeoplePage } from "./SuperPeoplePage";
import { SchoolDetailPage } from "./SchoolDetailPage";
import { SuperBillingPage } from "./SuperBillingPage";

export const superRoutes: RouteObject[] = [
  { index: true, element: <SuperDashboard /> },
  { path: "users", element: <SuperPeoplePage /> },
  { path: "schools/:id", element: <SchoolDetailPage /> },
  { path: "billing", element: <SuperBillingPage /> },
];
