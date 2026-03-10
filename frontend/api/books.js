const BOOKS_SEARCH_ENDPOINT = "/api/books";

export class BooksApiError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = "BooksApiError";
    this.status = options.status ?? null;
    this.cause = options.cause;
  }
}

function mapAgeRatingToBounds(ageRating) {
  if (ageRating === "kids") {
    return { ageMin: 0, ageMax: 12 };
  }
  if (ageRating === "teen") {
    return { ageMin: 13, ageMax: 17 };
  }
  if (ageRating === "adult") {
    return { ageMin: 18, ageMax: 120 };
  }
  return null;
}

export function buildBooksSearchUrl(params, baseOrigin = window.location.origin) {
  const url = new URL(BOOKS_SEARCH_ENDPOINT, baseOrigin);

  if (params.query) {
    url.searchParams.set("q", params.query);
  }

  if (params.fictionType && params.fictionType !== "all") {
    // Backward-compatible no-op for current backend; included for future API support.
    url.searchParams.set("fiction_type", params.fictionType);
  }

  if (params.spiceLevel && params.spiceLevel !== "any") {
    url.searchParams.set("spice_level", params.spiceLevel);
  }

  if (Array.isArray(params.subjects) && params.subjects.length > 0) {
    // Backend currently supports one subject parameter; keep all selected values
    // in a CSV param for forward compatibility and send first subject for today.
    url.searchParams.set("subject", params.subjects[0]);
    url.searchParams.set("subjects", params.subjects.join(","));
  }

  const ageBounds = mapAgeRatingToBounds(params.ageRating);
  if (ageBounds) {
    url.searchParams.set("age_min", String(ageBounds.ageMin));
    url.searchParams.set("age_max", String(ageBounds.ageMax));
  }

  return url;
}

function extractApiErrorMessage(payload) {
  if (payload && typeof payload === "object" && typeof payload.message === "string") {
    return payload.message;
  }
  return null;
}

export async function searchBooksApi(params, fetchImpl = fetch) {
  const url = buildBooksSearchUrl(params);

  let response;
  try {
    response = await fetchImpl(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
    });
  } catch (error) {
    throw new BooksApiError("Could not connect to the book search API.", {
      cause: error,
    });
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const message = extractApiErrorMessage(payload) ?? `Book search failed with HTTP ${response.status}.`;
    throw new BooksApiError(message, {
      status: response.status,
    });
  }

  if (!Array.isArray(payload)) {
    throw new BooksApiError("Unexpected response format from book search API.", {
      status: response.status,
    });
  }

  return payload;
}
