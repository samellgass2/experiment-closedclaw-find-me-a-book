# Results List and Item Wireframes

## Scope and intent

This document defines low- to mid-fidelity wireframes for the search results
experience, focused on:

- desktop and mobile list layouts
- per-item metadata needed for fast suitability scanning
- multi-result navigation pattern (pagination vs load more/infinite options)
- persistent visibility of query + active filters while scrolling
- entry from each result item into a future book detail page

This extends:

- [wireframes-main-search.md](./wireframes-main-search.md)
- [wireframes-filters-panel.md](./wireframes-filters-panel.md)

## Content priorities per result item

Each result must expose enough context to judge fit without opening details.
Priority order:

1. `Title` (primary link target)
2. `Author`
3. `Audience / Age rating`
4. `Genre`
5. `Subject matter tags`
6. `Spice level` indicator
7. `Character dynamics` tags
8. Optional support: rating, match reason, availability format

## Desktop wireframe

### A) Results page list layout (with sticky context)

```text
+--------------------------------------------------------------------------------------------------+
| Global Nav: [Find Me a Book] [Browse] [Saved] [Account]                                          |
+--------------------------------------------------------------------------------------------------+
| Sticky Search Context Bar                                                                         |
| [ mystery books with found family                                           ] [Search] [Filters] |
| Active: [Age 11-13 x] [Mystery x] [Found Family x] [Spice: None-Mild x] [Clear all]             |
| 186 results                                                   Sort: [Best Match v]  View: [List]  |
+--------------------------------------------+-----------------------------------------------------+
| Left rail filters (collapsible groups)      | Results list (scrollable)                           |
|---------------------------------------------|-----------------------------------------------------|
| Audience                                     | Above the fold on common laptop (~900px tall):      |
| ( ) 8-10  (x) 11-13  ( ) Teen               | - ~3 full items + top of item 4                     |
|                                             |                                                     |
| Genre                                        | [Result #1 card/row]                                 |
| [x] Mystery [ ] Fantasy [ ] Sci-Fi          | [Result #2 card/row]                                 |
|                                             | [Result #3 card/row]                                 |
| Subject matter                               | [Result #4 partially visible]                        |
| [x] Found Family [ ] Grief [ ] Adventure    |                                                     |
|                                             | ...                                                  |
| Character dynamics                           |                                                     |
| [x] Found Family [ ] Mentor-Student         | Pagination footer (default desktop):                 |
|                                             | [< Prev] [1] [2] [3] [4] [Next >]                   |
| Spice level                                  |                                                     |
| (x) None/Mild  ( ) Medium  ( ) High         | Alternative acceptable pattern:                      |
|                                             | [Load 20 more] with preserved scroll anchor         |
+--------------------------------------------+-----------------------------------------------------+
```

### B) Desktop item row/card anatomy

```text
+--------------------------------------------------------------------------------------------------+
| [Cover]  Title: The Graveyard Riddle                                            [Save] [Details] |
|         by Jordan Hale                                                                       4.4★ |
|                                                                                                  |
|         Audience: Ages 11-13        Genre: Mystery, Adventure                                   |
|         Subject tags: [Found Family] [Boarding School] [Secrets]                                |
|         Spice: [Low ▢▢■□□]  (None-Mild)                                                          |
|         Character dynamics: [Reluctant Allies] [Found Family]                                   |
|         Why it matches: query "mystery" + filters (Ages 11-13, Found Family)                   |
+--------------------------------------------------------------------------------------------------+
```

Desktop item behavior notes:

- `Title` and `Details` both open the future book detail view (same destination).
- Row hover state raises contrast/border and underlines title to indicate click.
- `Save` is secondary and does not compete with primary detail entry.
- Spice indicator uses both text and visual intensity bar for accessibility.

## Mobile wireframe

### A) Mobile results layout with sticky top context

