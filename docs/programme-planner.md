# Programme planner

Live at **https://chatscd.com/programmes** (deployed 4 October 2026, `main` at `1f23d16`). The chat sidebar also links to it.

## Local preview

Open **http://127.0.0.1:8015/programmes**. To start it from the repository root:

```sh
./start_local_planner.sh
```

The launcher binds only to `127.0.0.1`. It uses separate chat and settings databases in `data/local-preview/`; production defaults remain unchanged. `CHAT_SCD_LOCAL_PORT` can override 8015. The existing local dance catalogue is opened read-only, and programme generation/checking makes no model or external network requests.

## Try it

The page is one column: a setup sentence, the programme, then a short review.

1. Choose the event ("A social dance with 16 dances") and press **Generate**. The line underneath summarises the other settings; **More options** opens them (J/R/S counts, interval, difficulty balance, flow rules, dance pool, RSCDS target, figure rules). Changing the length re-splits J/R/S automatically.
2. Lock dances with the padlock and press **Regenerate**: locked dances stay in place. Intervals and extras are retained.
3. Click a dance to see its details, any problems with it, and Up/Down/Replace/Remove. Replace searches inside the row. Rows with problems carry a red (fix) or amber (consider) dot.
4. Paste an existing list from the **•••** menu (one dance per line; `Interval` and `Extras` headings). Unmatched names show "Did you mean" choices in the row.
5. The **Review** card lists problems with **Show** links to the rows. **Programme summary** holds the stats, difficulty target vs actual, figure variety and data-coverage notes.
6. The **•••** menu also has saved copies (save, reopen, download/open a file), export as text, print and start empty. **Undo** sits beside it.
7. Difficulty balances are easier evening (75/25/0%), mixed social (40/45/15%) or annual ball (20/45/35%) across one/two/three ghillies. These are adjustable ChatSCD starting points, not official RSCDS recommendations. Choose **Custom** to edit the percentages (including the separate expert/unusual category), or **No preference**. The event style sets the matching balance.

Drafts are saved in **this browser and origin**, not an account or the server. `localhost` and `127.0.0.1`, or different browsers, have different draft stores. Download a draft file to transfer it. Undo retains the last 30 edits during the current page session. Saved copies retain the latest 50 snapshots.

## Rule behaviour

- No duplicate main dances and no identical J/R/S neighbours are required by default. A beginners/mixed-social profile changes the latter to a warning. Changing event style also sets the corresponding suggested difficulty mix, which can then be customised independently.
- Generation fills pure J/R/S slots. The checker retains medleys/other/unknown rhythm labels and marks the gap in coverage. A locked mixed-rhythm dance blocks generation with an explanation.
- Intervals, extras and unknown dances interrupt adjacency. Figure counts apply to main dances across the whole programme; figure spacing restarts at a boundary.
- A figure is counted once per containing dance, not by occurrences/bars inside the dance. Exact IDs and broad families are separate choices. Broad families are catalogue groupings, not a finished pedagogical taxonomy.
- Required figure rules need verified tags on every main dance. Unknown/unverified coverage is reported, not assumed to pass. A hard figure rule narrows generation to dances with verified tags.
- RSCDS share uses “has at least one linked RSCDS publication,” among dances whose publication status is known. The target has a ±15 percentage-point tolerance and is a preference, not a hard membership filter.
- Fast-run length, opening/closing rhythm and RSCDS mix are preferences. Remaining warnings are shown on generated drafts. No “programme quality score” is invented.
- The default candidate pool comes from the 179-event research sample; the wider catalogue is selectable. Frequency is neither a popularity survey nor audience familiarity. Manual search covers the full catalogue.
- Explicit rhythm counts and locks are never relaxed. A bounded search may fail to find a solution for tight figure constraints; its failure message distinguishes this from a proved rhythm-count conflict.
- Difficulty uses the same published `rscds_grade` and labels as chat, via `dance_difficulty.py`. Grade 4 retains the expert/unusual description, never a four-ghillie label. Missing/invalid grades stay ungraded; no `intensity` value is relabelled as difficulty. Publication membership is independent.
- Difficulty is a soft programme-wide balance, not a per-dance ceiling. Percentages sum to 100 and are rounded to whole dances by largest remainders. The checker flags a difference requiring more than one dance to change grade. Locked harder dances remain and are counted before filling free slots; rhythm/figure requirements still take precedence. Sparse pools may leave a reported imbalance rather than failing merely on the target mix.
- Mixes are calculated over graded main dances only. Ungraded dances are excluded when balancing unless explicitly allowed; when allowed they are outside the percentage denominator and remain unassessed. An entirely ungraded programme cannot pass a balance assessment. Extras retain labels for manual review. RSCDS publication preference is separate.
- New browser drafts start with the mixed-social balance. Old drafts without a difficulty choice retain no preference. Old active thresholds migrate to the event-style balance with an on-screen notice; no hidden ceiling is retained. Mix settings survive saving, downloading, reopening and undo.
- Audience familiarity, musical style and actual running time are unassessed.

