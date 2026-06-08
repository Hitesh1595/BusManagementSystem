import { create } from "zustand";
import type {
  BusApproachingEvent,
  LocationUpdateEvent,
  TrackingPausedEvent,
} from "@/lib/socket";

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

interface LiveTripState {
  /** Global socket connection status (single shared socket). */
  connection: ConnectionStatus;
  /** Latest GPS fix per trip id. */
  positions: Record<string, LocationUpdateEvent>;
  /** Active "bus approaching" event per trip id. */
  approaching: Record<string, BusApproachingEvent | undefined>;
  /** Active "tracking paused" (stale GPS) state per trip id. */
  paused: Record<string, TrackingPausedEvent | undefined>;

  setConnection: (status: ConnectionStatus) => void;
  applyLocation: (event: LocationUpdateEvent) => void;
  applyApproaching: (event: BusApproachingEvent) => void;
  applyPaused: (event: TrackingPausedEvent) => void;
  resetTrip: (tripId: string) => void;
}

export const useLiveTripStore = create<LiveTripState>((set) => ({
  connection: "connecting",
  positions: {},
  approaching: {},
  paused: {},

  setConnection: (status) => set({ connection: status }),

  applyLocation: (event) =>
    set((s) => ({
      positions: { ...s.positions, [event.trip_id]: event },
      // A fresh fix clears any stale-tracking banner.
      paused: { ...s.paused, [event.trip_id]: undefined },
    })),

  applyApproaching: (event) =>
    set((s) => ({
      approaching: { ...s.approaching, [event.trip_id]: event },
    })),

  applyPaused: (event) =>
    set((s) => ({
      paused: { ...s.paused, [event.trip_id]: event },
    })),

  resetTrip: (tripId) =>
    set((s) => {
      const positions = { ...s.positions };
      const approaching = { ...s.approaching };
      const paused = { ...s.paused };
      delete positions[tripId];
      delete approaching[tripId];
      delete paused[tripId];
      return { positions, approaching, paused };
    }),
}));
