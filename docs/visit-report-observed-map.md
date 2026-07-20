# Visit Report Observed Venue Map

Visit Report v0 Phase 3 generates `map.html` from preserved Visit JSON.

The map shows only where the visitor was recorded as walking. It is not a repository tree, a website crawl, or a claim to know the full venue.

## What is drawn

For each observed venue or immutable snapshot, the generator derives:

- pages that appeared in recorded Visit steps
- directed transitions between consecutive steps
- how many Visits touched each page
- how many times a repeated transition was walked
- entrance and terminal observations
- chronological route summaries linked to local Visit Reports

The same information is shown both as an inline SVG and as accessible HTML tables.

## Venue identity

Trusted source-aware Visits are grouped by:

```text
repository URL
+ exact observed commit
+ trusted local snapshot identity
```

Different commits are not merged into one asserted state.

Local-only Visits remain visible as separate local habitats. They receive no fabricated repository or external page links.

## Links and navigation

`index.html` links to `map.html` through a relative path. `map.html` links back to `index.html`.

Trusted source-aware nodes link to the exact observed page:

```text
https://github.com/<owner>/<repository>/blob/<commit>/<path>
```

Route summaries link to named local Visit Reports through relative links.

## Boundaries

Map generation performs no remote request and does not crawl the venue snapshot.

It does not infer:

- unvisited pages
- unseen repository links
- relationships not present in consecutive Visit steps
- current remote state

It does not modify Visit JSON, memory, profile, state, Trace files, or wake-check records. Absolute local paths are used only as internal grouping keys and are never emitted into generated HTML.

An empty archive still produces a truthful empty `map.html`.
