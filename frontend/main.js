import { BooksApiError, searchBooksApi } from "./api/books.js";

const mockBooks = [
  {
    title: "The Great Adventure",
    author: "Alex Carter",
    snippet: "An epic coming-of-age journey across wild floating islands.",
    genre: "Fantasy",
    fictionType: "fiction",
    ageRating: "teen",
    subjects: ["fantasy"],
    spiceLevel: "low",
  },
  {
    title: "Night Library",
    author: "Jordan Kim",
    snippet: "A shy archivist uncovers coded notes hidden inside returned books.",
    genre: "Mystery",
    fictionType: "fiction",
    ageRating: "teen",
    subjects: ["historical"],
    spiceLevel: "medium",
  },
  {
    title: "Signal in the Snow",
    author: "Priya Das",
    snippet: "Two siblings trace a radio beacon through a frozen research outpost.",
    genre: "Thriller",
    fictionType: "fiction",
    ageRating: "adult",
    subjects: ["sci-fi"],
    spiceLevel: "high",
  },
  {
    title: "Summer on Alder Street",
    author: "Maya Flores",
    snippet: "A neighborhood project pulls rival friends into an unlikely partnership.",
    genre: "Contemporary",
    fictionType: "fiction",
    ageRating: "kids",
    subjects: ["historical"],
    spiceLevel: "low",
  },
  {
    title: "The River Clock",
    author: "Nathan Pierce",
    snippet: "A small town mechanic rebuilds an antique clock tied to local history.",
    genre: "Historical",
    fictionType: "fiction",
    ageRating: "adult",
    subjects: ["historical"],
    spiceLevel: "medium",
  },
  {
    title: "Orbit of Small Things",
    author: "Leah Morgan",
    snippet: "A science club launches homemade satellites and learns teamwork.",
    genre: "Science Fiction",
    fictionType: "fiction",
    ageRating: "kids",
    subjects: ["sci-fi"],
    spiceLevel: "low",
  },
  {
    title: "Letters to a Forgotten Map",
    author: "Evan Holt",
    snippet: "A puzzle trail sends a teen geographer across hidden city landmarks.",
    genre: "Adventure",
    fictionType: "fiction",
    ageRating: "teen",
    subjects: ["historical"],
    spiceLevel: "medium",
  },
  {
    title: "Tea Shop at Dawn",
    author: "Harper Lee",
    snippet: "An apprentice baker keeps a family shop alive while solving daily mysteries.",
    genre: "Slice of Life",
    fictionType: "fiction",
    ageRating: "kids",
    subjects: ["fantasy"],
    spiceLevel: "low",
  },
  {
    title: "Wildflower Code",
    author: "Rina Shah",
    snippet: "A student botanist discovers encrypted field journals in a greenhouse.",
    genre: "Mystery",
    fictionType: "fiction",
    ageRating: "teen",
    subjects: ["sci-fi"],
    spiceLevel: "medium",
  },
  {
    title: "Echoes Under Glass",
    author: "Marcus Vale",
    snippet: "A museum volunteer tracks missing artifacts and buried family secrets.",
    genre: "Drama",
    fictionType: "fiction",
    ageRating: "adult",
    subjects: ["historical"],
    spiceLevel: "high",
  },
  {
    title: "History of Lighthouse Engineering",
    author: "Elena Brooks",
    snippet: "A visual guide to coastal engineering breakthroughs and failures.",
    genre: "Reference",
    fictionType: "nonfiction",
    ageRating: "teen",
    subjects: ["historical"],
    spiceLevel: "low",
  },
  {
    title: "Beyond the Red Planet",
    author: "Ian Wallace",
    snippet: "An accessible look at current deep-space missions and future habitats.",
    genre: "Science",
    fictionType: "nonfiction",
    ageRating: "adult",
    subjects: ["sci-fi"],
    spiceLevel: "low",
  },
];

function createDefaultSearchParams() {
  return {
    query: "",
    fictionType: "all",
    ageRating: "all",
    subjects: [],
    spiceLevel: "any",
  };
}

function mapApiAgeRating(value) {
  if (value === "general" || value === "kids") {
    return "kids";
  }
  if (value === "mature" || value === "adult") {
    return "adult";
  }
  return "teen";
}

function mapApiSpiceLevel(book) {
  const rawSpice = book.spiceLevel ?? book.spice_level;
  if (rawSpice === "low" || rawSpice === "medium" || rawSpice === "high") {
    return rawSpice;
  }

  const ageRating = book.ageRating ?? book.age_rating;
  if (ageRating === "general" || ageRating === "kids") {
    return "low";
  }
  if (ageRating === "mature" || ageRating === "adult") {
    return "high";
  }
  return "medium";
}

