import type { RouteObject } from "react-router-dom";
import { SuperDashboard } from "./SuperDashboard";
import { SuperPeoplePage } from "./SuperPeoplePage";

export const superRoutes: RouteObject[] = [
  { index: true, element: <SuperDashboard /> },
  { path: "users", element: <SuperPeoplePage /> },
];
