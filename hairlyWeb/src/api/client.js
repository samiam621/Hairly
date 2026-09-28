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
  // FormData (a photo upload) is sent as-is: the browser sets the multipart Content-Type itself
  const json = body && !(body instanceof FormData)
  let res
  try {
    res = await fetch(path, {
      ...options,
      headers: json ? { 'Content-Type': 'application/json', ...headers } : headers,
      body: json ? JSON.stringify(body) : body,
    })
  } catch {
    // fetch only throws when there's no response at all (backend down, offline)
    throw new ApiError('NETWORK_ERROR', "Can't reach Hairly. Check your connection.", 0)
  }

  // .catch: a 502 from the proxy or a crash page isn't JSON
  const data = await res.json().catch(() => null)
  // data === null on a 200 too: a static host answering /api with its index.html
  if (!res.ok || data === null) {
    throw new ApiError(
      data?.error?.code ?? 'UNKNOWN',
      data?.error?.message ?? `Something went wrong (${res.status}). Try again.`,
      res.status,
    )
  }
  return data
}