function inferFictionType(book) {
  const explicitType = book.fictionType ?? book.fiction_type;
  if (explicitType === "fiction" || explicitType === "nonfiction") {
    return explicitType;
  }

  const genreText = String(book.genre ?? "").toLowerCase();
  if (genreText.includes("nonfiction") || genreText.includes("reference")) {
    return "nonfiction";
  }

  return "fiction";
}

function normalizeSubjectList(book) {
  if (Array.isArray(book.subjects)) {
    return book.subjects.map((subject) => String(subject).toLowerCase());
  }

  if (typeof book.subject === "string" && book.subject.trim() !== "") {
    return [book.subject.toLowerCase()];
  }

  return [];
}

function normalizeBook(book) {
  return {
    title: book.title ?? "Untitled",
    author: book.author ?? "Unknown",
    snippet: book.snippet ?? book.description ?? "No description available.",
    genre: book.genre ?? "Unknown",
    fictionType: inferFictionType(book),
    ageRating: mapApiAgeRating(book.ageRating ?? book.age_rating),
    subjects: normalizeSubjectList(book),
    spiceLevel: mapApiSpiceLevel(book),
  };
}

function formatFictionType(value) {
  return value === "nonfiction" ? "Non-fiction" : "Fiction";
}

function formatAgeRating(value) {
  if (value === "kids") {
    return "Kids (8-12)";
  }
  if (value === "adult") {
    return "Adult (18+)";
  }
  return "Teen (13-17)";
}

