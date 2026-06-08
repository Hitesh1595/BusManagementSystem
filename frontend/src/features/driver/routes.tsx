import type { RouteObject } from "react-router-dom";
import TodayPage from "./TodayPage";
import RunTripPage from "./RunTripPage";

export const driverRoutes: RouteObject[] = [
  { index: true, element: <TodayPage /> },
  { path: "trip/:tripId", element: <RunTripPage /> },
];
