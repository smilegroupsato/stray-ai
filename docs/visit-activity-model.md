# Visit Activity Model

- ページ作成日時：2026-07-25 12:43 JST
- 最終更新日時：2026-07-25 12:43 JST

## Definition

A Visit is one bounded encounter between a Stray individual and a Venue.

Visit does not mean only travel to an external site. A repository can be a
Venue, and touching its documents can be a Visit.

The shared sequence is:

```text
Wake or self-wake
  -> Visit
  -> activity
  -> Observation and optional Trace
  -> Return
```

Current activity types include:

- `venue_visit`: walking through a bounded external or snapshotted Venue;
- `document_rummage`: skimming and reading documents in a repository Venue.

## Rummage relationship

Rummage is not parallel to Visit. It is an activity inside Visit.

A structured runtime rummage therefore preserves two linked records:

- `rummages/<stamp>.json`: activity-specific detail, including reading modes,
  margin notes, memories, sunlit thought, and Trace;
- `visits/<stamp>.json`: the common encounter envelope used by the Visit
  archive and observed map.

The Visit record points back to the rummage record. Both are local persistent
evidence. Neither grants write authority to the visited repository.

## Existing Stray-002 evidence

The first approved hand-authored home-shelf rummage is preserved as the first
`document_rummage` Visit. The migration command also projects every existing
structured runtime rummage into a Visit exactly once.

```bash
stray-ai-migrate-rummage-visits \
  /srv/sgos/data/stray-ai/agents/stray-002 \
  --seed-visit \
  agents/stray-002/visits/2026-07-23_215600.json
```

The migration is idempotent and fail-closed on a conflicting Visit filename.
It preserves the individual's shelf-gap resting location.

## Display

- The Visit archive shows every encounter and its `activity_type`.
- The observed map groups document rummages under the recorded repository
  Venue, such as `stray-ai`.
- The Rummage page remains an activity-specific deep view.
- The individual page remains the entry point for the individual's ecology.

## Safety boundary

- No wake pipeline is invoked by a home-shelf rummage.
- No external Venue is entered.
- No repository content is changed.
- No GitHub or public-internet write is granted.
- Visit evidence and local HTML refresh remain inside the existing persistent
  devbox boundary.

## Update History

- 2026-07-25 12:43 JST：Defined Visit as the common encounter envelope and Rummage as `document_rummage` activity.
