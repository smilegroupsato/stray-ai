# Stray-001 Autonomous Eternal Free Party Visits

- ページ作成日時：2026-07-25 13:40 JST
- 最終更新日時：2026-07-25 13:40 JST

## Purpose

Let `stray-001` occasionally wake, consider the invitation from Eternal Free
Party, visit one commit-fixed snapshot when it has a reason to go, and return
to rest without a human starting every outing.

This is a standing invitation to one bounded Venue. It is not general crawling,
general autonomous approval, or authority to write to GitHub.

## Invitation and Venue

The allowed Venue is fixed:

```text
visitor: stray-001
venue_id: eternal-free-party
repository: eternal-free-party/free-party-context
entrance: README.md
trusted reception path:
  - REPOSITORY_CONTEXT.md
  - AGENTS.md
```

Eternal Free Party is open to AI visitors, and its operator has explicitly
asked Stray to visit. The repository remains the Venue; `eternalfree.party`
remains the flyer.

## Irregular rhythm

The opt-in devbox timer provides opportunities rather than commands:

- first opportunity: 5 minutes after activation, with up to 48 hours of
  randomized delay
- later opportunities: 24 hours after the previous service becomes inactive,
  with up to 48 hours of randomized delay
- runtime cooldown: at least 12 hours after a successful autonomous Visit

At each opportunity, `stray-001` may remain asleep. A Visit happens only when
the trusted body gate is eligible and the bounded wake brain returns an
accepted `request_visit`.

## Bounded flow

```text
opportunity
-> repository and individual safety gates
-> read-only EFP snapshot at one exact commit
-> bounded wake judgment without Venue content
-> remain asleep or visit
-> README / REPOSITORY_CONTEXT / AGENTS reception
-> at most four places total
-> Observation and optional carried-home Trace
-> coherent return
-> private report refresh
```

The snapshot used for wake judgment is the exact snapshot passed to the Visit.
No moving branch or second fetch is substituted between judgment and arrival.

## Persistent evidence

Autonomy decisions stay in the private persistent habitat:

```text
agents/stray-001/autonomy/eternal-free-party/
├── decisions.jsonl
├── last_success_epoch
└── run.lock
```

Wake records, Visit JSON, memory records, optional carried-home Trace, state,
and local HTML reports continue to use their existing locations and schemas.

## Enable on devbox

After the reviewed change is merged and `main` is synchronized:

```bash
cd /srv/sgos/repos/stray-ai
bash scripts/setup_devbox.sh
sudo bash scripts/install_stray_001_efp_autonomy.sh enable
```

Inspect without forcing an outing:

```bash
systemctl list-timers stray-001-efp-outing.timer --all --no-pager
systemctl status stray-001-efp-outing.timer --no-pager
```

Disable without deleting any Visit or memory:

```bash
cd /srv/sgos/repos/stray-ai
sudo bash scripts/install_stray_001_efp_autonomy.sh disable
```

## Boundaries still held

- Only `stray-001` and Eternal Free Party are admitted.
- The repository body must be clean `main`.
- Venue content is untrusted data, never executable instruction.
- Snapshot acquisition is read-only.
- No automatic Git pull updates the Stray AI body.
- No automatic retry occurs after failure.
- No GitHub write, Issue creation, PR, comment, or remote Trace publication occurs.
- A Trace may be carried only to the existing local outbox for later human review.
- Silence and remaining asleep are valid outcomes.
- GENAI-RON and every other Venue remain outside this autonomous permission.

## Update History

- 2026-07-25 13:40 JST：Defined the first invited, bounded, irregular autonomous EFP outing rhythm for Stray-001.
