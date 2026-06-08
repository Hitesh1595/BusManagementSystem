import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});

/**
 * Central query-key registry. Keep keys here so invalidation across features
 * stays consistent (e.g. mutating a vehicle invalidates qk.vehicles()).
 */
export const qk = {
  me: ["me"] as const,
  school: (id: string) => ["school", id] as const,

  vehicles: (params?: unknown) => ["vehicles", params ?? {}] as const,
  vehicle: (id: string) => ["vehicle", id] as const,

  drivers: (params?: unknown) => ["drivers", params ?? {}] as const,
  driver: (id: string) => ["driver", id] as const,

  routes: (params?: unknown) => ["routes", params ?? {}] as const,
  route: (id: string) => ["route", id] as const,
  routeStudents: (id: string) => ["route", id, "students"] as const,

  students: (params?: unknown) => ["students", params ?? {}] as const,
  student: (id: string) => ["student", id] as const,

  transportRequests: (params?: unknown) =>
    ["transport-requests", params ?? {}] as const,
  transportRequest: (id: string) => ["transport-request", id] as const,

  trips: (params?: unknown) => ["trips", params ?? {}] as const,
  trip: (id: string) => ["trip", id] as const,
  activeTrips: ["trips", "active"] as const,
  tripAttendance: (id: string) => ["trip", id, "attendance"] as const,
  tripAbsences: (id: string) => ["trip", id, "absences"] as const,
  tripGpsLog: (id: string) => ["trip", id, "gps-log"] as const,

  alerts: (params?: unknown) => ["alerts", params ?? {}] as const,
  notifications: (params?: unknown) => ["notifications", params ?? {}] as const,
};
