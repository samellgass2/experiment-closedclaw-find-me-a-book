# Filters Panel Wireframes

## Scope and intent

These low- to mid-fidelity wireframes define the dedicated filters panel
experience for search results. They extend
[wireframes-main-search.md](./wireframes-main-search.md) and align with
[ux-foundations.md](./ux-foundations.md).

Primary goals:

- make key constraints fast to scan and easy to combine
- avoid overwhelming users through progressive disclosure
- keep applied-state visibility persistent from results context
- support quick mobile refinement with clear apply/clear behavior

In-scope filter dimensions for this panel:

- genre
- age appropriateness
- subject matter
- character dynamics
- spice level
- additional practical refiners surfaced in UX foundations (format, rating,
  language)

## Design principles for comprehension and performance

- Group by decision intent, not database shape (Audience, Story, Content,
  Format/Quality).
- Show only top options initially; provide `Show more` for long lists.
- Use cheap, deterministic controls first (chips/checkboxes/radio), then optional
  advanced controls (range sliders) to reduce render cost and cognitive load.
- Defer expensive count recalculation until `Apply filters` on mobile; desktop can
  apply instantly with lightweight loading feedback.
- Keep applied filters visible in two places:
  1. filter button badge/count
  2. removable chips above the result list

## Desktop wireframes

### A) Results page with left sidebar panel

```text
+------------------------------------------------------------------------------------------------+
| [Find Me a Book]                                                                                |
| [ Search by title, author, or topic...                             ] [Search] [Filters 6]      |
| Applied: [Fantasy x] [Ages 8-10 x] [Friendship x] [Found Family x] [Mild x] [Clear all]       |
| 268 results                                                                  Sort: [Relevance v]|
+-------------------------------------------+----------------------------------------------------+
| Filters                                   | Results                                            |
|-------------------------------------------|----------------------------------------------------|
| [Reset all]                               | Card 1 ...                                         |
|                                           | Card 2 ...                                         |
| Audience                                  | ...                                                |
| Age appropriateness                       |                                                    |
| ( ) All ages                              |                                                    |
| (x) Ages 8-10                             |                                                    |
| ( ) Ages 11-13                            |                                                    |
| ( ) Teen                                  |                                                    |
|                                           |                                                    |
| Story                                     |                                                    |
| Genre                                     |                                                    |
| [x] Fantasy  [ ] Mystery  [ ] Sci-Fi      |                                                    |
| [ ] Historical [ ] Graphic Novel          |                                                    |
| [Show more genres]                        |                                                    |
|                                           |                                                    |
| Subject matter                            |                                                    |
| [x] Friendship [ ] STEM [ ] Family        |                                                    |
| [ ] School [ ] Adventure [ ] Identity     |                                                    |
| [Show more subjects]                      |                                                    |
|                                           |                                                    |
| Character dynamics                        |                                                    |
| [x] Found family                          |                                                    |
| [ ] Team quest [ ] Rivals-to-friends      |                                                    |
| [ ] Siblings [ ] Mentor-student           |                                                    |
|                                           |                                                    |
| Content tone                              |                                                    |
| Spice level                               |                                                    |
| ( ) None  (x) Mild  ( ) Medium  ( ) High  |                                                    |
|                                           |                                                    |
| More filters                              |                                                    |
| Format: [ ] Print [ ] eBook [ ] Audio     |                                                    |
| Min rating: [3.5 v]                       |                                                    |
+-------------------------------------------+----------------------------------------------------+
```

Desktop behavior notes:

- `Filters 6` badge reflects currently applied filter count.
- Chip row is always visible above results; each chip has one-click removal.
- `Clear all` in chip row clears everything globally.
- `Reset all` in panel performs the same action and scrolls to top of panel.
- Sidebar groups are collapsible to keep scanning quick on smaller laptop heights.
- Instant apply is preferred on desktop, with subtle in-panel loading state
  (`Updating results...`) to communicate responsiveness.

### B) Overflow handling for long taxonomies (genre/subject)

```text
Genre
[x] Fantasy  [ ] Mystery  [ ] Sci-Fi  [ ] Romance
[ ] Horror   [ ] Historical
[Show more genres]

[When Show more genres tapped]
+--------------------------------------+
| Find a genre... [search field]       |
| [x] Fantasy                          |
| [ ] Cozy Mystery                     |
| [ ] Space Opera                      |
| [ ] Magical Realism                  |
| ... virtualized list ...             |
| [Done]                               |
+--------------------------------------+
```

Overflow behavior notes:

- Modal/popover list supports local search and virtualized rendering to keep
  large vocabularies fast.
- Selected values return to compact chips/checkboxes in the sidebar.

## Mobile wireframes

### A) Results screen with filter trigger and chips

