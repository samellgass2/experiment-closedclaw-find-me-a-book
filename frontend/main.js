const searchForm = document.querySelector("#search-form");
const searchInput = document.querySelector("#search-input");
const resultsStatus = document.querySelector("#results-status");
const resultsList = document.querySelector("#results-list");

const sampleResults = [
  {
    title: "The Great Adventure",
    author: "Alex Carter",
    genre: "Fantasy",
  },
  {
    title: "Night Library",
    author: "Jordan Kim",
    genre: "Mystery",
  },
];

function renderResults(results) {
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

    const details = document.createElement("p");
    details.textContent = `Author: ${item.author} · Genre: ${item.genre}`;

    row.append(title, details);
    resultsList.append(row);
  }
}

async function tryFetchBooks(query) {
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

  return payload.map((book) => ({
    title: book.title ?? "Untitled",
    author: book.author ?? "Unknown",
    genre: book.genre ?? "Unknown",
  }));
}

searchForm?.addEventListener("submit", async (event) => {
  event.preventDefault();

  const query = searchInput?.value.trim() ?? "";
  resultsStatus.textContent = "Loading results...";

  try {
    const apiResults = await tryFetchBooks(query);
    renderResults(apiResults);
  } catch {
    // Keep a stable demo experience when backend is not attached.
    const filtered = sampleResults.filter((item) => {
      if (!query) {
        return true;
      }

      const text = `${item.title} ${item.author} ${item.genre}`.toLowerCase();
      return text.includes(query.toLowerCase());
    });

    renderResults(filtered);
  }
});
