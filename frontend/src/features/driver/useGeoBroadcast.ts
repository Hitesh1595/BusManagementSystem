import { useEffect, useRef, useState } from "react";
import { connectSocket, emitLocation } from "@/lib/socket";

/** Minimum gap between emitted location_update events (server caps ≤1/3s). */
const THROTTLE_MS = 3000;

export interface GeoBroadcastState {
  /** Geolocation is being watched and (at least once) reported. */
  tracking: boolean;
  /** A screen Wake Lock is currently held. */
  wakeLock: boolean;
  /** Last geolocation error code, if any (e.g. permission denied). */
  geoError: string | null;
  /** Last accuracy in metres of the most recent fix. */
  accuracy: number | null;
}

/**
 * While `enabled` (trip in_progress) is true:
 *  - watches the device geolocation and emits throttled `location_update`
 *    Socket.IO events for `tripId` (~1 per 3s),
 *  - requests a screen Wake Lock so the phone screen stays on, re-acquiring it
 *    when the tab becomes visible again.
 * Cleans everything up on unmount / when disabled.
 */
export function useGeoBroadcast(
  tripId: string | null | undefined,
  enabled: boolean,
): GeoBroadcastState {
  const [tracking, setTracking] = useState(false);
  const [wakeLock, setWakeLock] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [accuracy, setAccuracy] = useState<number | null>(null);

  const lastSentRef = useRef(0);

  // --- GPS watch + emit -----------------------------------------------------
  useEffect(() => {
    if (!tripId || !enabled) {
      setTracking(false);
      return;
    }
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setGeoError("unsupported");
      return;
    }

    connectSocket();
    setGeoError(null);

    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        setTracking(true);
        setAccuracy(pos.coords.accuracy ?? null);
        const now = Date.now();
        if (now - lastSentRef.current < THROTTLE_MS) return;
        lastSentRef.current = now;
        emitLocation({
          trip_id: tripId,
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          speed: Number.isFinite(pos.coords.speed) ? pos.coords.speed : null,
          heading: Number.isFinite(pos.coords.heading)
            ? pos.coords.heading
            : null,
          accuracy: Number.isFinite(pos.coords.accuracy)
            ? pos.coords.accuracy
            : null,
          ts: Math.floor(now / 1000),
        });
      },
      (err) => {
        setGeoError(err.message || "geolocation_error");
      },
      { enableHighAccuracy: true, maximumAge: 2000, timeout: 15000 },
    );

    return () => {
      navigator.geolocation.clearWatch(watchId);
      setTracking(false);
    };
  }, [tripId, enabled]);

  // --- Screen Wake Lock -----------------------------------------------------
  useEffect(() => {
    if (!enabled) {
      setWakeLock(false);
      return;
    }
    const nav = navigator as Navigator & {
      wakeLock?: { request: (type: "screen") => Promise<WakeLockSentinelLike> };
    };
    if (!nav.wakeLock) {
      setWakeLock(false);
      return;
    }

    let sentinel: WakeLockSentinelLike | null = null;
    let cancelled = false;

    const acquire = async () => {
      try {
        sentinel = await nav.wakeLock!.request("screen");
        if (cancelled) {
          await sentinel.release();
          sentinel = null;
          return;
        }
        setWakeLock(true);
        sentinel.addEventListener?.("release", () => setWakeLock(false));
      } catch {
        setWakeLock(false);
      }
    };

    const onVisibility = () => {
      if (document.visibilityState === "visible" && !cancelled) void acquire();
    };

    void acquire();
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisibility);
      void sentinel?.release().catch(() => undefined);
      sentinel = null;
      setWakeLock(false);
    };
  }, [enabled]);

  return { tracking, wakeLock, geoError, accuracy };
}

/** Minimal structural type for the Wake Lock sentinel (lib.dom may lack it). */
interface WakeLockSentinelLike {
  release: () => Promise<void>;
  addEventListener?: (type: "release", listener: () => void) => void;
}
