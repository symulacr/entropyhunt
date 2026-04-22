import { useState, useEffect, useRef, useCallback } from "react";
import type { SnapshotPayload } from "@/types/live";
import type { ConnectionState } from "@/lib/liveUtils";

const MAX_RECONNECT_DELAY = 30000;

export interface UseSSEReturn {
  payload: SnapshotPayload | null;
  connectionState: ConnectionState;
  connectionText: string;
  lastUpdate: string | null;
  reconnectAttempts: number;
}

export function useSSE(url: string): UseSSEReturn {
  const [payload, setPayload] = useState<SnapshotPayload | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>("connecting");
  const [connectionText, setConnectionText] = useState<string>("Connecting");
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState<number>(0);

  const evtSourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptsRef = useRef<number>(0);

  const setStatus = useCallback((state: ConnectionState, text: string) => {
    setConnectionState(state);
    setConnectionText(text);
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (reconnectTimerRef.current) return;
    attemptsRef.current += 1;
    setReconnectAttempts(attemptsRef.current);
    const delay = Math.min(1000 * Math.pow(2, attemptsRef.current - 1), MAX_RECONNECT_DELAY);
    setStatus("reconnecting", `Reconnecting in ${Math.round(delay / 1000)}s`);
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      connect();
    }, delay);
  }, [setStatus]);

  const connect = useCallback(() => {
    if (evtSourceRef.current) {
      evtSourceRef.current.close();
      evtSourceRef.current = null;
    }

    setStatus(
      "reconnecting",
      attemptsRef.current > 0 ? `Reconnecting (attempt ${attemptsRef.current})` : "Connecting"
    );

    const evtSource = new EventSource(url);
    evtSourceRef.current = evtSource;

    evtSource.addEventListener("snapshot", (event: MessageEvent<string>) => {
      attemptsRef.current = 0;
      setReconnectAttempts(0);
      setStatus("live", "Live");
      try {
        const data = JSON.parse(event.data) as SnapshotPayload;
        setPayload(data);
        setLastUpdate(new Date().toISOString());
      } catch {
        setStatus("error", "Malformed data");
      }
    });

    evtSource.addEventListener("error", () => {
      if (evtSource.readyState === EventSource.CLOSED) {
        setStatus("error", "Connection lost");
        scheduleReconnect();
      } else {
        setStatus("reconnecting", "Retrying");
      }
    });

    evtSource.addEventListener("open", () => {
      attemptsRef.current = 0;
      setReconnectAttempts(0);
      setStatus("live", "Live");
    });
  }, [url, setStatus, scheduleReconnect]);

  useEffect(() => {
    connect();
    return () => {
      if (evtSourceRef.current) {
        evtSourceRef.current.close();
        evtSourceRef.current = null;
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [connect]);

  return { payload, connectionState, connectionText, lastUpdate, reconnectAttempts };
}
