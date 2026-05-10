import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchLMStudioHealth, type LMStudioHealthResponse } from "../lib/llmApi";

export type LMStudioConnectionState = "checking" | "connected" | "offline";

export type LMStudioHealthState = {
  state: LMStudioConnectionState;
  data: LMStudioHealthResponse | null;
  error: string | null;
  lastCheckedAt: Date | null;
  checkNow: () => Promise<void>;
};

export function useLMStudioHealth(pollMs = 7000): LMStudioHealthState {
  const [state, setState] = useState<LMStudioConnectionState>("checking");
  const [data, setData] = useState<LMStudioHealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastCheckedAt, setLastCheckedAt] = useState<Date | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  const checkNow = useCallback(async () => {
    abortRef.current?.abort();

    const controller = new AbortController();
    abortRef.current = controller;

    setState((current) => (current === "connected" ? current : "checking"));

    try {
      const health = await fetchLMStudioHealth(controller.signal);

      setData(health);
      setError(health.error ?? null);
      setState(health.status === "connected" ? "connected" : "offline");
      setLastCheckedAt(new Date());
    } catch (unknownError) {
      if (controller.signal.aborted) {
        return;
      }

      const message =
        unknownError instanceof Error
          ? unknownError.message
          : "Unable to reach LM Studio through Serviq backend.";

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
      lastCheckedAt,
      checkNow,
    }),
    [state, data, error, lastCheckedAt, checkNow],
  );
}
