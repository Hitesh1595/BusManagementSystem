/**
 * Typed Socket.IO client singleton. Connects same-origin (Vite proxies
 * /socket.io → backend). The token is supplied via an auth callback so each
 * (re)connection picks up the freshest access token.
 */
import { io, type Socket } from "socket.io-client";
import { getAccessToken } from "./api/client";

// --- Event payloads (server → client) -------------------------------------

export interface LocationUpdateEvent {
  trip_id: string;
  lat: number;
  lng: number;
  speed: number | null;
  heading: number | null;
  accuracy: number | null;
  ts: number | null;
  eta_next_stop_s: number | null;
}

export interface BusApproachingEvent {
  trip_id: string;
  stop_id: string;
  distance_m: number;
  eta_s: number;
}

export interface TrackingPausedEvent {
  trip_id: string;
  last_updated_at: string;
  stale_for_sec: number;
}

export interface AttendanceUpdateEvent {
  trip_id: string;
  student_id: string;
  student_name: string;
  status: string;
  stop_name: string;
}

export interface ChildNotBoardedEvent {
  trip_id: string;
  student_id: string;
  student_name: string;
  stop_name: string;
}

export interface ChildNotDroppedEvent {
  trip_id: string;
  student_id: string;
  student_name: string;
}

export interface ChildAbsentMarkedEvent {
  trip_id: string;
  student_id: string;
  student_name: string;
}

export interface TripEndedEvent {
  trip_id: string;
}

export interface NotificationEvent {
  id: string;
  type: string;
  title: string;
  body: string | null;
  data: Record<string, unknown>;
  created_at: string;
}

export interface ServerToClientEvents {
  location_update: (e: LocationUpdateEvent) => void;
  bus_approaching: (e: BusApproachingEvent) => void;
  tracking_paused: (e: TrackingPausedEvent) => void;
  attendance_update: (e: AttendanceUpdateEvent) => void;
  child_not_boarded: (e: ChildNotBoardedEvent) => void;
  child_not_dropped: (e: ChildNotDroppedEvent) => void;
  child_absent_marked: (e: ChildAbsentMarkedEvent) => void;
  trip_ended: (e: TripEndedEvent) => void;
  notification: (e: NotificationEvent) => void;
}

// --- Events (client → server) ---------------------------------------------

export interface DriverLocationPayload {
  trip_id: string;
  lat: number;
  lng: number;
  speed?: number | null;
  heading?: number | null;
  accuracy?: number | null;
  ts: number;
}

interface Ack {
  ok: boolean;
  error?: string;
}

export interface ClientToServerEvents {
  join_trip: (data: { trip_id: string }, ack: (res: Ack) => void) => void;
  leave_trip: (data: { trip_id: string }, ack: (res: Ack) => void) => void;
  location_update: (data: DriverLocationPayload) => void;
}

export type AppSocket = Socket<ServerToClientEvents, ClientToServerEvents>;

let socket: AppSocket | null = null;

/** Lazily create (and connect) the shared socket. */
export function getSocket(): AppSocket {
  if (!socket) {
    socket = io({
      path: "/socket.io",
      autoConnect: false,
      transports: ["websocket", "polling"],
      auth: (cb) => cb({ token: getAccessToken() ?? "" }),
    });
  }
  return socket;
}

export function connectSocket(): AppSocket {
  const s = getSocket();
  if (!s.connected) s.connect();
  return s;
}

export function disconnectSocket(): void {
  if (socket?.connected) socket.disconnect();
}

/** Join a trip room; resolves with the ack from the server. */
export function joinTrip(tripId: string): Promise<Ack> {
  return getSocket()
    .timeout(5000)
    .emitWithAck("join_trip", { trip_id: tripId })
    .catch((): Ack => ({ ok: false, error: "timeout" }));
}

export function leaveTrip(tripId: string): Promise<Ack> {
  return getSocket()
    .timeout(5000)
    .emitWithAck("leave_trip", { trip_id: tripId })
    .catch((): Ack => ({ ok: false, error: "timeout" }));
}

export function emitLocation(payload: DriverLocationPayload): void {
  const s = getSocket();
  if (s.connected) s.emit("location_update", payload);
}