## Implementation

`programme_planner.py` provides a cached read-only catalogue, conservative text matching, deterministic checking, rhythm feasibility search and bounded draft generation. `programme_routes.py` exposes the page and four routes under `/api/programmes/`: `catalogue`, `import`, `check`, `generate`. Request sizes/counts have bounds; names are rendered as escaped text. The planner uses local JS/CSS without a new runtime frontend dependency.

`assets/programme-sample.json` is a small exported occurrence table, with source/date information. Runtime operation does not depend on research scripts or their raw downloads. Restart the app after replacing the catalogue or occurrence file to refresh its in-memory cache.

## Validation

Planner tests cover exact counts, repeatable seeds, locks/extras, impossible rhythm arrangements, unresolved identities, duplicates, intervals, exact/family figure checks, verified coverage, multiple lengths, request bounds, import round-trips and HTTP generation/checking.

```sh
CHAT_DB_PATH=data/local-preview/tests-chat.db \
SETTINGS_DB_PATH=data/local-preview/tests-settings.db \
uv run --no-sync --with pytest python -m pytest \
  test_programme_planner.py test_feedback.py test_usage_quota.py \
  test_model_configuration.py -q
```

Browser checks covered generating, locking/regenerating, refresh persistence, saved-copy reopening, import with duplicate/unknown/adjacent-jig warnings, search/replace, undo, required figure exclusion and conflicting numeric inputs preserving the draft. Phone and desktop layouts were visually inspected.

Difficulty balance update (19 September 2026): 37 planner and shared difficulty tests pass with
`.venv/bin/python -m unittest test_programme_planner test_dance_difficulty -q`.
Coverage includes the three balances across both pools and multiple seeds,
rounding, unknown coverage, harder and ungraded locks, insufficient graded pools,
combined figure rules, old-threshold migration and API validation.
Browser checks confirmed an easier 12/4/0 programme and an annual-ball 3/7/6
programme, event-style preset selection, editable proportions, target/actual
counts, invalid totals preserving the draft, ungraded coverage, custom settings
surviving reload, and Undo restoring the original programme.

Two existing legacy scripts, `test_chat_sessions.py` and `test_chat_persistence.py`, fail respectively on unowned-session listing and unauthorized clearing. Both failures were reproduced using `HEAD:web_app.py` with disposable databases. They predate this feature and were not changed as part of it. Do not run those scripts against a real chat database: they delete their configured database at startup.

## Deployment record

Deployed 4 October 2026 with the standard flow (push `main`, `git pull` on the VPS, `sudo systemctl restart chatscd`). The release also committed the difficulty work and `gpt-6-luna` default that were already running on the VPS from hand-copied files, so the VPS checkout is now clean on `main`. Backup of those hand-copied files: `/home/ubuntu/dance-teacher-release-backups/planner-20261004T113259Z/`. No database changes; the planner reads the SCDDB catalogue read-only and makes no model requests. Checked on the public site: the page and catalogue search return 200, and a programme generates without console errors.
