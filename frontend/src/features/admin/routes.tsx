import type { RouteObject } from "react-router-dom";

import { AdminDashboard } from "./AdminDashboard";
import { SetupWizard } from "./SetupWizard";
import { SettingsPage } from "./SettingsPage";
import { VehiclesPage } from "./vehicles/VehiclesPage";
import { DriversPage } from "./drivers/DriversPage";
import { PeoplePage } from "./people/PeoplePage";
// Owned by the ADMIN-OPS sibling agent (exact paths + named exports):
import { FleetMapPage } from "./fleet/FleetMapPage";
import { AlertsPage } from "./alerts/AlertsPage";
import { RequestsPage } from "./requests/RequestsPage";
import { RoutesListPage } from "./routes/RoutesListPage";
import { RouteEditorPage } from "./routes/RouteEditorPage";

export const adminRoutes: RouteObject[] = [
  { index: true, element: <AdminDashboard /> },
  { path: "setup", element: <SetupWizard /> },
  { path: "vehicles", element: <VehiclesPage /> },
  { path: "drivers", element: <DriversPage /> },
  { path: "users", element: <PeoplePage /> },
  { path: "settings", element: <SettingsPage /> },
  { path: "fleet", element: <FleetMapPage /> },
  { path: "alerts", element: <AlertsPage /> },
  { path: "requests", element: <RequestsPage /> },
  { path: "routes", element: <RoutesListPage /> },
  { path: "routes/:routeId", element: <RouteEditorPage /> },
];
