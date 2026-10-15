export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function unauthorized(message = "Missing or invalid bearer token"): ApiError {
  return new ApiError(401, "unauthorized", message);
}

export function notFound(message = "Not found"): ApiError {
  return new ApiError(404, "not_found", message);
}

export function badRequest(message: string): ApiError {
  return new ApiError(400, "bad_request", message);
}

export function conflict(message: string): ApiError {
  return new ApiError(409, "conflict", message);
}
