import { useEffect, useRef } from "react";
import { useLiveTripStore } from "@/stores/liveTrip";
import {
  connectSocket,
  getSocket,
  joinTrip,
  leaveTrip,
  type AttendanceUpdateEvent,
  type BusApproachingEvent,
  type ChildAbsentMarkedEvent,
  type ChildNotBoardedEvent,
  type ChildNotDroppedEvent,
  type LocationUpdateEvent,
  type TrackingPausedEvent,
  type TripEndedEvent,
} from "@/lib/socket";

export interface TripRoomHandlers {
  onLocation?: (e: LocationUpdateEvent) => void;
  onApproaching?: (e: BusApproachingEvent) => void;
  onPaused?: (e: TrackingPausedEvent) => void;
  onAttendance?: (e: AttendanceUpdateEvent) => void;
  onChildNotBoarded?: (e: ChildNotBoardedEvent) => void;
  onChildNotDropped?: (e: ChildNotDroppedEvent) => void;
  onChildAbsentMarked?: (e: ChildAbsentMarkedEvent) => void;
  onTripEnded?: (e: TripEndedEvent) => void;
}

/**
 * Join a trip's Socket.IO room and route live events into the liveTrip store
 * (and optional per-event callbacks). Automatically leaves on unmount or when
 * tripId/enabled changes. Filters events to the active tripId.
 */
export function useTripRoom(
  tripId: string | null | undefined,
  handlers: TripRoomHandlers = {},
  enabled = true,
) {
  const apply = useLiveTripStore();
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!tripId || !enabled) return;
    const socket = connectSocket();
    let active = true;

    const sameTrip = (e: { trip_id: string }) => e.trip_id === tripId;

    const onLocation = (e: LocationUpdateEvent) => {
      if (!sameTrip(e)) return;
      useLiveTripStore.getState().applyLocation(e);
      handlersRef.current.onLocation?.(e);
    };
    const onApproaching = (e: BusApproachingEvent) => {
      if (!sameTrip(e)) return;
      useLiveTripStore.getState().applyApproaching(e);
      handlersRef.current.onApproaching?.(e);
    };
    const onPaused = (e: TrackingPausedEvent) => {
      if (!sameTrip(e)) return;
      useLiveTripStore.getState().applyPaused(e);
      handlersRef.current.onPaused?.(e);
    };
    const onAttendance = (e: AttendanceUpdateEvent) => {
      if (!sameTrip(e)) return;
      handlersRef.current.onAttendance?.(e);
    };
    const onChildNotBoarded = (e: ChildNotBoardedEvent) => {
      if (!sameTrip(e)) return;
      handlersRef.current.onChildNotBoarded?.(e);
    };
    const onChildNotDropped = (e: ChildNotDroppedEvent) => {
      if (!sameTrip(e)) return;
      handlersRef.current.onChildNotDropped?.(e);
    };
    const onChildAbsentMarked = (e: ChildAbsentMarkedEvent) => {
      if (!sameTrip(e)) return;
      handlersRef.current.onChildAbsentMarked?.(e);
    };
    const onTripEnded = (e: TripEndedEvent) => {
      if (!sameTrip(e)) return;
      handlersRef.current.onTripEnded?.(e);
    };

    socket.on("location_update", onLocation);
    socket.on("bus_approaching", onApproaching);
    socket.on("tracking_paused", onPaused);
    socket.on("attendance_update", onAttendance);
    socket.on("child_not_boarded", onChildNotBoarded);
    socket.on("child_not_dropped", onChildNotDropped);
    socket.on("child_absent_marked", onChildAbsentMarked);
    socket.on("trip_ended", onTripEnded);

    void joinTrip(tripId);

    return () => {
      active = false;
      void active;
      socket.off("location_update", onLocation);
      socket.off("bus_approaching", onApproaching);
      socket.off("tracking_paused", onPaused);
      socket.off("attendance_update", onAttendance);
      socket.off("child_not_boarded", onChildNotBoarded);
      socket.off("child_not_dropped", onChildNotDropped);
      socket.off("child_absent_marked", onChildAbsentMarked);
      socket.off("trip_ended", onTripEnded);
      void leaveTrip(tripId);
    };
  }, [tripId, enabled]);

  return {
    connection: apply.connection,
    position: tripId ? apply.positions[tripId] : undefined,
    approaching: tripId ? apply.approaching[tripId] : undefined,
    paused: tripId ? apply.paused[tripId] : undefined,
    socket: getSocket(),
  };
}