```text
+----------------------------------------------+
| [<] Search                                   |
| [ mystery found family                 ] [Go]|
| [Filters (4)] [Sort v]                       |
| 186 results                                  |
| [11-13 x] [Mystery x] [Found Family x] ...   |
+----------------------------------------------+
|                                              |
| Above the fold on common mobile (~780px):    |
| - ~1 full card + ~60% of card 2              |
|                                              |
| [Result card 1]                               |
| [Result card 2 partial]                       |
|                                              |
| Scroll ...                                    |
+----------------------------------------------+
| Pattern options for additional results:       |
| 1) Preferred mobile default: [Load more]      |
| 2) Alternate: Infinite scroll + Back to top   |
+----------------------------------------------+
```

Sticky context behavior on mobile:

- Search query stays visible in compact header while scrolling down.
- Filter access remains one tap (`Filters (N)` badge stays in header).
- Active chips remain accessible via horizontal chip rail under header.

### B) Mobile result card anatomy

```text
+----------------------------------------------+
| [Cover]  The Graveyard Riddle          [Save]|
|         Jordan Hale                          |
|         Ages 11-13 • Mystery • 4.4★         |
|         Subject: [Found Family] [Secrets]    |
|         Spice: Mild  ▢▢■□□                   |
|         Dynamics: Reluctant Allies           |
|         Why match: mystery + found family    |
|         [View details >]                     |
+----------------------------------------------+
```

Mobile interaction notes:

- Card tap target: title area + `View details` CTA open detail view.
- `Save` is isolated in top-right to avoid accidental detail navigation.
- Touch feedback: pressed state darkens border/background briefly.

## Scannability and visual hierarchy notes

### 1) Information weight

- Line 1: `Title` receives strongest contrast and largest type.
- Line 2: `Author` has medium emphasis.
- Line 3: compact factual strip (`Age`, `Genre`, optional rating) for fast scan.
- Lines 4-6: tags and qualifiers (`Subject`, `Spice`, `Dynamics`) in grouped chips.

### 2) Suitability-first cues

- `Audience` and `Spice` are positioned high in the card (decision-critical for
  parents/educators).
- `Subject` and `Character dynamics` appear as chips to speed thematic scanning.
- `Why it matches` appears at bottom as relevance proof, not top-level noise.

### 3) Consistency rules

- Always show the same field order to reduce cognitive load during comparison.
- Truncate long tag sets after 2 lines with `+N more` expansion.
- Keep one primary action (`View details`) and one secondary action (`Save`).

## Results navigation model

### Desktop

- Default wireframe uses numbered pagination for location clarity and easy back
  navigation.
- Preserve query, filters, sort, and page index in URL/state.
- On back from detail, return to prior page and row scroll position.

### Mobile

- Preferred pattern: `Load more` batches (20 items per batch) to avoid sudden
  disorientation and footer starvation from raw infinite scroll.
- Alternate acceptable pattern: infinite scroll with visible `Back to top` and
  sticky context bar.
- On back from detail, restore previous scroll offset and loaded batch count.

## Persistent context while browsing

The following remain visible or one interaction away at all times:

1. Current query text (sticky desktop bar / compact sticky mobile header)
2. Active filter count (`Filters (N)`)
3. Applied filters (chip row with per-chip remove)
4. Result count and sort control

Recovery controls:

- `Clear all` appears in chip row when at least one filter is active.
- No-results state should include `Clear filters` and `Broaden query` actions
  without forcing users back to top.

## Optional states (for future UI polish)

### Hover (desktop)

- Slight elevation + title underline on row hover.
- `View details` affordance appears stronger on hover.

### Focus (keyboard)

- Visible focus ring around interactive row/title link.
- Chip removal buttons expose clear labels (`Remove filter: Mystery`).

### Loading additional results

- Skeleton rows mimic final card geometry.
- Keep sticky query/filter context static to avoid jumpiness.

## Acceptance criteria traceability

1. Desktop representation included: yes (layout + item anatomy).
2. Mobile representation included: yes (layout + card anatomy).
3. Required item data included: title, author, genre, audience/age,
   subject tags, spice level, and character dynamics.
4. Multi-result navigation shown: desktop pagination + mobile load more/
   infinite-scroll note.
5. Query and filter visibility while scrolling documented via sticky context and
   chip rail.
6. Entry to detail view shown: title link and `View details` action.
