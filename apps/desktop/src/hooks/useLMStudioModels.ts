import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchLMStudioModels } from "../lib/llmApi";

export type LMStudioModel = {
  id: string;
  raw: Record<string, unknown>;
};

export type LMStudioModelsState = {
  models: LMStudioModel[];
  selectedModel: string;
  isLoading: boolean;
  error: string | null;
  refreshModels: () => Promise<void>;
  setSelectedModel: (modelId: string) => void;
};

function normalizeModel(model: Record<string, unknown>): LMStudioModel | null {
  const id = model.id;

  if (typeof id !== "string" || id.length === 0) {
    return null;
  }

  return {
    id,
    raw: model,
  };
}

export function useLMStudioModels(): LMStudioModelsState {
  const [models, setModels] = useState<LMStudioModel[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refreshModels = useCallback(async () => {
    abortRef.current?.abort();

    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError(null);

    try {
      const result = await fetchLMStudioModels(controller.signal);
      const normalized = result.models
        .map(normalizeModel)
        .filter((model): model is LMStudioModel => Boolean(model));

      setModels(normalized);
      setSelectedModel((current) => {
        if (current && normalized.some((model) => model.id === current)) {
          return current;
        }

        return normalized[0]?.id ?? "";
      });
    } catch (unknownError) {
      if (controller.signal.aborted) {
        return;
      }

      const message =
        unknownError instanceof Error
          ? unknownError.message
          : "Unable to load LM Studio models.";

      setModels([]);
      setSelectedModel("");
      setError(message);
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void refreshModels();

    return () => {
      abortRef.current?.abort();
    };
  }, [refreshModels]);

  return useMemo(
    () => ({
      models,
      selectedModel,
      isLoading,
      error,
      refreshModels,
      setSelectedModel,
    }),
    [models, selectedModel, isLoading, error, refreshModels],
  );
}
