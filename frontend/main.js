const searchForm = document.querySelector("#search-form");
const searchInput = document.querySelector("#search-input");
const resultsStatus = document.querySelector("#results-status");
const resultsList = document.querySelector("#results-list");

const mockBooks = [
  {
    title: "The Great Adventure",
    author: "Alex Carter",
    snippet: "An epic coming-of-age journey across wild floating islands.",
    genre: "Fantasy",
  },
  {
    title: "Night Library",
    author: "Jordan Kim",
    snippet: "A shy archivist uncovers coded notes hidden inside returned books.",
    genre: "Mystery",
  },
  {
    title: "Signal in the Snow",
    author: "Priya Das",
    snippet: "Two siblings trace a radio beacon through a frozen research outpost.",
    genre: "Thriller",
  },
  {
    title: "Summer on Alder Street",
    author: "Maya Flores",
    snippet: "A neighborhood project pulls rival friends into an unlikely partnership.",
    genre: "Contemporary",
  },
  {
    title: "The River Clock",
    author: "Nathan Pierce",
    snippet: "A small town mechanic rebuilds an antique clock tied to local history.",
    genre: "Historical",
  },
  {
    title: "Orbit of Small Things",
    author: "Leah Morgan",
    snippet: "A science club launches homemade satellites and learns teamwork.",
    genre: "Science Fiction",
  },
  {
    title: "Letters to a Forgotten Map",
    author: "Evan Holt",
    snippet: "A puzzle trail sends a teen geographer across hidden city landmarks.",
    genre: "Adventure",
  },
  {
    title: "Tea Shop at Dawn",
    author: "Harper Lee",
    snippet: "An apprentice baker keeps a family shop alive while solving daily mysteries.",
    genre: "Slice of Life",
  },
  {
    title: "Wildflower Code",
    author: "Rina Shah",
    snippet: "A student botanist discovers encrypted field journals in a greenhouse.",
    genre: "Mystery",
  },
  {
    title: "Echoes Under Glass",
    author: "Marcus Vale",
    snippet: "A museum volunteer tracks missing artifacts and buried family secrets.",
    genre: "Drama",
  },
  {
    title: "Paper Moons",
    author: "Tess Rowan",
    snippet: "A school theater crew rebuilds trust before opening night chaos.",
    genre: "Young Adult",
  },
  {
    title: "Northbound Lantern",
    author: "Iris Bennett",
    snippet: "A coastal rescue team faces a storm while searching for a lost vessel.",
    genre: "Adventure",
  },
];

function normalizeBook(book) {
  return {
    title: book.title ?? "Untitled",
    author: book.author ?? "Unknown",
    snippet: book.snippet ?? book.description ?? "No description available.",
    genre: book.genre ?? "Unknown",
  };
}

function renderResults(results) {
  if (!resultsList || !resultsStatus) {
    return;
  }

  resultsList.replaceChildren();

  if (!results.length) {
    resultsStatus.textContent = "No books matched that search.";
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

    const snippet = document.createElement("p");
    snippet.className = "result-snippet";
    snippet.textContent = item.snippet;

    row.append(title, author, snippet);
    resultsList.append(row);
  }
}

function filterMockBooks(query) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return mockBooks.map(normalizeBook);
  }

  return mockBooks
    .filter((item) => {
      const searchableText = `${item.title} ${item.author} ${item.genre} ${item.snippet}`
        .toLowerCase();
      return searchableText.includes(normalizedQuery);
    })
    .map(normalizeBook);
}

async function fetchBooksFromApi(query) {
  const url = new URL("/api/books", window.location.origin);
  if (query) {
    url.searchParams.set("q", query);
  }

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
async function searchBooks(query) {
  try {
    return await fetchBooksFromApi(query);
  } catch {
    return filterMockBooks(query);
  }
}

if (searchForm && searchInput) {
  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const query = searchInput.value.trim();
    if (resultsStatus) {
      resultsStatus.textContent = "Loading results...";
    }

    const results = await searchBooks(query);
    renderResults(results);
  });
}
