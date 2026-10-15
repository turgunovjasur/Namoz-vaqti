import { useEffect, useState } from "react";
let csrf = "";
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}
export function setCsrf(value: string) {
  csrf = value;
}
export async function api<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET")
    headers.set("X-CSRF-Token", csrf);
  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      credentials: "same-origin",
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(
      "Server bilan bog‘lanib bo‘lmadi. Ulanishni tekshiring.",
      0,
    );
  }
  const body = await response
    .json()
    .catch(() => ({ detail: "Server javobini o‘qib bo‘lmadi." }));
  if (!response.ok) {
    if (response.status === 401 && csrf)
      window.dispatchEvent(new Event("admin-session-expired"));
    throw new ApiError(
      typeof body.detail === "string"
        ? body.detail
        : "Yuborilgan qiymatlarni tekshiring.",
      response.status,
    );
  }
  return body as T;
}
export function useRemote<T>(url: string) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState<Error | null>(null),
    [loading, setLoading] = useState(true),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let live = true;
    setLoading(true);
    setError(null);
    setData(null);
    api<T>(url, { signal: controller.signal })
      .then((value) => {
        if (live) setData(value);
      })
      .catch((e) => {
        if (live) setError(e);
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
      controller.abort();
    };
  }, [url, revision]);
  return { data, error, loading, reload: () => setRevision((v) => v + 1) };
}
export function useDebounced(value: string) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), 250);
    return () => clearTimeout(id);
  }, [value]);
  return debounced;
}
