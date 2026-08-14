"use client";

import { useEffect, useRef, useState, useCallback } from "react";

interface AgentUpdateEvent {
  type: "connected" | "agent_update";
  agent?: string;
  status?: "running" | "completed" | "failed" | "skipped";
  message?: string;
  data?: Record<string, unknown>;
  timestamp?: string;
  session_id?: string;
}

interface UseAnalysisStreamOptions {
  sessionId: string;
  enabled: boolean;
  onEvent?: (event: AgentUpdateEvent) => void;
}

export function useAnalysisStream({ sessionId, enabled, onEvent }: UseAnalysisStreamOptions) {
  const ws = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<AgentUpdateEvent[]>([]);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const connect = useCallback(() => {
    const rawWsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
    const baseUrl = rawWsUrl.replace(/\/ws\/?$/, "").replace(/\/$/, "");
    const wsUrl = `${baseUrl}/ws/analysis/${sessionId}`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => setConnected(true);

    socket.onmessage = (e) => {
      try {
        const event: AgentUpdateEvent = JSON.parse(e.data);
        setEvents((prev) => [...prev, event]);
        onEventRef.current?.(event);
      } catch {
        // ignore malformed messages
      }
    };

    socket.onclose = () => {
      setConnected(false);
      // Reconnect after 3s if still enabled
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    socket.onerror = () => socket.close();

    ws.current = socket;
  }, [sessionId, enabled]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      ws.current?.close();
    };
  }, [connect]);

  const sendPing = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send("ping");
    }
  }, []);

  return { connected, events, sendPing };
}