```text
+----------------------------------------------+
| [<] Search                                    |
| [ dragons for 9 year olds               ] [Go]|
| [Filters (6)] [Sort v]                        |
| 268 results                                    |
| [Fantasy x] [Ages 8-10 x] [Friendship x] ...  |
|----------------------------------------------|
| Result card                                   |
| Result card                                   |
+----------------------------------------------+
```

Mobile results behavior:

- `Filters (6)` is a primary trigger with active badge.
- Applied chips are horizontally scrollable and removable without opening drawer.
- A trailing `Clear all` chip appears once 2+ filters are active.

### B) Full-height filter drawer (one-hand pattern)

```text
+----------------------------------------------+
| Filters                                 [X]   |
| 6 active                                     |
|----------------------------------------------|
| Audience                                      |
| Age appropriateness                           |
| ( ) All ages                                  |
| (x) Ages 8-10                                 |
| ( ) Ages 11-13                                |
| ( ) Teen                                      |
|----------------------------------------------|
| Story                                         |
| Genre                                         |
| [Fantasy] [Mystery] [Sci-Fi] [Show more]     |
| Subject matter                                |
| [Friendship] [STEM] [Family] [Show more]     |
| Character dynamics                            |
| [Found family] [Team quest] [Mentor-student] |
|----------------------------------------------|
| Content tone                                  |
| Spice level                                   |
| ( ) None  (x) Mild  ( ) Medium  ( ) High      |
|----------------------------------------------|
| More filters                                  |
| Format: [ ] Print [ ] eBook [ ] Audio         |
| Min rating: [3.5 v]                           |
|----------------------------------------------|
| [Clear all]                     [Apply filters]|
+----------------------------------------------+
```

Mobile drawer behavior notes:

- Changes are staged in drawer state until `Apply filters`.
- Closing with `X` preserves staged edits only for the current open session;
  applied results remain unchanged until explicit apply.
- `Clear all` removes staged and applied filters in one action, then updates the
  badge/chips after apply.
- Sticky footer keeps `Clear all` and `Apply filters` always reachable.

## Interaction states and user control model

### Applied-state surfacing

- Primary: chips above results (`[Label x]`).
- Secondary: filter trigger badge (`Filters (N)`).
- Tertiary: section-level count in panel headers, example `Story (3)`.

### Clearing behavior

- Individual clear: remove one chip (`x`) from results context.
- Group clear: optional action inside a group header (`Clear genre`).
- Global clear: `Clear all` in chip row, drawer footer, and desktop sidebar.

### Recommended defaults to reduce overload

- Start with no preselected filters.
- Limit initially visible options per multi-select group to 5-7.
- Keep spice level single-select to avoid contradictory states.
- Use plain-language labels and avoid internal taxonomy terms.

## Conceptual mapping to data attributes

This is intentionally conceptual for backend/crawler planning and does not
require final schema decisions.

| UI filter | Conceptual data mapping | Current readiness |
| --- | --- | --- |
| Genre | `genres` taxonomy linked through `book_genres` (`genres.display_name`, `genres.code`) | Available now |
| Age appropriateness | `books.maturity_rating` + optional derived age-band field (`age_min`, `age_max` or `age_band`) | Partial now (`maturity_rating`), richer age bands likely needed |
| Subject matter | Controlled tag set such as `book_subjects` relation or normalized topic tags from description/metadata | Likely new ingestion/modeling work |
| Character dynamics | Narrative relationship tags (for example `found-family`, `mentor-student`) in a `book_character_dynamics` relation | New derived metadata needed |
| Spice level | Content-intensity field (ordinal enum such as `none/mild/medium/high`) sourced from editorial tags or trusted signals | New derived metadata needed |
| Format (supporting) | Edition/format attributes (`paperback`, `hardcover`, `ebook`, `audio`) | Deferred in crawler requirements; future extraction needed |
| Min rating (supporting) | `books.average_rating` numeric threshold | Available now |
| Language (supporting) | `books.language_code` | Available now |

Implementation guidance for later phases:

- Keep UI option identifiers stable (`slug`/`code`) to decouple display labels
  from storage naming.
- Treat subject matter, character dynamics, and spice level as taxonomies with
  curated vocabularies to avoid noisy free-text filters.
- Return filter metadata and counts via a dedicated aggregate endpoint so chips,
  badges, and group counts update without heavy client computation.

## Accessibility and guardrails

- All filter controls must be reachable by keyboard and expose clear labels.
- Chips announce removal actions to assistive tech (`Remove filter: Fantasy`).
- Drawer uses focus trap and restores focus to `Filters` button on close.
- Loading state should be non-blocking and preserve control positions to prevent
  disorientation.

## Acceptance checklist trace

1. Desktop treatment: sidebar filter panel with grouped controls and clear paths.
2. Mobile treatment: full-height drawer with staged apply model.
3. Required dimensions shown: genre, age appropriateness, subject matter,
   character dynamics, spice level.
4. Applied-state visualization shown: chips + button badge + clear individual/all.
5. Data mapping section included for backend/crawler alignment.
