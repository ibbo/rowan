# ChatSCD — data sources, UX roadmap, and sustainability

*Written 2026-07-05. Companion to the code changes made the same day (lesson
planner double-run fix, planner conversation memory, history rehydration,
cheap-model prompt checker, markdown sanitisation).*

## 1. Additional online sources worth integrating

Already integrated: SCDDB dump (CC BY 3.0 DE), live SCDDB lists API, RSCDS
Manual, RSCDS Teaching Guide v2.4, SCDDB video/recording links.

| Source | What it adds | Licence / terms | Integration idea |
|---|---|---|---|
| [MiniCrib](https://minicrib.org.uk/) | 4,600+ concise cribs in the format most teachers actually print for socials | Free to use provided the MINICRIB footnote/credit is kept ([about](https://www.minicrib.org.uk/about.html)) | Offer "MiniCrib style" as an alternative crib format in lesson plans; downloadable as .docx/PDF database, so it can be parsed into a keyed JSON like the manual |
| [Keith Rose's crib diagrams](https://www.scottish-country-dancing-dictionary.com/crib-diagrams.html) | Pilling-style diagrams for 4,600+ dances — the single most requested visual aid | Free with a credit to Keith Rose (Bedford Scottish Dance Group) | Link (don't inline) the diagram page per dance next to the Strathspey link; SCDDB records which dances have diagrams |
| [Scottish Country Dancing Dictionary](https://www.scottish-country-dancing-dictionary.com/) | Video index (3,100+ dances), dance-term dictionary, instructional videos | **All rights reserved** ([copyright](https://www.scottish-country-dancing-dictionary.com/copyright.html)) — link out only, or write to the maintainers for permission | Add as a "further reading" link per dance/term |
| [RSCDS Steps & Techniques pages](https://rscds.org/learn/steps-techniques) and [YouTube channel](https://www.youtube.com/channel/UC2mNV40nY6C2akB5Z8yE27w) | Official step tutorial videos (Steps & Techniques playlist), simple-dances guides, [beginner teaching framework](https://rscds.org/learn/teaching-scottish-country-dance/introducing-scd-beginners) | Public web/YouTube; link out | Curate a small JSON mapping step/formation → official video URL, and have `search_manual`/`get_teaching_guidance` answers append "watch: …". Zero LLM cost, big helpfulness win |
| [Dance Scottish At Home](https://rscds.org/get-involved/dance-scottish-home) | 64 recorded online classes by RSCDS teachers (technique, steps, warm-ups) | Public | Same curated-links approach, keyed by topic |
| [my-next.strathspey.org](https://my-next.strathspey.org/dd/) | The new SCDDB front end | — | Watch for API/schema changes when it replaces the current site |

The highest value-per-hour item is the **curated step/formation → video map**:
it needs no licence negotiation, improves teaching answers materially, and
costs nothing per query.

## 2. Accuracy / helpfulness roadmap

- **Token streaming.** `/api/query` currently sends the answer only when
  fully complete; the progress box masks this but long answers still feel
  slow. LangGraph's `stream_mode="messages"` can stream tokens; the front end
  needs a `token` SSE event that appends into the assistant bubble.
- **Trim seeded history.** Conversation memory now survives restarts, but a
  long session sends its whole history every turn. Cap at the last ~20
  messages when seeding/summarising to bound cost.
- **Port the track-2 no-improvise guardrails** (still sitting in the
  rowan-accuracy-track2 worktree) and get the live end-to-end track-3 eval
  running as a deploy gate.
- **Prefer structured formation search.** `search_cribs` FTS matches crib
  prose; `v_dance_has_token` is authoritative. Teaching the planner to
  resolve a formation via `list_formations` → token → `find_dances` first,
  with FTS as fallback, would cut false positives from prose mentions.

## 3. UX roadmap (beyond today's fixes)

- Streamed tokens (above) — the single biggest perceived-speed win.
- A compact **dance card** component (name, kind, bars, set shape, links to
  Strathspey / video / diagram) instead of prose lists.
- "Copy crib" and "share lesson plan" (read-only link) actions.
- A static, searchable **formation & step library** rendered from the manual
  KB — no LLM involved, instant, and it doubles as SEO landing pages.
- Mobile: the planner's three-pane layout needs a stacked mode.

## 4. Covering costs without commercialising

Cost profile: VPS is fixed and small; the risk is LLM spend, which scales
with (a) real users, (b) scrapers/abuse. Defaults are already cheap
(gpt-5.4-mini, and the prompt checker now always uses the cheap model).

Recommended, in order:

1. **Daily message quota, generous but hard.** E.g. 20 messages/day
   anonymous (keyed on browser_id + IP), 50/day signed in. A friendly
   "you've reached today's limit — sign in / add your own key / come back
   tomorrow" message. This alone bounds worst-case spend; everything else is
   optimisation. Store counts in the existing SQLite DB.
2. **Surface the BYO-key feature.** Per-user API keys are already built
   (encrypted in user_settings). Make it a visible option on the quota
   message: "power users: add your own OpenAI/Google key in Settings for
   unlimited use." Heavy users then cost you nothing.
3. **Provider budget alerts + admin usage panel.** Set hard monthly budgets
   in the OpenAI/Google consoles; log per-session token usage and show
   totals in `/admin` so you can see cost per week at a glance.
4. **Answer repeatable questions without the LLM.** Formation/step
   explanations are the most repeated queries and the manual KB lookup is
   already deterministic — the static library page (§3) diverts those to
   zero-cost pages and brings search traffic.
5. **Donations, not subscriptions.** A quiet Ko-fi/GitHub Sponsors link in
   the footer ("ChatSCD is free for the SCD community — donations cover the
   AI costs") is normal for community sites. Consider asking your RSCDS
   branch, TAC, or local groups whether they'd sponsor a month's costs in
   exchange for a "supported by" credit; teacher-training candidates (Units
   2/3/5) are the natural champions since lesson planning is the killer
   feature.
6. **Prompt caching.** The system prompts are long and identical per
   request; enable provider-side prompt caching where available to cut input
   token cost substantially.

What to avoid: ads (kills trust in a small community), and unbounded free
access with no sign-in (one scraper can spend a month's budget in a night).

## Sources

- https://minicrib.org.uk/ (and /about.html, /publish.html)
- https://www.scottish-country-dancing-dictionary.com/ (copyright.html, crib-diagrams.html)
- https://my.strathspey.org/dd/ and https://my-next.strathspey.org/dd/
- https://rscds.org/learn/steps-techniques and https://rscds.org/get-involved/dance-scottish-home
- https://www.youtube.com/channel/UC2mNV40nY6C2akB5Z8yE27w
