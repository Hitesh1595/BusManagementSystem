import type { RouteObject } from "react-router-dom";
import { SuperDashboard } from "./SuperDashboard";

export const superRoutes: RouteObject[] = [
  { index: true, element: <SuperDashboard /> },
];
