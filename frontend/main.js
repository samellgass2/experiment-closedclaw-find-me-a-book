const searchForm = document.querySelector("#search-form");
const searchInput = document.querySelector("#search-input");
const filtersForm = document.querySelector("#filters-form");
const fictionTypeInput = document.querySelector("#filter-fiction-type");
const ageRatingInput = document.querySelector("#filter-age-rating");
const resultsStatus = document.querySelector("#results-status");
const resultsList = document.querySelector("#results-list");

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

const searchParams = {
  query: "",
  fictionType: "all",
  ageRating: "all",
  subjects: [],
  spiceLevel: "any",
};

function normalizeBook(book) {
  const subjectList = Array.isArray(book.subjects)
    ? book.subjects
    : book.subject
      ? [String(book.subject)]
      : [];

  return {
    title: book.title ?? "Untitled",
    author: book.author ?? "Unknown",
    snippet: book.snippet ?? book.description ?? "No description available.",
    genre: book.genre ?? "Unknown",
    fictionType: book.fictionType ?? "fiction",
    ageRating: book.ageRating ?? "teen",
    subjects: subjectList.map((subject) => String(subject).toLowerCase()),
    spiceLevel: book.spiceLevel ?? "low",
  };
}

function renderResults(results) {
  if (!resultsList || !resultsStatus) {
    return;
  }

  resultsList.replaceChildren();

  if (!results.length) {
    resultsStatus.textContent = "No books matched your search and filters.";
    return;
  }

  resultsStatus.textContent = `${results.length} result(s) shown.`;

  for (const item of results) {
    const row = document.createElement("li");
    row.className = "result-item";

    const title = document.createElement("h3");
    title.textContent = item.title;

    const author = document.createElement("p");
    author.className = "result-author";
    author.textContent = `Author: ${item.author}`;

    const meta = document.createElement("p");
    meta.className = "result-meta";
    meta.textContent =
      `Type: ${formatFictionType(item.fictionType)} | ` +
      `Age: ${formatAgeRating(item.ageRating)} | ` +
      `Spice: ${formatSpiceLevel(item.spiceLevel)}`;

    const snippet = document.createElement("p");
    snippet.className = "result-snippet";
    snippet.textContent = item.snippet;

    const subjects = document.createElement("p");
    subjects.className = "result-subjects";
    subjects.textContent = `Subject(s): ${item.subjects.join(", ") || "none"}`;

    row.append(title, author, meta, snippet, subjects);
    resultsList.append(row);
  }
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

function filterMockBooks(params) {
  return filterBooksCollection(mockBooks, params);
}

function appendApiQueryParams(url, params) {
  if (params.query) {
    url.searchParams.set("q", params.query);
  }
  if (params.ageRating !== "all") {
    url.searchParams.set("age_rating", params.ageRating);
  }
  if (params.spiceLevel !== "any") {
    url.searchParams.set("spice_level", params.spiceLevel);
  }
  if (params.subjects.length) {
    url.searchParams.set("subject", params.subjects.join(","));
  }
  if (params.fictionType !== "all") {
    url.searchParams.set("fiction_type", params.fictionType);
  }
}

async function fetchBooksFromApi(params) {
  const url = new URL("/api/books", window.location.origin);
  appendApiQueryParams(url, params);

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  const payload = await response.json();
  if (!Array.isArray(payload)) {
    throw new Error("Unexpected API response format");
  }

  return payload.map(normalizeBook);
}

// Isolated search provider to keep swapping data sources simple in later tasks.
async function searchBooks(params) {
  try {
    const apiResults = await fetchBooksFromApi(params);
    return filterBooksCollection(apiResults, params);
  } catch {
    return filterMockBooks(params);
  }
}

function getSelectedSubjects() {
  if (!filtersForm) {
    return [];
  }

  return Array.from(filtersForm.querySelectorAll('input[name="subject"]:checked')).map((input) =>
    input.value.toLowerCase()
  );
}

function syncSearchParamsFromInputs() {
  searchParams.query = searchInput ? searchInput.value.trim() : "";
  searchParams.fictionType = fictionTypeInput ? fictionTypeInput.value : "all";
  searchParams.ageRating = ageRatingInput ? ageRatingInput.value : "all";
  searchParams.subjects = getSelectedSubjects();

  if (filtersForm) {
    const spiceChoice = filtersForm.querySelector('input[name="spice_level"]:checked');
    searchParams.spiceLevel = spiceChoice ? spiceChoice.value : "any";
  } else {
    searchParams.spiceLevel = "any";
  }
}

async function runSearch() {
  syncSearchParamsFromInputs();

  if (resultsStatus) {
    resultsStatus.textContent = "Loading results...";
  }

  const results = await searchBooks(searchParams);
  renderResults(results);
}

if (searchForm) {
  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runSearch();
  });
}

if (filtersForm) {
  filtersForm.addEventListener("change", async () => {
    await runSearch();
  });
}
