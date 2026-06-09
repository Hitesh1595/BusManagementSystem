import type { RouteObject } from "react-router-dom";
import { DashboardPage } from "./DashboardPage";
import { RequestsPage } from "./RequestsPage";
import { RequestTransportPage } from "./RequestTransportPage";
import { NotificationsPage } from "./NotificationsPage";
import { LiveTrackPage } from "./LiveTrackPage";
import { SettingsPage } from "./SettingsPage";

export const parentRoutes: RouteObject[] = [
  { index: true, element: <DashboardPage /> },
  { path: "requests", element: <RequestsPage /> },
  { path: "request/new", element: <RequestTransportPage /> },
  { path: "notifications", element: <NotificationsPage /> },
  { path: "track/:tripId", element: <LiveTrackPage /> },
  { path: "settings", element: <SettingsPage /> },
];
