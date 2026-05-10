import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchBackendHealth, type BackendHealthResponse } from "../lib/api";
import { SERVIQ_API_BASE_URL } from "../lib/config";

export type BackendConnectionState = "checking" | "connected" | "offline";

export type BackendHealthState = {
  state: BackendConnectionState;
  data: BackendHealthResponse | null;
  error: string | null;
  apiBaseUrl: string;
  lastCheckedAt: Date | null;
  checkNow: () => Promise<void>;
};

export function useBackendHealth(pollMs = 5000): BackendHealthState {
  const [state, setState] = useState<BackendConnectionState>("checking");
  const [data, setData] = useState<BackendHealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  const checkNow = useCallback(async () => {
    abortRef.current?.abort();

    const controller = new AbortController();
    abortRef.current = controller;

    setState((current) => (current === "connected" ? current : "checking"));

    try {
      const health = await fetchBackendHealth(controller.signal);

      setData(health);
      setError(null);
      setState("connected");
      setLastCheckedAt(new Date());
    } catch (unknownError) {
      if (controller.signal.aborted) {
        return;
      }

      const message =
        unknownError instanceof Error
          ? unknownError.message
          : "Unable to connect to the Serviq backend.";

      setData(null);
      setError(message);
      setState("offline");
      setLastCheckedAt(new Date());
    }
  }, []);

  useEffect(() => {
    void checkNow();

    const intervalId = window.setInterval(() => {
      void checkNow();
    }, pollMs);

    return () => {
      window.clearInterval(intervalId);
      abortRef.current?.abort();
    };
  }, [checkNow, pollMs]);

  return useMemo(
    () => ({
      state,
      data,
      error,
      apiBaseUrl: SERVIQ_API_BASE_URL,
      lastCheckedAt,
      checkNow,
    }),
    [state, data, error, lastCheckedAt, checkNow],
  );
}
