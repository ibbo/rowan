# Difficulty and the nightly SCDDB refresh

Verified 19 September 2026 on chatscd.com (`chatscd.service`,
`/home/ubuntu/dance-teacher`). The existing cron runs at 02:15 UTC daily under
`flock`; its recent runs succeeded. The downloaded base `dance` table already
contained `rscds_grade`, but ChatSCD's derived tables and tools omitted it.

The live download contained 23,662 dances: 379 grade 1, 421 grade 2, 155 grade 3,
6 grade 4, and 22,701 ungraded (`-1`). Of 1,061 dances linked to an RSCDS
publication, 933 had grades and 128 did not. Publication membership and grading
are separate: do not infer either from the other.

## Meaning and provenance

SCDDB displays these labels (verified on the linked dance pages):

| Grade | Meaning | Example |
|---|---|---|
| 1 | Suitable for everyone; one ghillie | [Reel of the 51st Division](https://my.strathspey.org/dd/dance/5525/) |
| 2 | An experienced partner would be helpful; two ghillies | [Haymaking](https://my.strathspey.org/dd/dance/2821/) |
| 3 | For more confident dancers; three ghillies | [Brig o' Bogendreep](https://my.strathspey.org/dd/dance/803/) |
| 4 | Expert-level or unusual dance unsuitable for most programmes | [Lilibet's Strathspey](https://my.strathspey.org/dd/dance/15435/) |

The fourth value is retained as supplied by SCDDB; do not invent a four-ghillie
label. The upstream field is the source of truth, not an inferred grade.
Unknown grades become SQL NULL in the search tables and JSON null in tools.
Intensity is an activity measure, not a validated cognitive difficulty rating.

## Agent behaviour

`find_dances` supports `min_rscds_grade`, `max_rscds_grade`,
`has_rscds_grade` and `sort_by_rscds_grade`. Grade filtering and sorting exclude
ungraded dances. Other search filters still combine with these filters.

Search results, dance details, crib searches, publication dances and full cribs
include the grade, readable label, intensity, difficulty source and any legacy
estimate. Both the chat and lesson agents receive the same grade-first guidance.

For dances without grades, including non-RSCDS dances, the previous intensity
bands remain available as explicitly labelled estimates: positive values <=40
easy, 41-69 medium, >=70 hard. They are never converted to ghillies or returned
as an estimate when a published grade exists. Cribs, formation transitions and
audience familiarity must inform recommendations. If intensity is also missing,
difficulty remains unassessed.

The old misleading instructions were in `find_dances`,
`docs/database_fields_roadmap.md` and `test_intensity_filter.py`; these are corrected.
`INTENSITY_RECURSION_FIX.md` is marked historical. The programme planner also
uses published grades for optional difficulty balances and coverage checks (see
`programme-planner.md`). It was deployed separately, on 4 October 2026.

## Refresh reliability

`refresh_scddb.py` now builds the derived tables, FTS index and grade index in
the temporary database, checks integrity and nonempty grade coverage, then
atomically publishes it. Failure before publication preserves the live database.
`build_views.py` reuses the same implementation. Pooled database connections
detect a replaced file and reopen, including discarding connections that were
in use during the swap, so an application restart is not needed nightly.

Validation includes grade precedence despite conflicting intensity, grades 1-4,
ungraded and unknown cases, combined filters, all relevant tool outputs, invalid
filter arguments, failed imports preserving live data, and pooled reads after
an atomic replacement. Run:

```sh
.venv/bin/python -m unittest test_dance_difficulty test_name_search test_search_cribs_rscds -q
```

## Deployment record

Deployed 19 September 2026, 11:32 UTC, including a successful live refresh.
Rollback code and database: `/home/ubuntu/dance-teacher-release-backups/rscds-grades-20260919T113225Z/`.
Only the difficulty/import/agent modules were deployed; existing local settings,
web UI and programme-planner changes remained separate at the time. These files
were copied by hand and committed later, in `e79a710` (4 October 2026).

Verified 41 local tests (including the existing programme-planner regressions)
and 25 tests on the VPS. Browser checks on the public site confirmed:

- Chat: Crom Allt and The Reel of the 51st Division return grade 1; Mairi's
  Wedding returns grade 2.
- A beginner-reels request selects actual RSCDS-published grade-1 dances.
- Fisherman's Reel remains ungraded, with a clearly identified legacy estimate.
- Lilibet's Strathspey retains the source's grade-4 wording.
- Lesson mode distinguishes Crom Allt's published grade from Fisherman's Reel's
  estimate and considers the formations in its recommendation.

The browser check initially revealed an invented "four ghillies" label and
ambiguous attribution of the fallback. Shared agent guidance now explicitly
forbids that label and names the fallback as ChatSCD's estimate from SCDDB
intensity. The final browser checks used that guidance.
