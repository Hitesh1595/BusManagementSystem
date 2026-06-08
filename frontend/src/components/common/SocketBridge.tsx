import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getSocket, type NotificationEvent } from "@/lib/socket";
import { useLiveTripStore } from "@/stores/liveTrip";

/**
 * Wires the shared socket's lifecycle into the liveTrip store (connection
 * status) and surfaces incoming `notification` events as toasts + a query
 * invalidation so the bell badge updates. Renders nothing.
 */
export function SocketBridge() {
  const qc = useQueryClient();
  const setConnection = useLiveTripStore((s) => s.setConnection);

  useEffect(() => {
    const socket = getSocket();

    const onConnect = () => setConnection("connected");
    const onDisconnect = () => setConnection("disconnected");
    const onError = () => setConnection("disconnected");
    const onReconnectAttempt = () => setConnection("connecting");
    const onNotification = (e: NotificationEvent) => {
      void qc.invalidateQueries({ queryKey: ["notifications"] });
      toast(e.title, { description: e.body ?? undefined });
    };

    socket.on("connect", onConnect);
    socket.on("disconnect", onDisconnect);
    socket.on("connect_error", onError);
    socket.io.on("reconnect_attempt", onReconnectAttempt);
    socket.on("notification", onNotification);

    if (socket.connected) setConnection("connected");

    return () => {
      socket.off("connect", onConnect);
      socket.off("disconnect", onDisconnect);
      socket.off("connect_error", onError);
      socket.io.off("reconnect_attempt", onReconnectAttempt);
      socket.off("notification", onNotification);
    };
  }, [qc, setConnection]);

  return null;
}
