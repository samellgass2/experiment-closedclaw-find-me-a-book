# UI Wireframes Overview: Core Book Discovery Flow

## Purpose

This overview ties together the core discovery wireframes so implementation can
build one coherent experience across search, filters, and results:

- [Main search view](./wireframes-main-search.md)
- [Filters panel](./wireframes-filters-panel.md)
- [Results list and items](./wireframes-results-and-items.md)

## End-to-end user flow

### 1. Land on main search page

The user starts on the pre-search state defined in
[wireframes-main-search.md](./wireframes-main-search.md):

- prominent search input (`title, author, or topic`)
- visible primary search CTA
- visible `Filters` entry point
- empty-state guidance chips for quick starts

This ensures users can begin either with a free-text query or with immediate
filter intent.

### 2. Execute search and enter results context

After submit (`Enter` or button tap), the UI transitions to the post-search
state from [wireframes-main-search.md](./wireframes-main-search.md):

- query persists in the search field
- applied filter chips appear near results header
- result count and sort appear in context

The results region then follows
[wireframes-results-and-items.md](./wireframes-results-and-items.md), with
scannable cards/rows and a stable field order (title, author, audience, genre,
subject, spice, character dynamics, match reason).

### 3. Open and adjust filters

Filter refinement uses the control model in
[wireframes-filters-panel.md](./wireframes-filters-panel.md):

- desktop: left sidebar with grouped controls and instant apply
- mobile: full-height drawer with staged edits and explicit `Apply filters`
- applied state visible through `Filters (N)` plus removable chips above results
- clear actions available at individual chip, section, and global levels

### 4. Review updated results and continue browsing

Results behavior is driven by
[wireframes-results-and-items.md](./wireframes-results-and-items.md):

- sticky query/filter context while scrolling
- result list updates reflect current query + filter state
- desktop navigation via pagination (or approved load-more alternative)
- mobile navigation via load-more default (with infinite-scroll alternative)
- item-level entry into detail view via title / `View details`

## Key interaction patterns

### Mobile filters open pattern

`Filters (N)` opens a full-height drawer. Edits are staged until `Apply
filters`; closing with `X` does not commit staged edits to results. Sticky
drawer footer keeps `Clear all` and `Apply filters` reachable.

### Results update model

- desktop: instant apply for most filter interactions, with lightweight
  `Updating results...` feedback
- mobile: batched updates on explicit apply to avoid excessive redraw and keep
  interactions predictable
- query text, chips, sort, and counts stay visible or one interaction away

### Responsiveness and load-feel expectations

- above-the-fold should show meaningful content quickly (empty guidance before
  query, multiple result items once queried)
- state changes should avoid disruptive layout jumps
- loading states should preserve header/chip/filter control positions
- interactions should feel near-immediate for control feedback, with clear
  progress messaging when results recompute

## Open UX questions and tradeoffs

1. Desktop results navigation: keep strict pagination for location clarity, or
   adopt load-more for continuity with mobile behavior.
2. Mobile drawer staging: whether staged edits should persist if the user closes
   and reopens filters before applying.
3. Long-taxonomy controls (`Show more`): decide threshold values and whether
   modal search defaults to recent selections.
4. Result density vs metadata depth: confirm when to collapse tags into `+N
   more` across narrow viewports.
5. No-results recovery priority: whether `Clear filters` or `Broaden query`
   should be the primary CTA for each persona.

## Project spec acceptance alignment

The wireframe set now covers all major views required by the project spec:

- search view: [wireframes-main-search.md](./wireframes-main-search.md)
- filters view: [wireframes-filters-panel.md](./wireframes-filters-panel.md)
- results view: [wireframes-results-and-items.md](./wireframes-results-and-items.md)

Together, these are complete and ready to guide frontend implementation of the
core book discovery experience.
