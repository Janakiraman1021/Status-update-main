"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api, type PageMeta } from "./api";

type Params = Record<string, string | number | boolean | null | undefined>;

function asApiError(err: unknown): ApiError {
  return err instanceof ApiError ? err : new ApiError("UNKNOWN", "Something went wrong.", 0);
}

interface ApiState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => Promise<void>;
  setData: (update: T | null | ((current: T | null) => T | null)) => void;
}

/**
 * Fetch a GET endpoint; pass null to skip. Results are keyed by path, so stale responses
 * from a previous path are never shown and `loading` is derived rather than toggled.
 */
export function useApi<T>(path: string | null): ApiState<T> {
  const [result, setResult] = useState<{ key: string | null; data: T | null; error: ApiError | null }>({ key: null, data: null, error: null });
  const [refreshing, setRefreshing] = useState(false);
  const latest = useRef(0);

  const fetchInto = useCallback(async (target: string) => {
    const id = ++latest.current;
    try {
      const data = await api.get<T>(target);
      if (id === latest.current) setResult({ key: target, data, error: null });
    } catch (err) {
      if (id === latest.current) setResult((r) => ({ key: target, data: r.key === target ? r.data : null, error: asApiError(err) }));
    }
  }, []);

  useEffect(() => {
    if (path) void fetchInto(path);
  }, [path, fetchInto]);

  const reload = useCallback(async () => {
    if (!path) return;
    setRefreshing(true);
    try {
      await fetchInto(path);
    } finally {
      setRefreshing(false);
    }
  }, [path, fetchInto]);

  const setData = useCallback<ApiState<T>["setData"]>((update) => {
    setResult((r) => ({ ...r, error: null, data: typeof update === "function" ? (update as (c: T | null) => T | null)(r.data) : update }));
  }, []);

  const current = result.key === path;
  return {
    data: current ? result.data : null,
    error: current ? result.error : null,
    loading: Boolean(path) && (!current || refreshing),
    reload,
    setData,
  };
}

/** Paginated GET with the same keyed-result approach. */
export function usePagedApi<T>(path: string, params: Params) {
  const key = `${path}?${JSON.stringify(params)}`;
  const [result, setResult] = useState<{ key: string | null; rows: T[]; meta: PageMeta | null; error: string | null }>({ key: null, rows: [], meta: null, error: null });
  const [nonce, setNonce] = useState(0);
  const paramsRef = useRef(params);

  useEffect(() => {
    paramsRef.current = params;
  });

  useEffect(() => {
    let cancelled = false;
    api.page<T[]>(path, paramsRef.current)
      .then((res) => !cancelled && setResult({ key, rows: res.data, meta: res.meta ?? null, error: null }))
      .catch((err) => !cancelled && setResult((r) => ({ ...r, key, error: asApiError(err).message })));
    return () => {
      cancelled = true;
    };
  }, [path, key, nonce]);

  const current = result.key === key;
  return {
    rows: result.rows,
    meta: result.meta,
    loading: !current,
    error: current ? result.error : null,
    retry: () => setNonce((n) => n + 1),
  };
}

export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const handle = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(handle);
  }, [value, delay]);
  return debounced;
}

/** Warn before leaving the page while there are unsaved changes. */
export function useUnsavedChangesWarning(active: boolean) {
  useEffect(() => {
    if (!active) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [active]);
}

/** Page number that resets to 1 whenever `resetKey` changes, without an effect. */
export function usePageState(resetKey: string): [number, (page: number) => void] {
  const [state, setState] = useState({ key: resetKey, page: 1 });
  const page = state.key === resetKey ? state.page : 1;
  return [page, (next: number) => setState({ key: resetKey, page: next })];
}
