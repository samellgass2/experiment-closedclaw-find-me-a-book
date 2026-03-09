# Main Search View Wireframes

## Scope and intent

These low- to mid-fidelity wireframes define the main search view for finding
books by title, author, or topic. They focus on:

- prominent search input
- obvious filters entry point
- initial results area behavior before and after a query

They are aligned to personas and UX checklist guidance in
[ux-foundations.md](./ux-foundations.md):

- Parent selecting age-appropriate books (fast mobile refinement)
- Educator building a constrained reading list (clear filter state)
- Avid reader exploring genres (quick pivoting of query and filters)

## UX checklist alignment (explicit)

The wireframes explicitly satisfy these checklist items from
`docs/ui/ux-foundations.md`:

1. `Search input is prominent and understandable without helper text.`
2. `Search state is explicit (query shown, clear action available).`
3. `Applied filters are visible from the results context and removable directly.`
4. `Mobile layout keeps search, filters, and results usable with one hand.`
5. `Sort order and total/estimated results are visible near the list.`

## Desktop wireframe

### A) Pre-search empty state (before first query)

```text
+--------------------------------------------------------------------------------+
| Global Nav: [Find Me a Book] [Browse] [Saved] [Sign In]                        |
+--------------------------------------------------------------------------------+
|                                                                                |
|  Discover your next book                                                       |
|                                                                                |
|  [ Search by title, author, or topic...                         ] [Search CTA] |
|                                              [Filters icon + "Filters"]       |
|                                                                                |
|  Quick hints: Try "space adventure", "grade 4 mystery", "Octavia Butler"      |
|                                                                                |
|  ---------------------------------------------------------------------------   |
|  Results area placeholder                                                       |
|                                                                                |
|  [ Empty state card ]                                                          |
|  - Message: "Start with a search to see matching books."                      |
|  - Recovery action: "Use popular topics" chips                                |
|  - Optional chips: [Fantasy] [STEM] [Ages 8-10] [Award Winners]               |
|                                                                                |
+--------------------------------------------------------------------------------+
```

Element labels:

- Global navigation: top bar with core destinations.
- Main search bar: centered and above the fold, primary visual anchor.
- Primary CTA: `Search` button adjacent to input.
- Prominent filters entry point: `Filters` button with icon at search row.
- Placeholder area: reserved results panel showing empty state + recovery cues.

Interaction state notes:

- `Enter` key and `Search` CTA trigger initial query.
- Filters button opens panel/drawer even before search; selected filters are
  staged and visible once results context appears.
- Empty state includes actionable next steps to prevent dead ends.

### B) Post-search state (after initial query with results)

```text
+--------------------------------------------------------------------------------+
| Global Nav: [Find Me a Book] [Browse] [Saved] [Sign In]                        |
+--------------------------------------------------------------------------------+
| [ space adventure books for 9 year olds                         ] [Search CTA] |
| [Filters]  Applied: [Age 8-10 x] [Sci-Fi x] [Paperback x]                      |
|                                                          Sort: [Relevance v]   |
|                                                  124 results                   |
+--------------------------------------+-----------------------------------------+
| Filters panel (desktop side rail)    | Results list                             |
|--------------------------------------|-----------------------------------------|
| Audience                              | 1) "The Wild Robot"                     |
| [x] Ages 8-10                         |    by Peter Brown                       |
| [ ] Ages 11-13                        |    Rating: 4.5 | Format: Print/eBook    |
|                                      |    Why this matches: sci-fi, age fit     |
| Genre                                 |                                         |
| [x] Sci-Fi                            | 2) "Space Case"                          |
| [ ] Mystery                           |    by Stuart Gibbs                      |
|                                      |    Rating: 4.2 | Ages: 8-12             |
| Format                                |    Why this matches: space + middle grade|
| [x] Paperback                         |                                         |
| [ ] eBook                             | 3) ... progressive list                  |
|                                      |                                         |
| [Clear all filters]                   | [Load more / pagination]                |
+--------------------------------------+-----------------------------------------+
```

Element labels:

- Search input remains visible with active query text.
- Filters invocation remains obvious (`Filters` button) plus side-rail filters.
- Applied filter chips shown near results header and removable inline.
- Results area contains sortable metadata-rich list with relevance cues.

Interaction state notes:

- Removing a chip (`x`) updates results without losing query text.
- Sort changes keep query + filter state intact.
- Back navigation should preserve query, filter chips, and scroll position.
- If no results, swap list with no-results card including `Clear filters` and
  `Broaden search` actions.

## Mobile wireframe

### A) Pre-search empty state (one-hand friendly)

```text
+--------------------------------------+
| [Logo]                    [Menu]     |
+--------------------------------------+
| Search books                          |
| [ title, author, or topic...   ] [Go]|
| [Filters]                              |
|--------------------------------------|
| Empty state                           |
| "Search to find books for your reader"|
| [Popular: Fantasy] [Ages 8-10]       |
| [Popular: Graphic Novels]            |
+--------------------------------------+
```

Mobile behavior notes:

- Search field and `Go` CTA are in the top thumb-reachable zone.
- Single-tap `Filters` opens full-height drawer with clear close control.
- Empty state offers large tap targets for suggested starting chips.

### B) Post-search state (results + filter drawer pattern)

```text
+--------------------------------------+
| [<] Search                            |
| [ space adventure for kids      ] [Go]|
| [Filters (3)]   [Sort: Relevance v]  |
| 124 results                            |
|--------------------------------------|
| [Age 8-10 x] [Sci-Fi x] [Paperback x]|
|--------------------------------------|
| Result card 1                         |
| The Wild Robot                        |
| Peter Brown                           |
| 4.5★  Ages 8-10  Paperback            |
| Why this matches: space, age fit      |
|--------------------------------------|
| Result card 2 ...                     |
+--------------------------------------+

[When Filters tapped]
+--------------------------------------+
| Filters                        [Done] |
| Audience                               |
| (x) Ages 8-10                          |
| ( ) Ages 11-13                         |
| Genre                                  |
| (x) Sci-Fi                             |
| Format                                 |
| (x) Paperback                          |
| [Clear all]            [Apply filters] |
+--------------------------------------+
```

Mobile behavior notes:

- Query and filter count remain visible at top while scrolling.
- Applied filters are represented as horizontally scrollable chips that can be
  removed directly.
- Drawer actions are explicit: `Done` (close), `Apply filters`, `Clear all`.

## State coverage summary

- Pre-search state: guidance-focused empty layout with immediate recovery
  actions and visible search+filters controls.
- Post-search with results: query persistence, active filters visibility,
  sortable results, and metadata for quick decisions.

## Accessibility and interaction guardrails

- All controls are keyboard focusable on desktop (`Search`, `Filters`, chips,
  `Sort`, result links).
- Touch targets for mobile controls are sized for one-handed operation.
- Labels are plain language (`Age`, `Genre`, `Format`) to reduce cognitive load.
- State changes (loading/no results) are designed to appear in the results
  region without disorienting layout shifts.
