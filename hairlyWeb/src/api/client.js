// The one place that calls fetch(): serializes JSON, parses responses,
// and turns HTTP failures into an ApiError carrying the backend's error code.

export class ApiError extends Error {
  constructor(code, message, status) {
    super(message)
    this.code = code
    this.status = status
  }
}

export async function request(path, { body, headers, ...options } = {}) {
  let res
  try {
    res = await fetch(path, {
      ...options,
      headers: body ? { 'Content-Type': 'application/json', ...headers } : headers,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    // fetch only throws when there's no response at all (backend down, offline)
    throw new ApiError('NETWORK_ERROR', "Can't reach Hairly. Check your connection.", 0)
  }

  // .catch: a 502 from the proxy or a crash page isn't JSON
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    throw new ApiError(
      data?.error?.code ?? 'UNKNOWN',
      data?.error?.message ?? `Request failed (${res.status})`,
      res.status,
    )
  }
  return data
}