function formatSpiceLevel(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function matchesQuery(item, query) {
  if (!query) {
    return true;
  }

  const searchableText = `${item.title} ${item.author} ${item.genre} ${item.snippet}`.toLowerCase();
  return searchableText.includes(query);
}

function matchesSubjects(item, subjects) {
  if (!subjects.length) {
    return true;
  }

  return subjects.every((subject) => item.subjects.includes(subject));
}

function filterBooksCollection(items, params) {
  const normalizedQuery = params.query.trim().toLowerCase();
  return items
    .map(normalizeBook)
    .filter((item) => {
      if (!matchesQuery(item, normalizedQuery)) {
        return false;
      }
      if (params.fictionType !== "all" && item.fictionType !== params.fictionType) {
        return false;
      }
      if (params.ageRating !== "all" && item.ageRating !== params.ageRating) {
        return false;
      }
      if (params.spiceLevel !== "any" && item.spiceLevel !== params.spiceLevel) {
        return false;
      }
      return matchesSubjects(item, params.subjects);
    });
}

function cloneSearchParams(searchParams) {
  return {
    ...searchParams,
    subjects: [...searchParams.subjects],
  };
}

export function createSearchApp({
  searchForm = null,
  searchInput = null,
  searchButton = null,
  filtersForm = null,
  fictionTypeInput = null,
  ageRatingInput = null,
  resultsStatus = null,
  resultsError = null,
  resultsList = null,
  createElement = null,
  searchBooksApiImpl = searchBooksApi,
  fallbackBooks = mockBooks,
} = {}) {
  const searchParams = createDefaultSearchParams();
  let isLoading = false;

  function renderResults(results) {
    if (!resultsList || !resultsStatus || typeof createElement !== "function") {
      return;
    }

    resultsList.replaceChildren();

    if (!results.length) {
      resultsStatus.textContent = "No books matched your search and filters.";
      return;
    }

    resultsStatus.textContent = `${results.length} result(s) shown.`;

    for (const item of results) {
      const row = createElement("li");
      row.className = "result-item";

      const title = createElement("h3");
      title.textContent = item.title;

      const author = createElement("p");
      author.className = "result-author";
      author.textContent = `Author: ${item.author}`;

      const meta = createElement("p");
      meta.className = "result-meta";
      meta.textContent =
        `Type: ${formatFictionType(item.fictionType)} | ` +
        `Age: ${formatAgeRating(item.ageRating)} | ` +
        `Spice: ${formatSpiceLevel(item.spiceLevel)}`;

      const snippet = createElement("p");
      snippet.className = "result-snippet";
      snippet.textContent = item.snippet;

      const subjects = createElement("p");
      subjects.className = "result-subjects";
      subjects.textContent = `Subject(s): ${item.subjects.join(", ") || "none"}`;

      row.append(title, author, meta, snippet, subjects);
      resultsList.append(row);
    }
  }

  function filterMockBooks(params) {
    return filterBooksCollection(fallbackBooks, params);
  }

  function getSelectedSubjects() {
    if (!filtersForm || typeof filtersForm.querySelectorAll !== "function") {
      return [];
    }

    return Array.from(filtersForm.querySelectorAll('input[name="subject"]:checked')).map(
      (input) => input.value.toLowerCase()
    );
  }

  function syncSearchParamsFromInputs() {
    searchParams.query = searchInput ? searchInput.value.trim() : "";
    searchParams.fictionType = fictionTypeInput ? fictionTypeInput.value : "all";
    searchParams.ageRating = ageRatingInput ? ageRatingInput.value : "all";
    searchParams.subjects = getSelectedSubjects();

    if (filtersForm && typeof filtersForm.querySelector === "function") {
      const spiceChoice = filtersForm.querySelector('input[name="spice_level"]:checked');
      searchParams.spiceLevel = spiceChoice ? spiceChoice.value : "any";
    } else {
      searchParams.spiceLevel = "any";
    }
  }

  function setLoadingState(loading) {
    isLoading = loading;

    if (searchButton) {
      searchButton.disabled = loading;
      searchButton.textContent = loading ? "Searching..." : "Search";
    }

    if (filtersForm && filtersForm.elements) {
      for (const control of filtersForm.elements) {
        if (control && typeof control === "object" && "disabled" in control) {
          control.disabled = loading;
        }
      }
    }

    if (searchInput) {
      searchInput.disabled = loading;
    }
  }

  function setErrorMessage(message) {
    if (!resultsError) {
      return;
    }

    if (!message) {
      resultsError.hidden = true;
      resultsError.textContent = "";
      return;
    }

    resultsError.hidden = false;
    resultsError.textContent = message;
  }

  function buildUserFacingError(error) {
    if (error instanceof BooksApiError) {
      if (error.status !== null) {
        return `Live API request failed (${error.status}). Showing fallback results.`;
      }
      return "Unable to reach live API. Showing fallback results.";
    }
    return "Search request failed. Showing fallback results.";
  }

  async function runSearch() {
    if (isLoading) {
      return;
    }

    syncSearchParamsFromInputs();
    const paramsSnapshot = cloneSearchParams(searchParams);
    setErrorMessage("");
    setLoadingState(true);

    if (resultsStatus) {
      resultsStatus.textContent = "Loading results...";
    }

    try {
      const apiResults = await searchBooksApiImpl(paramsSnapshot);
      const filteredResults = filterBooksCollection(apiResults, paramsSnapshot);
      renderResults(filteredResults);
    } catch (error) {
      setErrorMessage(buildUserFacingError(error));
      const fallbackResults = filterMockBooks(paramsSnapshot);
      renderResults(fallbackResults);
    } finally {
      setLoadingState(false);
    }
  }

  async function onSubmit(event) {
    event.preventDefault();
    await runSearch();
  }

  async function onFiltersChange() {
    await runSearch();
  }

  function attachEventHandlers() {
    if (searchForm && typeof searchForm.addEventListener === "function") {
      searchForm.addEventListener("submit", onSubmit);
    }

    if (filtersForm && typeof filtersForm.addEventListener === "function") {
      filtersForm.addEventListener("change", onFiltersChange);
    }
  }

  function getSearchParams() {
    return cloneSearchParams(searchParams);
  }

  return {
    attachEventHandlers,
    runSearch,
    syncSearchParamsFromInputs,
    getSearchParams,
  };
}

export function initializeSearchApp({
  documentRef = globalThis.document,
  searchBooksApiImpl = searchBooksApi,
  fallbackBooks = mockBooks,
} = {}) {
  if (!documentRef || typeof documentRef.querySelector !== "function") {
    return null;
  }

  const searchForm = documentRef.querySelector("#search-form");
  const searchInput = documentRef.querySelector("#search-input");
  const filtersForm = documentRef.querySelector("#filters-form");
  const fictionTypeInput = documentRef.querySelector("#filter-fiction-type");
  const ageRatingInput = documentRef.querySelector("#filter-age-rating");
  const resultsStatus = documentRef.querySelector("#results-status");
  const resultsError = documentRef.querySelector("#results-error");
  const resultsList = documentRef.querySelector("#results-list");
  const searchButton =
    searchForm && typeof searchForm.querySelector === "function"
      ? searchForm.querySelector('button[type="submit"]')
      : null;

  const app = createSearchApp({
    searchForm,
    searchInput,
    searchButton,
    filtersForm,
    fictionTypeInput,
    ageRatingInput,
    resultsStatus,
    resultsError,
    resultsList,
    createElement: (tagName) => documentRef.createElement(tagName),
    searchBooksApiImpl,
    fallbackBooks,
  });
  app.attachEventHandlers();
  return app;
}

if (typeof document !== "undefined") {
  initializeSearchApp();
}
