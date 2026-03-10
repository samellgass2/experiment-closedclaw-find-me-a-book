import test from "node:test";
import assert from "node:assert/strict";

import { createSearchApp } from "../main.js";

function createFakeNode(tagName = "div") {
  return {
    tagName: tagName.toUpperCase(),
    className: "",
    textContent: "",
    children: [],
    append(...nodes) {
      this.children.push(...nodes);
    },
  };
}

function createFakeControl({
  name = "",
  type = "text",
  value = "",
  checked = false,
} = {}) {
  return {
    name,
    type,
    value,
    checked,
    disabled: false,
  };
}

function createEventTarget({ querySelector, querySelectorAll, elements = [] } = {}) {
  const listeners = new Map();

  return {
    elements,
    addEventListener(eventName, handler) {
      const handlers = listeners.get(eventName) ?? [];
      handlers.push(handler);
      listeners.set(eventName, handlers);
    },
    async dispatch(eventName, event = {}) {
      const handlers = listeners.get(eventName) ?? [];
      for (const handler of handlers) {
        await handler(event);
      }
    },
    querySelector(selector) {
      if (typeof querySelector === "function") {
        return querySelector(selector);
      }
      return null;
    },
    querySelectorAll(selector) {
      if (typeof querySelectorAll === "function") {
        return querySelectorAll(selector);
      }
      return [];
    },
  };
}

function buildHarness(searchBooksApiImpl) {
  const searchInput = createFakeControl();
  const searchButton = createFakeControl({ type: "submit", value: "Search" });
  searchButton.textContent = "Search";

  const fictionTypeInput = createFakeControl({
    name: "fiction_type",
    value: "all",
  });
  const ageRatingInput = createFakeControl({
    name: "age_rating",
    value: "all",
  });
  const subjectFantasy = createFakeControl({
    name: "subject",
    type: "checkbox",
    value: "fantasy",
    checked: false,
  });
  const spiceAny = createFakeControl({
    name: "spice_level",
    type: "radio",
    value: "any",
    checked: true,
  });
  const spiceHigh = createFakeControl({
    name: "spice_level",
    type: "radio",
    value: "high",
    checked: false,
  });

  const filtersControls = [
    fictionTypeInput,
    ageRatingInput,
    subjectFantasy,
    spiceAny,
    spiceHigh,
  ];

  const searchForm = createEventTarget({
    querySelector(selector) {
      if (selector === 'button[type="submit"]') {
        return searchButton;
      }
      return null;
    },
  });

  const filtersForm = createEventTarget({
    elements: filtersControls,
    querySelector(selector) {
      if (selector === 'input[name="spice_level"]:checked') {
        return filtersControls.find(
          (control) => control.name === "spice_level" && control.checked
        );
      }
      return null;
    },
    querySelectorAll(selector) {
      if (selector === 'input[name="subject"]:checked') {
        return filtersControls.filter(
          (control) => control.name === "subject" && control.checked
        );
      }
      return [];
    },
  });

  const resultsStatus = { textContent: "" };
  const resultsError = { hidden: true, textContent: "" };
  const resultsList = {
    children: [],
    replaceChildren(...nodes) {
      this.children = [...nodes];
    },
    append(node) {
      this.children.push(node);
    },
  };

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
    createElement: createFakeNode,
    searchBooksApiImpl,
  });
  app.attachEventHandlers();

  return {
    app,
    searchForm,
    searchInput,
    searchButton,
    filtersForm,
    fictionTypeInput,
    ageRatingInput,
    subjectFantasy,
    spiceAny,
    spiceHigh,
    resultsStatus,
    resultsList,
  };
}

function extractResultTitles(resultsList) {
  return resultsList.children.map((row) => {
    const heading = row.children.find((node) => node.tagName === "H3");
    return heading?.textContent ?? "";
  });
}

test("search input and button are wired to submit and pass query", async () => {
  const apiCalls = [];
  const harness = buildHarness(async (params) => {
    apiCalls.push(params);
    return [];
  });

  assert.ok(harness.searchInput);
  assert.ok(harness.searchButton);

  harness.searchInput.value = "galaxy";
  let prevented = false;
  await harness.searchForm.dispatch("submit", {
    preventDefault() {
      prevented = true;
    },
  });

  assert.equal(prevented, true);
  assert.equal(apiCalls.length, 1);
  assert.equal(apiCalls[0].query, "galaxy");
  assert.equal(harness.app.getSearchParams().query, "galaxy");
  assert.equal(harness.searchButton.textContent, "Search");
});

test("filter changes are propagated to API search parameters", async () => {
  const apiCalls = [];
  const harness = buildHarness(async (params) => {
    apiCalls.push(params);
    return [];
  });

  harness.fictionTypeInput.value = "nonfiction";
  harness.ageRatingInput.value = "adult";
  harness.subjectFantasy.checked = true;
  harness.spiceAny.checked = false;
  harness.spiceHigh.checked = true;

  await harness.filtersForm.dispatch("change", {});

  assert.equal(apiCalls.length, 1);
  assert.equal(apiCalls[0].fictionType, "nonfiction");
  assert.equal(apiCalls[0].ageRating, "adult");
  assert.deepEqual(apiCalls[0].subjects, ["fantasy"]);
  assert.equal(apiCalls[0].spiceLevel, "high");
});

test("results list updates when API data changes between searches", async () => {
  const responseSets = [
    [
      {
        title: "Alpha Test Book",
        author: "A. Writer",
        genre: "Mystery",
        age_rating: "teen",
        description: "First API response.",
      },
    ],
    [
      {
        title: "Beta Test Book",
        author: "B. Writer",
        genre: "Mystery",
        age_rating: "teen",
        description: "Second API response first item.",
      },
      {
        title: "Gamma Test Book",
        author: "C. Writer",
        genre: "Science Fiction",
        age_rating: "adult",
        description: "Second API response second item.",
      },
    ],
  ];

  let callCount = 0;
  const harness = buildHarness(async () => {
    const result = responseSets[callCount] ?? responseSets[responseSets.length - 1];
    callCount += 1;
    return result;
  });

  await harness.searchForm.dispatch("submit", {
    preventDefault() {},
  });
  assert.equal(harness.resultsStatus.textContent, "1 result(s) shown.");
  assert.deepEqual(extractResultTitles(harness.resultsList), ["Alpha Test Book"]);

  await harness.searchForm.dispatch("submit", {
    preventDefault() {},
  });
  assert.equal(harness.resultsStatus.textContent, "2 result(s) shown.");
  assert.deepEqual(extractResultTitles(harness.resultsList), [
    "Beta Test Book",
    "Gamma Test Book",
  ]);
});
