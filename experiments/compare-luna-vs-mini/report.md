# Model comparison — 2026-09-01 23:36

| Model | Passed | Errors | Avg latency | Avg tool calls | Input tokens | Output tokens | of which reasoning |
|---|---|---|---|---|---|---|---|
| gpt-5.4-mini | 12/19 | 0 | 5.1s | 2.7 | 277,844 | 6,927 | 0 |
| gpt-5.6-luna | 17/19 | 0 | 8.7s | 4.4 | 389,128 | 9,139 | 0 |
| gpt-5.6-luna+reasoning | 19/19 | 0 | 11.8s | 3.7 | 355,453 | 12,827 | 2,656 |

## Per-prompt results

| Prompt | gpt-5.4-mini | gpt-5.6-luna | gpt-5.6-luna+reasoning |
|---|---|---|---|
| formation-allemande-2c | ✅ 4.4s / 2 tools | ✅ 4.2s / 2 tools | ✅ 5.0s / 1 tools |
| formation-allemande-turn | ✅ 3.2s / 1 tools | ✅ 5.4s / 1 tools | ✅ 4.0s / 1 tools |
| bars-skip-change-stephen | ✅ 7.4s / 5 tools | ✅ 7.3s / 4 tools | ✅ 5.4s / 2 tools |
| bars-pas-de-basque-discounted-suit | ❌ 3.3s / 1 tools | ✅ 6.0s / 3 tools | ✅ 8.5s / 3 tools |
| bars-travelling-step-kirkcudbright | ❌ 4.5s / 2 tools | ✅ 11.6s / 5 tools | ✅ 6.4s / 2 tools |
| bars-setting-step-circle-strathspey | ❌ 3.1s / 1 tools | ✅ 7.3s / 3 tools | ✅ 9.9s / 2 tools |
| bars-mairis-wedding-pass-lsh | ❌ 3.2s / 1 tools | ✅ 8.4s / 5 tools | ✅ 6.5s / 2 tools |
| bars-reel51-cast-two-places | ❌ 4.6s / 2 tools | ✅ 5.4s / 3 tools | ✅ 12.1s / 4 tools |
| bars-montgomeries-cross-lh | ✅ 3.0s / 1 tools | ✅ 5.6s / 3 tools | ✅ 6.1s / 2 tools |
| bars-diplomat-setting-steps | ❌ 4.1s / 2 tools | ❌ 4.0s / 2 tools | ✅ 12.5s / 5 tools |
| manual-skip-change-quote | ✅ 3.9s / 2 tools | ✅ 5.9s / 2 tools | ✅ 9.2s / 4 tools |
| manual-absent-term-abstain | ✅ 5.8s / 2 tools | ✅ 5.3s / 3 tools | ✅ 15.2s / 6 tools |
| teaching-skip-change-guidance | ✅ 5.8s / 2 tools | ✅ 7.6s / 2 tools | ✅ 13.6s / 3 tools |
| search-rscds-strathspey-poussette | ✅ 7.4s / 4 tools | ✅ 7.0s / 5 tools | ✅ 6.4s / 1 tools |
| teach-pas-de-basque | ✅ 5.3s / 2 tools | ✅ 8.5s / 2 tools | ✅ 13.9s / 3 tools |
| formation-reel3-vs-reel4 | ✅ 7.2s / 5 tools | ✅ 10.2s / 4 tools | ✅ 21.9s / 5 tools |
| crib-lookup-knot | ❌ 3.6s / 2 tools | ❌ 8.0s / 2 tools | ✅ 10.7s / 4 tools |
| offtopic-reject | ✅ 0.7s / 0 tools | ✅ 0.7s / 0 tools | ✅ 0.7s / 0 tools |
| planner-rscds-tournee | ✅ 17.2s / 14 tools | ✅ 47.0s / 32 tools | ✅ 56.4s / 21 tools |

## Answers side by side

### formation-allemande-2c

**Prompt:** Are 'allemande for 2 couples' and 'allemande turn' the same formation? Name the exact formation/token to use for a standard 2-couple allemande.

#### gpt-5.4-mini — PASS (4.4s, 2 tool calls, 10312+194 tokens)
- missing: ['2 couple allemande']; forbidden: []
- tools: search_manual, list_formations

No — they are not the same.

- **Allemande for 2 couples** is the standard 2-couple formation.
- **Allemande turn** refers to the turning action/hold, not the full 2-couple formation.

For a standard 2-couple allemande, use:

- **Formation name:** Allemande for 2 couples
- **Token:** `ALLMND;2C;`

If you want, I can also tell you the difference between **allemande turn** and the full **allemande for 2 couples** in dance-crib terms.

#### gpt-5.6-luna — PASS (4.2s, 2 tool calls, 10312+209 tokens)
- missing: ['2-couple allemande', '2 couple allemande']; forbidden: []
- tools: list_formations, search_manual

No. They are distinct database concepts:

- **Allemande Turn (to R or L)** — token `ALL_RL`; this is a generic turn/figure and does not specify a two-couple allemande.
- **Allemande for 2 couples** — token **`ALLMND;2C;`**; this is the exact formation to use for a standard two-couple allemande.

The RSCDS Manual identifies the general formation as **“6.2 Allemande”**, but for database searches or tagging a standard two-couple version, use **Allemande for 2 couples — `ALLMND;2C;`**.

#### gpt-5.6-luna+reasoning — PASS (5.0s, 1 tool calls, 9691+174 tokens)
- missing: ['2-couple allemande', '2 couple allemande']; forbidden: []
- tools: list_formations

No. They are distinct database formations:

- **Allemande Turn (to R or L)** — token: `ALL_RL`  
  A turn in allemande hold, generally involving a single couple or specified dancers.

- **Allemande for 2 couples** — token: **`ALLMND;2C;`**  
  This is the exact formation/token to use for a **standard two-couple allemande**.

Do not use `ALL_RL` when searching for the standard 2-couple figure.

### formation-allemande-turn

**Prompt:** Which formation entry matches an allemande turn to right or left, not a two-couple allemande?

#### gpt-5.4-mini — PASS (3.2s, 1 tool calls, 10105+117 tokens)
- tools: list_formations

The formation entry you want is **[Allemande Turn (to R or L)](https://my.strathspey.org/dd/dance/302/)**.

- **Formation name:** Allemande Turn (to R or L)
- **Token:** `ALL_RL`

This is the general turning allemande, distinct from **Allemande for 2 couples** (`ALLMND;2C;`).

#### gpt-5.6-luna — PASS (5.4s, 1 tool calls, 10105+78 tokens)
- tools: list_formations

The matching formation entry is:

**Allemande Turn (to R or L)** — token: `ALL_RL`

This is distinct from **Allemande for 2 couples** (`ALLMND;2C;`).

#### gpt-5.6-luna+reasoning — PASS (4.0s, 1 tool calls, 9642+99 tokens)
- tools: list_formations

The matching formation entry is:

**Allemande Turn (to R or L)** — token: `ALL_RL`

This is distinct from **Allemande for 2 couples** — token: `ALLMND;2C;`.

### bars-skip-change-stephen

**Prompt:** In Bill's Friend, Stephen, what step is explicitly named on bars 11-16?

#### gpt-5.4-mini — PASS (7.4s, 5 tool calls, 30391+234 tokens)
- tools: get_dance_detail, search_cribs, search_cribs, find_dances, get_dance_detail

On bars 11–16, the crib explicitly names **skip change** — in both phrases:

- **11–12:** “using **skio/skip change**”
- **15–16:** “using **skip change**”

So the step named there is **skip change of step**.

Dance link: [Bill's Friend, Stephen](https://my.strathspey.org/dd/dance/23334/)

#### gpt-5.6-luna — PASS (7.3s, 4 tool calls, 25260+183 tokens)
- tools: search_cribs, search_cribs, find_dances, get_dance_detail

On bars **11–16**, the explicitly named step is the **skip change of step**:

- Bars 11–12: “using skio [skip] change”
- Bars 15–16: “using skip change”

[Bill’s Friend, Stephen](https://my.strathspey.org/dd/dance/23334/) is a reel.

#### gpt-5.6-luna+reasoning — PASS (5.4s, 2 tool calls, 14591+174 tokens)
- tools: find_dances, get_dance_detail

The step explicitly named on bars **11–16** is the **skip change of step**. It appears on both bars 11–12 and 15–16.

### bars-pas-de-basque-discounted-suit

**Prompt:** In Discounted Suit, The, what step is explicitly named on bars 17-18?

#### gpt-5.4-mini — FAIL (3.3s, 1 tool calls, 9659+109 tokens)
- missing: ['pas de basque']; forbidden: []
- tools: get_dance_detail

I couldn’t retrieve **The Discounted Suit** from the dance database with the information available here, so I can’t safely say what step is named on bars 17–18.

If you want, send me either:
- the **exact dance ID**, or
- the **publication/book** it’s from,

and I’ll look it up.

If you meant a different dance title, please paste it exactly as printed.

#### gpt-5.6-luna — PASS (6.0s, 3 tool calls, 20138+130 tokens)
- tools: find_dances, find_dances, get_dance_detail

The step explicitly named on bars 17–18 is **pas de basque**.

[The Discounted Suit](https://my.strathspey.org/dd/dance/16763/) is a reel.

#### gpt-5.6-luna+reasoning — PASS (8.5s, 3 tool calls, 19528+271 tokens)
- tools: find_dances, find_dances, get_dance_detail

The step explicitly named on bars 17–18 is **pas de basque**.  

[The Discounted Suit](https://my.strathspey.org/dd/dance/16763/) is a reel.

### bars-travelling-step-kirkcudbright

**Prompt:** In Dancing in Kirkcudbright, what step is named for the pivot on bar 4?

#### gpt-5.4-mini — FAIL (4.5s, 2 tool calls, 14644+139 tokens)
- missing: ['travelling step']; forbidden: ['skip change']
- tools: get_dance_detail, search_manual

I’m sorry, but I can’t identify that step from the RSCDS manual or database as asked.

If you mean a specific formation or step in **Dancing in Kirkcudbright**, please give me the exact term or the manual section number — for example **“skip change of step”** or **“5.4.1”** — and I can look it up precisely.

#### gpt-5.6-luna — PASS (11.6s, 5 tool calls, 32427+206 tokens)
- tools: search_cribs, find_dances, get_dance_detail, search_manual, get_teaching_guidance

The step is **strathspey travelling step**—specifically, the crib says **“pivot L (travelling step L)”** on bar 4.

[Dancing in Kirkcudbright](https://my.strathspey.org/dd/dance/16845/) is a 32-bar Strathspey.

#### gpt-5.6-luna+reasoning — PASS (6.4s, 2 tool calls, 14709+209 tokens)
- tools: find_dances, get_dance_detail

In *Dancing in Kirkcudbright*, the step named for the pivot on bar 4 is the **left travelling step**: the first man and second man “pivot L (travelling step L)” to finish behind their partners.

[ Dancing in Kirkcudbright](https://my.strathspey.org/dd/dance/16845/) is a 32-bar Strathspey.

### bars-setting-step-circle-strathspey

**Prompt:** Which step is named in Circle Strathspey bars 1-8?

#### gpt-5.4-mini — FAIL (3.1s, 1 tool calls, 9726+137 tokens)
- missing: ['setting step', 'glasgow highlanders setting step']; forbidden: ['travelling step']
- tools: search_manual

I couldn’t find a matching entry in the RSCDS manual for that phrasing.

If you mean the step used in the opening bars of **Circle Strathspey**, please send the **exact formation or step name** you want checked, or the **manual section number** if you have one. For example: **“strathspey travelling step”**, **“strathspey setting”**, or a section like **“5.4.1”**.

#### gpt-5.6-luna — PASS (7.3s, 3 tool calls, 20059+144 tokens)
- tools: search_cribs, find_dances, get_dance_detail

In **[Circle Strathspey](https://my.strathspey.org/dd/dance/16390/)**, bars 1–8 name the **Glasgow Highlanders setting step**:

> “All set facing the centre using Glasgow Highlanders setting step.”

#### gpt-5.6-luna+reasoning — PASS (9.9s, 2 tool calls, 14576+192 tokens)
- tools: find_dances, get_dance_detail

In **[Circle Strathspey](https://my.strathspey.org/dd/dance/16390/)**, bars 1–8 name the **Glasgow Highlanders setting step**, danced by all facing the centre.

### bars-mairis-wedding-pass-lsh

**Prompt:** In Mairi's Wedding bars 9-24, does first couple pass left shoulder or right shoulder?

#### gpt-5.4-mini — FAIL (3.2s, 1 tool calls, 10550+168 tokens)
- missing: ['left shoulder', 'lsh']; forbidden: ['right shoulder']
- tools: get_dance_detail

In **Mairi’s Wedding** bars **9–24**, the first couple **do not pass shoulders** in a reel-of-3 style movement. The crib for the dance in the database shows:

- **9–16:** first and second dancers on the women's/men's side set and turn right hand, then repeat
- **17–24:** first couple **cross RH, cast off**, then half figure of eight up round 2nd couple

So for the section you’re asking about, the first couple **cross right hand**, rather than passing left or right shoulder.

If you want, I can also lay out the full bars of **Mairi’s Wedding** step by step.

#### gpt-5.6-luna — PASS (8.4s, 5 tool calls, 32383+238 tokens)
- tools: get_dance_detail, search_cribs, find_dances, find_dances, get_dance_detail

In **[Mairi’s Wedding](https://my.strathspey.org/dd/dance/4102/)**, bars **9–24**: the first couple pass **left shoulder** during each half-reel of four.

The crib explicitly says: **“½ Reel 4 with 1st corners (pass P Lsh)”**, then repeat with the second corners. A right-shoulder version is sometimes danced, but the published Cosh instruction specifies **left shoulder**.

#### gpt-5.6-luna+reasoning — PASS (6.5s, 2 tool calls, 15238+237 tokens)
- missing: ['lsh']; forbidden: []
- tools: find_dances, get_dance_detail

In [Mairi’s Wedding](https://my.strathspey.org/dd/dance/4102/), bars **9–24**, first couple pass **left shoulder**:

- Bars 9–16: half-reel of four with first corners, passing left shoulder.
- Bars 17–24: repeat with second corners.

The crib notes that a right-shoulder pass is also danced by some groups, sometimes called “Mairi’s Divorce,” but the explicitly specified version is **left shoulder**.

### bars-reel51-cast-two-places

**Prompt:** In The Reel of the 51st Division bars 1-8, do first couple cast off one place or two places?

#### gpt-5.4-mini — FAIL (4.6s, 2 tool calls, 15318+211 tokens)
- missing: ['two places', '2 places']; forbidden: ['one place']
- tools: search_manual, get_dance_detail

In **The Reel of the 51st Division**, the **first couple cast off one place**, not two.

The RSCDS manual distinguishes:
- **Cast off one place (2 steps / 2 bars)**: from first place into second place
- **Cast off one place (4 steps / 4 bars)**: still only one place, but danced over 4 steps

So for bars 1–8, the action is a **cast off one place**. If you want, I can also check the exact crib for *The Reel of the 51st Division* to confirm the full first 8 bars.

#### gpt-5.6-luna — PASS (5.4s, 3 tool calls, 20740+154 tokens)
- missing: ['2 places']; forbidden: []
- tools: get_dance_detail, find_dances, get_dance_detail

The first couple **cast off two places** in bars 1–4, with the second couple moving up. They then **lead up to first-couple corners** in bars 5–8.

[The Reel of the 51st Division](https://my.strathspey.org/dd/dance/5525/) is a 32-bar reel.

#### gpt-5.6-luna+reasoning — PASS (12.1s, 4 tool calls, 25642+513 tokens)
- missing: ['2 places']; forbidden: []
- tools: find_dances, search_cribs, find_dances, get_dance_detail

In bars 1–8, the first couple **cast off two places**, with the second couple stepping up. They then lead up to the first corners.

[The Reel of the 51st Division](https://my.strathspey.org/dd/dance/5525/) — RSCDS Book 13, dance 10.

### bars-montgomeries-cross-lh

**Prompt:** After first couple cross right hand in Montgomeries' Rant, The bars 1-8, what is the next explicitly stated action: cross left hand or start the reel of three?

#### gpt-5.4-mini — PASS (3.0s, 1 tool calls, 10588+162 tokens)
- missing: ['cross lh']; forbidden: []
- tools: get_dance_detail

In the crib for **Montgomeries' Rant, The**, after **“1c cross RH”** in bars 17–24, the next explicitly stated action is:

**“cast off (2c up)”**

So it is **not** “cross left hand,” and it is **not** “start the reel of three” at that point.

Relevant dance link: [The Duke of Atholl's Reel](https://my.strathspey.org/dd/dance/1786/)

If you want, I can also pull the exact crib for **Montgomeries' Rant** and quote the bars 1–8 section verbatim.

#### gpt-5.6-luna — PASS (5.6s, 3 tool calls, 20916+194 tokens)
- tools: get_dance_detail, find_dances, get_dance_detail

After the first couple’s **cross right hand** in bars 1–2, the next explicitly stated action is **cast off**, followed by **cross left hand**—not the reel of three.

The reel of three starts at **bar 9**:

> “1c cross RH | cast off (2c up) ; cross LH | cast L …”  
> “9–: … Reels3 across”

[Montgomeries’ Rant, The](https://my.strathspey.org/dd/dance/4641/)

#### gpt-5.6-luna+reasoning — PASS (6.1s, 2 tool calls, 14984+226 tokens)
- tools: find_dances, get_dance_detail

The next explicitly stated action is **cross left hand**, not start the reel of three.

For bars 1–8, the crib says:

> “1c cross RH | cast off (2c up) ; **cross LH** | cast L (W up, M down)”

The reel of three starts at **bar 9**. [Montgomeries' Rant, The](https://my.strathspey.org/dd/dance/4641/)

### bars-diplomat-setting-steps

**Prompt:** In The Diplomat bars 17-24, what kind of steps does first couple use when they pass each other by the left shoulder?

#### gpt-5.4-mini — FAIL (4.1s, 2 tool calls, 14394+155 tokens)
- missing: ['setting step', 'two setting steps']; forbidden: []
- tools: get_dance_detail, find_dances

I couldn’t locate **The Diplomat** in the database from the name alone, so I can’t verify bars 17–24 from the crib yet.

If you can share one of these, I can answer precisely:
- the **devisor**,
- the **publication/book** it’s from,
- or a screenshot/text of the **crib**.

If you want, I can also help by searching for the dance in RSCDS publications or by looking up the exact bars once identified.

#### gpt-5.6-luna — FAIL (4.0s, 2 tool calls, 14390+80 tokens)
- missing: ['setting step', 'two setting steps']; forbidden: []
- tools: get_dance_detail, search_cribs

In **The Diplomat**, bars 17–24, the first couple pass each other by the left shoulder using **skip-change-of-step**.

#### gpt-5.6-luna+reasoning — PASS (12.5s, 5 tool calls, 30346+465 tokens)
- tools: find_dances, search_cribs, find_dances, search_cribs, get_dance_detail

In bars 17–24 of [The Diplomat](https://my.strathspey.org/dd/dance/17880/), first couple pass each other by the left shoulder using **two setting steps**.

### manual-skip-change-quote

**Prompt:** Quote the exact RSCDS manual wording for how to teach skip change of step.

#### gpt-5.4-mini — PASS (3.9s, 2 tool calls, 10768+282 tokens)
- tools: search_manual, get_teaching_guidance

Here is the exact RSCDS manual wording for **skip change of step**:

> **5.4.1 Skip change of step**  
> This step is used to travel. One skip change of step takes one bar of music.  
> 1. Hop on the left foot and, at the same time, fully extend the right leg forward.  
> 2. With the right leg fully extended in fourth in front of third position, step forward onto the right foot.  
> 3. Bring the left foot behind the right foot to third rear position.  
> 4. Step forward again with the right foot into fourth in front of third position.  
> Rhythmic words: Hop, step, close, step (or similar rhythmic variations).  
> The rhythm of jig time is particularly suitable for the practice of this step.  
> The character of the step is light and lively. It should give the feeling of flight and easy movement.

If you want, I can also quote the **“Points to observe”** section verbatim.

#### gpt-5.6-luna — PASS (5.9s, 2 tool calls, 10213+623 tokens)
- missing: ['hop, step, close, step']; forbidden: []
- tools: search_manual, get_teaching_guidance

The RSCDS manual’s exact wording for **Skip change of step** is:

> **5.4.1 Skip change of step**  
> This step is used to travel. One skip change of step takes one bar of music.  
>   
> 1. Hop on the left foot and, at the same time, fully extend the right leg forward.  
> 2. With the right leg fully extended in fourth in front of third position, step forward onto the right foot …

The manual search result truncates the remaining text. The accompanying RSCDS teaching guidance gives this teaching progression:

> **Main teaching points**  
> a) The hop.  
> b) The straight front leg and the reach forward.  
> c) The third position.  
>   
> **Sample lesson plan**  
> 1. Give name and purpose and cover numbers 2, 3 and 4 from the guidelines in section 4.  
>   
> 2. Rhythmic words – Hop Step Close Step  
> a) Walking words – “And Step Close Step” or “And Right Close Right”  
> b) While walking, bring in music, gradually increasing speed.  
> c) While music is playing introduce “On your toes”.  
> d) As speed increases introduce “Hop Step Close Step”.  
>   
> 3. Hop  
> a) Isolate the movement. Demonstrate the hop and have class copy 2 or 3 times with each foot. (Avoid using spring points as the toe of the front leg is not on the floor during the “Hop”).  
> b) Dance step concentrating on “Hop”.  
>   
> 4. Straight Front Leg  
> a) Show position and have class show also.  
> b) Show and practise the hop with fully extended front leg 3 or 4 times with each foot (keep front foot off floor).  
> c) Dance step concentrating on full extension on hop.  
>   
> 5. Reach  
> a) Link the three movements – Hop, Reach Forward, Close.  
> b) Have class practise with R and L foot 3 or 4 times.  
> c) Dance step concentrating on the “reach”.  
>   
> 6. Third Position  
> a) Practise – Step forward, close in 3rd – 3 or 4 times with the same foot and then with the other.  
> b) Repeat on toes.  
>   
> 7. Finally dance the complete PERFECT STEP! If necessary go on to teach skip change of step travelling backwards.

The manual reference is **section 5.4.1, page 74**.

#### gpt-5.6-luna+reasoning — PASS (9.2s, 4 tool calls, 15401+410 tokens)
- missing: ['hop, step, close, step']; forbidden: []
- tools: search_manual, get_teaching_guidance, search_manual, search_manual

The RSCDS Manual, §5.4.1, **“Skip change of step”** (p. 74), states:

> “This step is used to travel. One skip change of step takes one bar of music.”

It begins:

> “1. Hop on the left foot and, at the same time, fully extend the right leg forward.  
> 2. With the right leg fully extended in fourth in front of third position, step forward onto the right foot…”

The database excerpt available to me truncates the remaining wording, so I can’t responsibly present the rest as an exact quotation. The accompanying RSCDS teaching guidance identifies the main teaching points as **the hop, the straight front leg and reach forward, and third position**.

### manual-absent-term-abstain

**Prompt:** Quote the exact RSCDS manual wording for teaching the 'highland swing turn'.

#### gpt-5.4-mini — PASS (5.8s, 2 tool calls, 14876+220 tokens)
- missing: ['not in the manual', 'no section', 'cannot verify', "can't quote", 'cannot quote', 'could not find', "can't find", 'cannot find', 'does not appear', "doesn't appear", 'no manual entry', 'no entry', "couldn't locate", 'could not locate', "can't locate", 'cannot locate', 'did not return', "didn't return", 'unable to find', 'not a term', 'not an rscds term']; forbidden: []
- tools: search_manual, search_manual

I couldn’t find a manual entry for **“highland swing turn”** as an exact term.

The closest RSCDS manual match is the general **Turn** section:

> **6.39 Turn**  
> **6.39.1 Turn with the right or left hand (4 bars)**  
> Steps: 4 travelling steps  
> No. of bars: 4  
> Bars  
> Approach partner and, joining hands, start to turn.  
> Continue to turn.  
> Complete the turn, start to release hands and dance forward towards own side.  
> Dance forward out into sidelines an...

If you want, I can also help find the exact RSCDS wording for **Highland Schottische step** or **Glasgow Highlanders step**, which may be what you meant.

#### gpt-5.6-luna — PASS (5.3s, 3 tool calls, 14986+247 tokens)
- missing: ['not in the manual', 'no section', 'cannot verify', "can't quote", 'cannot quote', "couldn't find", 'could not find', 'cannot find', 'does not appear', "doesn't appear", 'no manual entry', 'no entry', "couldn't locate", 'could not locate', "can't locate", 'cannot locate', 'did not return', "didn't return", 'unable to find', 'not a term', 'not an rscds term']; forbidden: []
- tools: search_manual, get_teaching_guidance, search_manual

I can’t find an RSCDS manual section specifically titled **“Highland swing turn.”** The closest relevant entry is **Manual §6.39, “Turn” (p. 169)**:

> **6.39.1 Turn with the right or left hand (4 bars)**  
> **Steps:** 4 travelling steps  
> **No. of bars:** 4  
> “Approach partner and, joining hands, start to turn.  
> Continue to turn.  
> Complete the turn, start to release hands and dance forward towards own side.  
> Dance forward out into sidelines …”

The available manual result is truncated, and the RSCDS teaching guide has no separate entry for “Highland swing turn.”

#### gpt-5.6-luna+reasoning — PASS (15.2s, 6 tool calls, 36716+526 tokens)
- missing: ['not in the manual', 'no section', 'cannot verify', "can't quote", 'cannot quote', "couldn't find", 'could not find', "can't find", 'cannot find', "doesn't appear", 'no manual entry', 'no entry', "couldn't locate", 'could not locate', "can't locate", 'cannot locate', 'did not return', "didn't return", 'unable to find', 'not a term', 'not an rscds term']; forbidden: []
- tools: search_manual, search_manual, search_manual, search_manual, search_manual, search_manual

The RSCDS Manual does not appear to use the exact term **“Highland swing turn.”** The relevant wording is:

> **6.39.1 Turn with the right or left hand (4 bars)**  
> **Steps:** 4 travelling steps  
> **No. of bars:** 4  
>
> Approach partner and, joining hands, start to turn.  
> Continue to turn.  
> Complete the turn, start to release hands and dance forward towards own side.  
> Dance forward out into sidelines and curve into place.  
>
> **Example:** *Sally’s Fancy*, Book 27.6  
>
> **Note:** in some dances a one-and-a-half times turn is danced in 4 bars.

**RSCDS Manual, section 6.39.1, page 169.**

### teaching-skip-change-guidance

**Prompt:** How do I teach skip change of step to a beginner class?

#### gpt-5.4-mini — PASS (5.8s, 2 tool calls, 10760+595 tokens)
- tools: search_manual, get_teaching_guidance

Here’s a beginner-friendly way to teach **skip change of step**.

### 1) Start with the purpose
Use the step to **travel lightly and lively**. It takes **one bar of music** and the rhythmic words are:

**“Hop, step, close, step”**

The RSCDS manual says the character should feel like **flight and easy movement**.

### 2) Teach it in small parts
Use the RSCDS teaching progression:

- **The hop**
- **The straight front leg and reach forward**
- **Third position**

A good way in class is:

1. **Walk the rhythm first**
   - “And step close step” or “And right close right”
   - Then add music
   - Then change to “Hop step close step”

2. **Teach the hop alone**
   - Show a clear, positive hop
   - Keep it small; don’t let it become too high

3. **Teach the reaching leg**
   - Show the leading leg fully extended from the hip
   - Explain that the foot is not just placed down; it **reaches forward onto the new foot**

4. **Teach the close to third position**
   - Stress that the feet close in **third position**
   - Don’t let dancers leave a gap, close in first, or pass the feet

5. **Put it together**
   - “Hop, step, close, step”
   - Practice with one foot, then the other
   - Only then add music and travel

### 3) Common faults to watch for
From the RSCDS teaching guidance, the main faults are:

- lack of outward rotation from the hip
- incorrect third position
- lack of hop
- front leg kicking up on the hop
- lack of extension in the knee and foot
- coming down on a bent front knee
- pulling the leading foot in as it takes weight
- poor poise
- scraping

### 4) Teaching tips for beginners
- Keep the first demonstration simple and clear
- Don’t rush to full speed
- Use music slowly at first
- Encourage lightness, posture, and turnout
- Let dancers practise on both feet before using it in figures

### RSCDS source
**Skip change of step** — RSCDS Manual, section **5.4.1**, page **74**.  
Teaching guidance from the RSCDS teaching guide on **Skip Change Of Step**.

If you want, I can also give you a **5-minute beginner class plan** for teaching it.

#### gpt-5.6-luna — PASS (7.6s, 2 tool calls, 10205+619 tokens)
- missing: ['hop step close step', 'hop, step, close, step']; forbidden: []
- tools: search_manual, get_teaching_guidance

## Teaching skip-change of step to beginners

### 1. Explain the purpose and rhythm

The RSCDS Manual describes skip-change as a travelling step, with **one step taking one bar of music**.

Use the rhythm:

> **Hop – Step – Close – Step**

Initially, have the class walk the rhythm while saying:

> **“And step, close, step”**  
> or  
> **“And right, close, right.”**

Gradually introduce music and increase the speed. Encourage dancers to stay on their toes as they become more comfortable.

### 2. Teach the hop separately

Have the class practise the hop on each foot two or three times.

Emphasise that:

- The hop is light and controlled.
- The front foot is **off the floor** during the hop.
- The front leg is extended rather than kicked upward.

### 3. Add the extended front leg

On the hop, the opposite leg reaches forward with the knee and foot extended. Practise this slowly, without worrying about travelling at first.

The main points are:

- A straight front leg.
- A clear reach forward.
- The leg remains low and controlled.

### 4. Link hop, reach and close

Combine the movements:

> **Hop – reach forward – close**

Practise with both the right and left foot leading. Keep the movement small enough that dancers can maintain balance and poise.

### 5. Introduce third position

Practise separately:

1. Step forward.
2. Close the other foot neatly into third position.
3. Repeat with the other foot.

Then repeat the exercise on the toes. Avoid allowing dancers to:

- Leave a gap between the feet.
- Close in first position.
- Pass the feet.

### 6. Put the complete step together

Once the components are secure, dance the full step to music:

> **Hop – Step – Close – Step**

Start slowly, perhaps travelling only a short distance. Increase the tempo only when the class can retain the hop, extension and neat third position.

## Faults to watch for

The RSCDS teaching guidance identifies these common faults:

- Lack of outward rotation from the hip.
- Incorrect third position.
- Lack of hop.
- Front leg kicking up on the hop.
- Insufficient extension of the knee and foot.
- Coming down on a bent front knee.
- Pulling in the leading foot as it takes weight.
- Poor poise.
- Scraping the feet.

A useful teaching sequence is to focus on **one point at a time**—first the hop, then the straight front leg, then the reach, and finally third position—before asking beginners to perform the complete step.

#### gpt-5.6-luna+reasoning — PASS (13.6s, 3 tool calls, 15669+1003 tokens)
- missing: ['hop step close step']; forbidden: []
- tools: search_manual, get_teaching_guidance, search_manual

## Teaching skip change of step to beginners

### 1. Explain the step

According to the **RSCDS Manual, section 5.4.1, p. 74**:

> “This step is used to travel. One skip change of step takes one bar of music.”

> “Hop on the left foot and, at the same time, fully extend the right leg forward.”  
> “With the right leg fully extended in fourth in front of third position, step forward onto the right foot.”  
> “Bring the left foot behind the right foot to third rear position.”  
> “Step forward again with the right foot into fourth in front of third position.”

Use the rhythm:

> “Hop, step, close, step”

The manual describes the character as:

> “light and lively”  
> “the feeling of flight and easy movement.”

### 2. Teach it in stages

The RSCDS teaching guidance recommends focusing on one element at a time:

1. **Introduce the rhythm**
   - Begin with walking: “And step, close, step” or “And right, close, right.”
   - Gradually increase the speed.
   - Add the spoken rhythm: **“Hop, step, close, step.”**

2. **Isolate the hop**
   - Demonstrate the hop.
   - Let the class copy it several times with each foot.
   - Practise the complete step while concentrating only on making the hop clear.

3. **Add the straight front leg**
   - Show the extended front-leg position.
   - Practise the hop with the front leg fully extended and the front foot off the floor.
   - Repeat the step while concentrating on the extension.

4. **Add the reach**
   - Link the hop, reach forward and close.
   - Practise leading with both the right and left foot.

5. **Add third position**
   - Practise: step forward, close in third position.
   - Repeat leading with each foot.
   - Repeat on the toes if appropriate.

6. **Put the complete step together**
   - Finish by dancing the complete step, first slowly and then with suitable jig music. The teaching guidance specifically notes that jig time is particularly suitable for practice.

### 3. Points to observe

The manual says:

> “The hop at the beginning must be very positive, although it should not be too high or the remainder of the step will become distorted.”

It also specifies that:

> “The fully extended leg should be turned out from the hip to show a firm line from hip to toe, the knee straight but not stiff, the toe pointed down and approximately 5 cm (2 inches) clear of the floor.”

For the close:

> “Each time the feet close in third position, the instep of the rear foot makes contact with the heel of the front foot, but is not tucked under that heel.”

### 4. Common beginner faults

The RSCDS teaching guidance lists these faults to watch for:

- Lack of outward rotation from the hip
- An incorrect third position—leaving a gap, closing in first position, or passing the feet
- Lack of hop
- Kicking the front leg up during the hop
- Insufficient extension in the knee and foot
- Bending the front knee when taking weight
- Pulling in the leading foot instead of reaching forward
- Poor poise
- Scraping the feet

For a beginner class, correct only one or two faults at a time—usually the **clear hop**, **forward reach**, and **third-position close**. Once those are secure, refine turnout, poise and foot detail.

### search-rscds-strathspey-poussette

**Prompt:** Find me three 32-bar RSCDS strathspeys that include a poussette.

#### gpt-5.4-mini — PASS (7.4s, 4 tool calls, 31989+350 tokens)
- ✅ rscds_only: 3 dances linked; non-RSCDS: none
- ✅ min_dance_links: 3 linked (need 3)
- ✅ expect_any: hits: ['poussette']
- tools: search_cribs, get_dance_detail, get_dance_detail, get_dance_detail

Here are three 32-bar **RSCDS Strathspeys** that include a **poussette**:

1. [Neidpath Castle](https://my.strathspey.org/dd/dance/4890/) — Strathspey, 32 bars, Longwise 3C  
   - Includes a **½ poussette**  
   - RSCDS Book 22

2. [New Park](https://my.strathspey.org/dd/dance/4925/) — Strathspey, 32 bars, Longwise 4C  
   - Includes a **standard poussette**  
   - RSCDS Book 19

3. [The Star](https://my.strathspey.org/dd/dance/6285/) — Strathspey, 32 bars, Longwise 3C  
   - Includes **½ diamond poussette** and **½ poussette**  
   - RSCDS Book 28

If you want, I can also give you:
- three **easier** ones,
- three from a specific **RSCDS book**, or
- the **cribs** for any of these.

#### gpt-5.6-luna — PASS (7.0s, 5 tool calls, 24601+392 tokens)
- ✅ rscds_only: 3 dances linked; non-RSCDS: none
- ✅ min_dance_links: 3 linked (need 3)
- ✅ expect_any: hits: ['poussette']
- tools: search_cribs, find_dances, get_dance_detail, get_dance_detail, get_dance_detail

Here are three **32-bar RSCDS strathspeys containing a poussette**:

1. [New Park](https://my.strathspey.org/dd/dance/4925/) — 32 bars, 3-couple longwise set  
   - Includes a **standard poussette** in bars 1–8  
   - RSCDS Book 19, No. 11

2. [Neidpath Castle](https://my.strathspey.org/dd/dance/4890/) — 32 bars, 3-couple longwise set  
   - Includes two **half-poussettes** in bars 25–32  
   - RSCDS Book 22, No. 9

3. [The Fête](https://my.strathspey.org/dd/dance/2136/) — 32 bars, 3-couple longwise set  
   - Includes a **standard poussette** in bars 25–32  
   - RSCDS Book 25, No. 1

#### gpt-5.6-luna+reasoning — PASS (6.4s, 1 tool calls, 10405+329 tokens)
- ✅ rscds_only: 3 dances linked; non-RSCDS: none
- ✅ min_dance_links: 3 linked (need 3)
- ✅ expect_any: hits: ['poussette']
- tools: search_cribs

Here are three **32-bar RSCDS strathspeys** that include a **poussette**:

1. [Neidpath Castle](https://my.strathspey.org/dd/dance/4890/) — 32-bar Strathspey, 3-couple longwise  
2. [New Park](https://my.strathspey.org/dd/dance/4925/) — 32-bar Strathspey, 3-couple longwise  
3. [The Star](https://my.strathspey.org/dd/dance/6285/) — 32-bar Strathspey, 3-couple longwise

### teach-pas-de-basque

**Prompt:** How do I teach pas de basque to a beginner class? Include the common faults to watch for.

#### gpt-5.4-mini — PASS (5.3s, 2 tool calls, 10925+599 tokens)
- ✅ required_tools: missing: none; used: ['get_teaching_guidance', 'search_manual']
- ✅ expect_any: hits: ['pas de basque']
- ✅ forbid_any: forbidden hits: none
- tools: search_manual, get_teaching_guidance

Here’s a beginner-friendly way to teach **pas de basque**.

## What the step is
From the RSCDS manual, **pas de basque** is a step used for setting, turning on the spot, turning when two hands are given, and sometimes for travelling a short distance. It is danced on **three distinct beats**, with the **jeté** as the distinctive Scottish element.

## Main teaching points
From the RSCDS teaching guidance:
- **The three distinct beats**, with a momentary change of weight on the 2nd beat
- **Pick up the knee on beat 1**
- **The third position**
- **A strong jeté** with full extension of the foot, ankle, and leg

## A simple teaching progression for beginners
1. **Name and purpose**
   - Tell them this is the step used for setting and turning.

2. **Rhythm first**
   - Use the words: **“Spring, beat, beat and”**
   - Or **“step, beat, beat and”** to begin
   - Have them mark time and feel the three beats clearly

3. **Third position**
   - Show the feet in **third position**
   - Have the class copy you
   - Check that they can see and feel the correct foot placement

4. **Add the jeté**
   - Demonstrate the full step slowly to both sides
   - Emphasize **“extend”** on the jeté
   - Then have them dance the whole step with music

5. **Keep it on the spot**
   - For first teaching, stress that pas de basque is danced **on the spot, not side to side**
   - Only later introduce travelling or turning uses

## Common faults to watch for
From the RSCDS teaching guide, watch for:
- **Lack of outward rotation from the hip**
- **A two-beat step** instead of three clear beats
- **A tap of the foot on the second beat**
- **Incorrect position of jeté**
- **Lack of extension in the jeté**
- **Incorrect movement into third position**
- **An incorrect third position**
- **Poor poise**

## Helpful coaching reminders
- Keep asking for **three clear beats**
- Encourage dancers to stay **on their toes**
- Make sure the **jeté is strong and extended**
- Don’t let the step drift into a travelling movement too early

If you want, I can also give you a **5-minute class exercise plan** for teaching pas de basque to complete beginners.

#### gpt-5.6-luna — PASS (8.5s, 2 tool calls, 10280+730 tokens)
- ✅ required_tools: missing: none; used: ['get_teaching_guidance', 'search_manual']
- ✅ expect_any: hits: ['pas de basque']
- ✅ forbid_any: forbidden hits: none
- tools: search_manual, get_teaching_guidance

## Teaching pas de basque to beginners

### 1. Explain the purpose and rhythm

Tell the class that pas de basque is used for setting, turning on the spot, and sometimes travelling a short distance. One pas de basque takes **one bar of music**.

Use the rhythm:

> **Spring – beat – beat**  
> or initially: **1 – 2 – 3**

Emphasise that it has **three distinct beats**, not two.

### 2. Establish the rhythm

Begin without travelling:

1. Have the dancers mark time on the spot.
2. Say or clap **“1, 2, 3”**.
3. Ask them to lift the knees and feet slightly so that all three beats are clear.
4. Add music gradually, increasing the speed as they become comfortable.
5. Encourage them to stay lifted and dance “on their toes”.

### 3. Introduce third position

Demonstrate third position clearly:

- One foot is in front of the other.
- The heel of the front foot is tucked into the instep of the other foot.
- Practise placing the left foot in front, then the right, several times.
- Have the class look down briefly to check their foot placement.

Then practise:

> **Step in front – behind – and**

Keep the feet light and continue to insist on three clear beats.

### 4. Add the jeté

Demonstrate the complete movement slowly to both sides:

- Begin with the spring.
- Move through the front and behind positions.
- Finish with a strong **jeté**, extending the foot, ankle and leg fully.
- The step should be danced **on the spot**, rather than travelling significantly.

Practise the jeté separately from third position, only a few times on each foot, before combining it with the complete step.

### 5. Put it into setting

Once the individual pas de basque is secure, practise:

- Right foot, then left foot
- Setting in place
- Setting while facing a partner
- Eventually, setting with the arms and upper-body poise required in a dance

Keep the focus on rhythm and placement rather than adding too many details at once.

## Common faults to watch for

According to the RSCDS teaching guidance, observe and correct:

- **Lack of outward rotation from the hip**
- **A two-beat step** instead of three distinct beats
- **Tapping the foot** on the second beat
- **Incorrect jeté position**
- **Insufficient extension** of the jeté
- **Incorrect movement into third position**
- **Incorrect third position**
- **Poor poise**

A useful correction sequence is:

1. Re-establish **“spring, beat, beat”**.
2. Check the third-position foot placement.
3. Practise the jeté separately.
4. Recombine the parts slowly.
5. Return to music only when the three beats are clear.

### Sources

- **RSCDS Manual**, section **5.4.2, “Pas de basque,” p. 75**
- **RSCDS Teaching Scottish Country Dancing – Guidelines for Tutors, Teachers and Candidates**, “Teaching Pas De Basque”

#### gpt-5.6-luna+reasoning — PASS (13.9s, 3 tool calls, 15900+1039 tokens)
- ✅ required_tools: missing: none; used: ['get_teaching_guidance', 'search_manual']
- ✅ expect_any: hits: ['pas de basque']
- ✅ forbid_any: forbidden hits: none
- tools: search_manual, get_teaching_guidance, search_manual

## Pas de basque: beginner lesson

### 1. Explain the purpose and rhythm

Tell the class that pas de basque is used for setting and turning, and that one step takes one bar of music. Begin with the right foot, then repeat to the left.

Use the rhythm:

> **“Spring, beat, beat, and…”**

For beginners, practise initially to reel music, which provides four even beats.

### 2. Teach the step slowly

The RSCDS Manual describes the right-foot step as follows:

> 1. Spring onto the right foot.  
> 2. Bring the left foot in front of the right foot to third position, and with a transfer of weight onto the left foot, bring the right foot off the floor.  
> 3. Change the weight onto the right foot again and bring the left foot to fourth intermediate aerial position.  
> 4. Hold the position.

Then repeat beginning with the left foot.

The step should be danced **on the spot**, not from side to side. At first, avoid asking the class to travel or turn.

### 3. Suggested teaching progression

From the RSCDS teaching guidance:

1. **Give the name and purpose.**
2. Practise the rhythm without the full step:
   - “1, 2, 3”
   - “Spring, beat, beat”
3. Add the knee and foot pick-up so that the three beats are clearly visible.
4. Introduce third position on the flat of the foot:
   - heel of the front foot tucked into the instep of the back foot.
5. Mark time in third position, alternating which foot is in front.
6. Add the action:
   - spring,
   - close in front,
   - jeté.
7. Bring in music slowly, then gradually increase the speed.
8. Encourage the dancers to remain lifted “on their toes.”
9. Practise only a few repetitions on each foot before resting or changing activity.
10. Finish by dancing the complete step, first slowly and then to suitable music.

Use visual and rhythmic reminders such as:

> **“Spring, in front, behind”**  
> **“Spring, beat, beat”**  
> **“Extend”**

For a beginner class, prioritise **three clear beats, a good third position, and dancing on the spot**. Travelling pas de basque can be introduced later.

## Common faults to watch for

The RSCDS teaching guidance identifies these faults:

- Lack of outward rotation from the hip
- Making it a two-beat step
- Tapping the foot on the second beat
- Incorrect position of the jeté
- Lack of extension in the jeté
- Incorrect movement into third position
- Incorrect third position
- Poor poise

### Specific corrections

- **Two beats instead of three:** return to “spring, beat, beat” without music, making the weight changes distinct.
- **Tap on beat two:** clarify that the dancer changes weight rather than merely touching the floor.
- **Poor third position:** practise the position separately, with the heel of the front foot near the instep of the back foot.
- **Weak jeté:** ask for a positive, extended movement of the foot and leg, while maintaining balance.
- **Travelling sideways:** remind dancers that the beginner version is danced on the spot.
- **Poor poise or raised shoulders:** reduce the size of the step, keep the body lifted, and allow the arms to remain relaxed.

The manual particularly stresses that the jeté is the distinctive element of the Scottish pas de basque, but beginners should first learn it with control rather than trying to make it large or high.

### formation-reel3-vs-reel4

**Prompt:** What is the difference between a reel of three and a reel of four? Explain the track each dancer follows.

#### gpt-5.4-mini — PASS (7.2s, 5 tool calls, 16304+739 tokens)
- ✅ required_tools: missing: none; used: ['search_manual']
- ✅ expect_any: hits: ['reel of three']
- tools: search_manual, search_manual, search_manual, search_manual, search_manual

A **reel of three** and a **reel of four** are both figure-of-eight style reels, but they differ in the number of dancers involved and the path each dancer traces.

## Reel of three
From the RSCDS manual, a reel of three is “similar to a figure of 8 on the sidelines” and “forms a figure of 8 with well-rounded loops at both ends.”  
In the standard reel of three on the sidelines:

- It is danced by **3 dancers**
- It usually starts with one dancer facing one way and the other two the opposite way
- Each dancer follows a **single figure-eight path** around the other two dancers
- All three finish back in their starting places

### Track each dancer follows
Thinking of the three dancers as **top, middle, bottom** along the line:

- The dancer who starts in the **middle** usually weaves out one side, round one end, and back through the center to the other end.
- The two end dancers each make a similar figure-of-eight path, but offset so that all three interlace smoothly.
- The result is that each dancer alternates passing one dancer on one side and another on the other side, completing a neat 8-bar pattern.

## Reel of four
A reel of four involves **4 dancers**, and there are two common kinds:

### 1. Reel of four (double)
This is the familiar “two couples dancing two interlocking reels.”  
The manual says that in a square set the reels are at right angles to each other; in a longwise set, one reel runs from 1st man’s place to 4th woman’s place, the other from 1st woman’s place to 4th man’s place.

### 2. Reel of four (interlocking)
Here three or more couples face as if for grand chain, and all dance the path of a reel of four as if from an end position.

### Track each dancer follows
In a reel of four, each dancer follows a **longer, more extended figure-eight path** than in a reel of three:

- Each person passes the first dancer by the **right**
- Then passes the next by the **left**
- Then the next by the **right**
- Then loops round to face the last dancer passed
- In the common double reel, the paths are **interlocking**, so two reels happen at once and cross in the middle

## Main difference in one sentence
- **Reel of three:** 3 dancers weaving a figure eight around one another.
- **Reel of four:** 4 dancers interweaving, usually with two crossing figure-eight paths.

If you want, I can also draw a simple step-by-step track diagram for each dancer in a reel of three and a reel of four.

#### gpt-5.6-luna — PASS (10.2s, 4 tool calls, 21145+657 tokens)
- ✅ required_tools: missing: none; used: ['search_manual']
- ✅ expect_any: hits: ['reel of three']
- tools: search_manual, search_manual, search_manual, search_manual

A **reel of three** uses **three dancers**; a **reel of four** uses **four dancers**. In both cases, each dancer follows a continuous, rounded **figure-of-eight track**, passing the other dancers alternately by the right and left.

### Reel of three

Imagine three dancers arranged in a line:

```text
A — B — C
```

The **middle dancer** begins by passing one end dancer, while the two end dancers travel around the outside of the figure. The tracks form a single figure eight:

- Each dancer passes another dancer by the **right**.
- They then pass the next dancer by the **left**.
- The dancers loop around the ends and return through the centre.
- Each dancer finishes in the position from which they started, unless the dance specifies a different ending.

The important visual point is that the three tracks are interwoven into **one figure eight**, with the dancers making rounded loops at each end. The RSCDS Manual describes the reel of three as forming “a figure of 8 with well-rounded loops at both ends” (Manual §6.25.1).

### Reel of four

A standard reel of four uses four dancers, commonly arranged in a square or in two facing pairs:

```text
A     B

C     D
```

The dancers follow **two interweaving figure-eight tracks**:

- Each dancer passes the facing dancer by the **right**.
- Each then passes the next dancer by the **left**.
- The four dancers continue around the outside and through the centre.
- The tracks are wider and more open than in a reel of three because there are four dancers and four passing points.

In a **double reel of four**, two reels of four are danced simultaneously. The two figure-eight patterns intersect in the middle, where dancers commonly give left hands across halfway (RSCDS Manual §6.24.8).

There is also an **interlocking reel of four**, in which three or more couples face as for a grand chain. Each couple follows the path of a reel of four, passing successive dancers alternately right and left (RSCDS Manual §6.24.9).

### In short

- **Reel of three:** three dancers, one figure eight, with one dancer initially in the middle.
- **Reel of four:** four dancers, two interwoven figure-eight paths, usually beginning from a square or two facing pairs.
- In both: **right-hand pass, left-hand pass**, with rounded loops rather than sharp corners.

#### gpt-5.6-luna+reasoning — PASS (21.9s, 5 tool calls, 15759+1465 tokens)
- ✅ required_tools: missing: none; used: ['search_manual']
- ✅ expect_any: hits: ['reel of three']
- tools: search_manual, search_manual, search_manual, search_manual, search_manual

## Reel of three

A **reel of three** is danced by three people. The dancers collectively trace a **figure of eight**, with a rounded loop at each end.

Imagine three starting places in a line:

```text
A
B
C
```

The track works as follows:

- The dancers repeatedly pass one another, alternating **right shoulder and left shoulder**.
- The dancer who is not passing at that moment travels around one of the end loops.
- The end loops alternate: one dancer curves around the top, then another around the bottom, and so on.
- Each dancer therefore travels through the central crossing and around both ends of the figure-eight track during the eight bars.
- At the end, everyone returns to their original place, usually facing the opposite direction from the way they began or as specified by the dance.

So the essential picture is:

```text
     \     /
      \   /
       \ /
       / \
      /   \
     /     \
```

The three dancers share one continuous **figure-eight track**. The crossings are made by passing the appropriate dancer by the right or left shoulder.

## Reel of four

A **reel of four** is danced by four people. It is not simply a reel of three with one extra dancer added. The dancers pass alternately by the right and left, but the track consists of **two interlocking loops or reels**.

In a standard or **double reel of four**:

- Two pairs of dancers dance one reel.
- The other two pairs dance a second reel crossing the first in the middle.
- In a square set, the two reels are generally at right angles.
- The dancers pass their partner by the right, then pass the next facing dancer by the right, while the dancers not passing travel round the outside of their loop.
- Usually the dancers give **left hands across in the middle** halfway through the figure.
- Each dancer follows a curved route around one of the interlocking loops and returns to the starting place after the second half.

A simplified view is:

```text
       \   /
        \ /
         X
        / \
       /   \
```

The central crossing is the important difference: the four tracks form **two crossing/interlocking reels**, rather than the single figure-eight track of a reel of three.

## Interlocking reel of four

There is also a specific formation called an **interlocking reel of four**, often seen with three or more couples in a grand-chain arrangement:

- Everyone passes the facing dancer by the right.
- Then the next dancer by the left.
- Then the next by the right.
- Each dancer then travels to the right around a loop to face the last dancer passed.
- The sequence repeats.

Here, each dancer’s route is essentially a **reel-of-four path through the line or circle of dancers**, with alternating right- and left-shoulder passes followed by a large looping turn.

### In short

| Formation | Number of dancers | Track |
|---|---:|---|
| Reel of three | 3 | One shared figure-eight track with rounded loops at both ends |
| Reel of four | 4 | Two interlocking or crossing reel tracks, usually with a central crossing |
| Interlocking reel of four | 4 or more in the larger arrangement | Each dancer follows a reel-of-four loop through successive facing dancers |

The safest visual distinction is: **three dancers make one figure eight; four dancers make two reels that interlock through the centre.**

### crib-lookup-knot

**Prompt:** In the dance 'The Wee Cooper of Fife', what happens in bars 1-8? Quote the crib.

#### gpt-5.4-mini — FAIL (3.6s, 2 tool calls, 14577+151 tokens)
- ❌ min_dance_links: 0 linked (need 1)
- ✅ required_tools: missing: none; used: ['find_dances', 'get_dance_detail']
- tools: get_dance_detail, find_dances

I couldn’t find a matching dance record for **“The Wee Cooper of Fife”** in the database, so I can’t quote the crib yet.

If you want, send me:
- the exact dance title as it appears in the book, or
- the devisor / publication name, or
- a Strathspey Server link,

and I’ll look up bars 1–8 and quote the crib precisely.

#### gpt-5.6-luna — FAIL (8.0s, 2 tool calls, 14561+120 tokens)
- ❌ min_dance_links: 0 linked (need 1)
- ❌ required_tools: missing: ['get_dance_detail']; used: ['find_dances', 'search_cribs']
- tools: find_dances, search_cribs

I couldn’t locate **“The Wee Cooper of Fife”** in the dance database, so I can’t quote its crib reliably. Could you check the title or provide the source/book (and, if possible, the dance’s Strathspey Server link)?

#### gpt-5.6-luna+reasoning — PASS (10.7s, 4 tool calls, 26015+428 tokens)
- ✅ min_dance_links: 1 linked (need 1)
- ✅ required_tools: missing: none; used: ['find_dances', 'get_dance_detail', 'search_cribs']
- tools: find_dances, search_cribs, find_dances, get_dance_detail

In **[The Wee Cooper O’ Fife](https://my.strathspey.org/dd/dance/6995/)**, bars 1–8 are part of the 1st couple’s first figure. The crib says:

> **1-10:** 1s set & cross RH, set & cross down LH & cast up round 2s to original place - 1 2

Thus, in bars 1–8, the 1st couple set and cross by the right hand, then set and cross down by the left hand before continuing the cast around the 2nd couple.

### offtopic-reject

**Prompt:** Write me a limerick about my cat and then give me a recipe for shortbread.

#### gpt-5.4-mini — PASS (0.7s, 0 tool calls, 0+0 tokens)
- ✅ expect_any: hits: ['Scottish Country Dancing']
- ✅ forbid_any: forbidden hits: none
- tools: none

Thanks for reaching out! I'm dedicated to Scottish Country Dancing, including sharing information and helping plan classes or dance programmes. Could you rephrase your question to focus on Scottish Country Dancing?

#### gpt-5.6-luna — PASS (0.7s, 0 tool calls, 0+0 tokens)
- ✅ expect_any: hits: ['Scottish Country Dancing']
- ✅ forbid_any: forbidden hits: none
- tools: none

Thanks for reaching out! I'm dedicated to Scottish Country Dancing, including sharing information and helping plan classes or dance programmes. Could you rephrase your question to focus on Scottish Country Dancing?

#### gpt-5.6-luna+reasoning — PASS (0.7s, 0 tool calls, 0+0 tokens)
- ✅ expect_any: hits: ['Scottish Country Dancing']
- ✅ forbid_any: forbidden hits: none
- tools: none

Thanks for reaching out! I'm dedicated to Scottish Country Dancing, including sharing information and helping plan classes or dance programmes. Could you rephrase your question to focus on Scottish Country Dancing?

### planner-rscds-tournee

**Prompt:** Plan a 45 minute lesson with 3 RSCDS dances, at least one strathspey, for an advanced class working on the tournee.

#### gpt-5.4-mini — PASS (17.2s, 14 tool calls, 31958+2365 tokens)
- ✅ rscds_only: 3 dances linked; non-RSCDS: none
- ✅ min_dance_links: 3 linked (need 3)
- ✅ required_tools: missing: none; used: ['find_dances', 'get_dance_detail', 'get_full_crib', 'get_teaching_guidance', 'get_teaching_points_for_dance', 'search_cribs']
- ✅ expect_any: hits: ['tournee']
- tools: find_dances, find_dances, search_cribs, get_full_crib, get_full_crib, get_full_crib, get_teaching_points_for_dance, get_teaching_points_for_dance, get_teaching_points_for_dance, get_dance_detail, get_dance_detail, get_dance_detail, get_teaching_guidance, get_teaching_guidance

Here’s a 45-minute lesson plan for an advanced class working on the **tournee**, with **3 RSCDS dances** including **at least one strathspey**.

I’ve chosen dances that are all RSCDS-published and that give useful practice in:
- turning corners / partner
- reeling and directional awareness
- strathspey phrasing and control
- movement on the tournee, especially maintaining shape, flow, and timing in turns

## Lesson focus
**Tournee:** aim for smooth, well-tracked turning on the tournee, with clear posture, maintained frame, and control of the rotation through the whole turn.

### Suggested dance order
1. **[Bridge of Nairn](https://my.strathspey.org/dd/dance/794/)** — Strathspey, easier start, good for control and corners  
2. **[Portnacraig](https://my.strathspey.org/dd/dance/5326/)** — Reel, builds clarity and flow through reels and diagonals  
3. **[Lennox Love to Blantyre](https://my.strathspey.org/dd/dance/3775/)** — Strathspey, best as the final dance for consolidation and stamina  

---

## Timing and structure: 45 minutes

### 1) Warm-up and technique: 8 minutes
- 2 min general warm-up: ankles, knees, hips, posture, turnout
- 3 min travelling step / strathspey step refresher
- 3 min tournee-specific work:
  - turn from the body, not the arms
  - keep the line of the shoulders stable
  - step around the turn with control
  - finish each turn in balance, ready to move on

### 2) Dance 1: Bridge of Nairn — 11 minutes
- 3 min walk-through
- 7 min dance
- 1 min recap of tournee-related points

### 3) Dance 2: Portnacraig — 11 minutes
- 3 min walk-through
- 7 min dance
- 1 min recap

### 4) Dance 3: Lennox Love to Blantyre — 12 minutes
- 4 min walk-through
- 7 min dance
- 1 min final review

### 5) Cool-down / summary: 3 minutes
- brief debrief
- reinforce key technical points for tournee
- mention what improved and what to watch next time

---

# Dance 1: [Bridge of Nairn](https://my.strathspey.org/dd/dance/794/)
**Strathspey, 32 bars, Longwise 4, 3C**

## Full crib
**1–**
1c cast off 2 places, lead up to the top ; cross over and cast off one place (2c up), meet NHJ facing 2W

**9–**
1c set to 2W, turn inwards, set to 3M ; veer left and set to 3W, turn inwards, set to 2M, finish facing 1cnrs (1M pulls back Rsh).

**17–**
1c turn corner, P ; corner, P finishing (2,1x,3)

**25–**
All A&R ; 1c turn BH 1½ times (2,1,3)

## Teaching points
### Formations in the dance
- **Cast behind own lines and lead up the middle**
- **Turn corners and partner**
- **Advance and retire**

### Tournee focus
- In the **turn corners and partner** phrase, insist on:
  - making the turn continuous, not two separate actions
  - maintaining eye contact and frame through the turn
  - finishing the turn square to the next movement
- For strathspey phrasing, dancers should **travel smoothly** rather than “step and stop.”

### Helpful teaching notes
- In the corner turns, remind dancers to keep the turn moving **on the line of dance** and to avoid over-turning before they are ready to travel on.
- Encourage clear, calm preparation before the tournee-like turn with partner at the end.

---

# Dance 2: [Portnacraig](https://my.strathspey.org/dd/dance/5326/)
**Reel, 32 bars, Longwise 4, 3C**

## Full crib
**1–**
1c set (no advance), turn BH ½ into the middle NHJ facing 2c diagonally (drop hands) ; 1c set to 2c and face out | turn 2c EH ½ (2,1x,3)

**9–**
All A&R ; ½circle6 L (3x,1,2x)

**17–**
1c pass Lsh into ½ Rsh Reel4 with 1cnrs, pass Lsh into ; ½ Rsh Reel4 with 2cnrs (to 2,1x,3)

**25–**
1c ½Fig8 round 3c ; All turn RH (2,1,3)

## Teaching points
### Formations in the dance
- **Advance and retire**
- **Half circle six hands left**
- **Half reels of four**
- **Half figure of eight**
- **Turn right hands**

### Tournee focus
- The reel phrases are ideal for teaching **body-led turning**:
  - keep shoulders level
  - let the feet do the turning work
  - maintain flow through the reel without “stopping to think”
- Use the final **all turn RH** to remind dancers of:
  - a clean, centred turn
  - finishing ready for the next bar
  - no collapsing of frame as the turn finishes

### Helpful teaching notes
- This is the best dance in the set for reinforcing **direction changes and rotation under pressure**.
- Make sure dancers don’t break the reel shape when tired: keep the path clear and the turn controlled.

---

# Dance 3: [Lennox Love to Blantyre](https://my.strathspey.org/dd/dance/3775/)
**Strathspey, 32 bars, Longwise 4, 3C**

## Full crib
**1–**
1c cross RH, cast off (2c up) ; 1c+3c ½RHA (2,3x,1)

**9–**
1c set twice ; 3c+1c ½R&L, to face 1cnr

**17–**
1c set to and turn corners

**25–**
Reels3{6} on the sides | 1c cross to 2pl own side

## Teaching points
### Formations in the dance
- **Half right hands across**
- **Half rights and lefts**
- **Set to and turn corners**
- **Reels of three on the sides**

### Tournee focus
- The **set to and turn corners** is the key phrase for the lesson:
  - encourage a confident set before turning
  - turn with a steady centre and good posture
  - don’t rush out of the turn
- In the strathspey context, the tournee should feel **measured, smooth, and complete**.

### Helpful teaching notes
- This dance offers a good contrast with Bridge of Nairn:
  - more directional variety
  - more obvious need to control the turn after corners
- Remind dancers that the turn begins from a balanced stance, not from a leap.

---

## Teaching the tournee in this class
For an advanced class, I’d keep the focus fairly refined:

### Key coaching points
- **Start from balance**
  - dancers should arrive at the turn ready, not chasing it
- **Use the body to turn**
  - the frame stays stable; the feet and torso manage the turn
- **Maintain speed through the turn**
  - no hesitations mid-turn
- **Finish in alignment**
  - be ready to flow into the next figure immediately
- **In strathspey turns**
  - keep it long, calm, and continuous
  - do not shorten the final part of the rotation

### Common faults to watch for
- overuse of the arms
- turning too early or too late
- loss of posture or frame
- stopping at the end of the tournee instead of flowing onward
- inconsistent rotation between bar 1 and bar 2 of the turn

---

## Suggested class management
- **First walk-through**: brief and efficient; give the dance shape clearly
- **Second walkthrough**: only stop for the tournee or turning issue
- **During dancing**: prompt with concise cues, especially:
  - “turn from the body”
  - “keep the shape”
  - “finish the turn”
  - “travel on”
- Since this is an advanced class, avoid over-explaining; correct with precision

---

## Optional music planning
If you’d like, I can also find suitable recordings for these three dances and add them to the lesson plan.

I can also:
- save this as a lesson plan
- export it as Markdown
- revise it to use a different selection of dances if you want more or less challenge

#### gpt-5.6-luna — PASS (47.0s, 32 tool calls, 76407+4135 tokens)
- ✅ rscds_only: 3 dances linked; non-RSCDS: none
- ✅ min_dance_links: 3 linked (need 3)
- ✅ required_tools: missing: none; used: ['find_dances', 'find_videos', 'get_dance_detail', 'get_full_crib', 'get_teaching_guidance', 'get_teaching_points_for_dance', 'search_cribs', 'search_manual']
- ✅ expect_any: hits: ['tournee']
- tools: search_cribs, find_dances, search_cribs, search_cribs, find_dances, search_cribs, get_full_crib, get_dance_detail, get_teaching_points_for_dance, get_full_crib, get_dance_detail, get_teaching_points_for_dance, get_full_crib, get_dance_detail, get_teaching_points_for_dance, search_manual, get_teaching_guidance, get_teaching_guidance, find_dances, search_cribs, search_manual, search_manual, search_manual, get_full_crib, get_dance_detail, get_teaching_points_for_dance, get_full_crib, get_dance_detail, get_teaching_points_for_dance, get_teaching_guidance, get_teaching_guidance, find_videos

# 45-minute advanced lesson: Tournee

**Class focus:** the tournee, with attention to preparation, handhold, weight transfer, rotation, and clean exits.  
**Dances:** three RSCDS dances, including two strathspeys.  
**Suggested order:** teach the tournee in a controlled strathspey context first, reinforce it in a second strathspey, then apply the same principles at reel tempo.

> **Important:** The database’s RSCDS manual lookup did not return a dedicated “tournee” entry. The tournee-specific coaching below is therefore practical teaching guidance, while the cited RSCDS points for pas de basque, poussette, and strathspey travelling step should be used where relevant.

---

## Timing at a glance

| Time | Activity |
|---:|---|
| 0:00–0:04 | Warm-up and tournee preparation |
| 0:04–0:12 | Teach and practise the tournee |
| 0:12–0:21 | Dance 1: [Argyll Strathspey](https://my.strathspey.org/dd/dance/221/) |
| 0:21–0:29 | Dance 2: [Out of Thin Air](https://my.strathspey.org/dd/dance/15406/) |
| 0:29–0:41 | Dance 3: [The Nut](https://my.strathspey.org/dd/dance/5007/) |
| 0:41–0:45 | Consolidation: tournee review and final dance |

Use short explanations and frequent dancing. This is an advanced class, so avoid teaching every formation from first principles; isolate only the tournee and any transition that affects it.

---

# 1. Warm-up and preparation — 4 minutes

### Aims
- Establish upright posture, turnout, and controlled weight transfer.
- Prepare the pas de basque action used in the tournee.
- Remind dancers that the tournee is a turning formation, not a hurried spin.

### Exercise
1. In pairs, face a partner with both hands joined.
2. Practise slow pas de basque on the spot, first without turning.
3. Add a quarter-turn over two bars, then a half-turn over four bars.
4. Repeat with dancers concentrating on:
   - staying lifted through the torso;
   - keeping the feet underneath the body;
   - transferring weight fully before the next step;
   - maintaining a comfortable, supportive handhold.

### RSCDS pas de basque points
The RSCDS teaching guidance identifies:
- three distinct beats;
- knee lifted on beat 1;
- accurate third position;
- a strong jeté with full extension;
- the step remaining on the spot unless it is deliberately travelling or turning.

Correct immediately:
- a two-beat pas de basque;
- tapping rather than transferring weight;
- collapsing posture;
- excessive sideways travel;
- a weak or absent jeté.

---

# 2. Teaching the tournee — 8 minutes

## Formation concept

The tournee is normally danced by two couples. Partners dance together in a turning, travelling movement, using pas de basque. The formation depends on accurate preparation and a shared centre: dancers should turn as a unit rather than pull one another around.

### Teaching sequence

#### A. Walk the shape — 2 minutes
Arrange the class in pairs or small groups of two couples.

Walk the formation without steps:

1. Begin in the correct starting position, with the couples facing as required by the dance.
2. Establish the handhold before moving.
3. Move around the centre of the formation in the prescribed direction.
4. Show the intended finishing position clearly.
5. Repeat from the opposite side so dancers understand the spatial pattern.

At this stage, emphasise the **entry and exit**, not speed.

#### B. Add pas de basque — 2 minutes
- Men begin with the left foot and women with the right where the formation requires the standard reel/jig-time pas de basque convention.
- Keep the first movement decisive but not large.
- The body turns progressively through the phrase; do not twist the upper body independently of the feet.
- Maintain the handhold without gripping.

#### C. Practise in slow time — 2 minutes
Dance the tournee with the music slowed or with the teacher counting.

Coach:
- “Prepare.”
- “Step underneath.”
- “Turn together.”
- “Keep the centre.”
- “Finish the phrase.”

#### D. Dance to tempo — 2 minutes
Dance once at a moderate tempo, stop, correct one or two faults only, then repeat at normal strathspey tempo.

### Tournee teaching points

- **Preparation:** arrive in the correct formation before beginning the first turning step.
- **Handhold:** hands should support the movement, not drag the partner.
- **Shared centre:** both dancers rotate around a common centre.
- **Weight transfer:** complete each pas de basque before beginning the next.
- **Foot placement:** retain turnout and close accurately in third position where appropriate.
- **Travel:** cover the required distance without taking oversized steps.
- **Phrasing:** do not rush the final step to reach the finishing place.
- **Exit:** release or change hands smoothly and face the next formation promptly.
- **Partner awareness:** look in the direction of travel when needed, but avoid turning the head so far that posture collapses.

For an advanced class, ask dancers to identify whether their difficulty is caused by:
1. incorrect entry;
2. poor handhold;
3. insufficient weight transfer;
4. turning too early;
5. over-travelling; or
6. an untidy exit.

---

# 3. Dance 1 — Argyll Strathspey — 9 minutes

**RSCDS publication:** *Book 35 Scottish Country Dances*, No. 3.  
**Formation:** longwise, three couples active.  
**Music:** strathspey.  
**Primary focus:** tournee after a demanding sequence of circle and rights-and-lefts work.

## Full crib

**1–8:**  
1st, 2nd and 3rd couples: half right-hand turn and remain in the middle; swivel right and dance out to opposite sides; repeat, finishing in own places.

**9–16:**  
1st, 2nd and 3rd couples: circle six hands round and back. 1st and 3rd couples finish facing down and up the middle respectively.

**17–24:**  
1st and 3rd couples: rights and lefts up and down the middle, finishing in own places.

**25–32:**  
1st and 2nd couples: tournee.

## Teaching and coaching points

### Bars 1–8: half-turn and cast away
- The half-turn must finish with dancers remaining in the middle.
- The swivel is a controlled change of direction, not a separate flourish.
- Dancers should leave the middle on the correct diagonal and arrive on the opposite side without drifting.
- Watch that the second repetition does not become hurried.

### Bars 9–16: circle six and back
- Keep the circle round and evenly spaced.
- The circle should finish with 1st and 3rd couples correctly oriented for the next phrase.
- Do not allow the circle to collapse as dancers prepare to face up or down.

### Bars 17–24: rights and lefts
RSCDS guidance:
- the formation follows a square pattern;
- it may be danced across or up and down the set;
- hands are released at shoulder height as dancers pass one another.

For this dance:
- keep the movement compact enough to preserve the square;
- release hands cleanly rather than dropping them;
- arrive in own places with enough time to prepare for the tournee.

### Bars 25–32: tournee
- The preceding rights and lefts should finish with the couples ready, not still adjusting.
- Establish the handhold immediately.
- Keep the turning action smooth and centred.
- The final two bars should be used to complete the phrase and settle into the next position.

## Class procedure

1. Walk bars 25–32 once with two couples.
2. Dance the tournee twice slowly.
3. Dance the complete dance once without music, calling only the tournee.
4. Dance once to music.
5. If time permits, repeat the final eight bars from different starting positions.

---

# 4. Dance 2 — Out of Thin Air — 8 minutes

**RSCDS publication:** *A Third Book of Graded Scottish Country Dances*, No. 13.  
**Formation:** longwise, three couples.  
**Music:** strathspey.  
**Primary focus:** a tournee entered from a middle-of-the-set position, with attention to orientation and the transition from the preceding phrase.

## Full crib

**1–8:**  
1st couple set; cross by the right hand; cast off one place, 2nd couple moving up; turn by the left hand to face first corners.

**9–16:**  
1st couple turn corners and partner, finishing in 2nd place in the middle, facing up, nearer hands joined.

**17–24:**  
1st couple dance up between 2nd couple and cast off to 2nd place; dance down between 3rd couple and cast up to 2nd place, finishing in progressed places.

**25–32:**  
1st and 3rd couples: tournee.

## Teaching and coaching points

### Bars 1–8: set, cross, cast, and turn
- The first couple should preserve clear phrasing through the set, cross, and cast.
- After the left-hand turn, the couple must know exactly where they are facing before beginning the corner sequence.
- The cast should be a smooth strathspey movement, not a sudden change of direction.

### Bars 9–16: turn corners and partner
- The corner sequence must finish with the first couple in the middle, facing up, with nearer hands joined.
- This is the critical preparation for the next phrase.
- Encourage dancers to finish the final turn with their bodies already aligned for the upward movement.

### Bars 17–24: dance up and cast; dance down and cast
- The first couple should use the full eight bars for each up-and-down section.
- Avoid cutting the cast short.
- The final cast should place the couple accurately for the tournee with 3rd couple.
- The couple should arrive together; one dancer should not be ahead of the other.

### Bars 25–32: tournee
- The entry is from the middle of the set, so dancers must recognise the orientation rather than rely only on a familiar visual pattern.
- Keep the movement compact and smooth.
- The couple finishing the tournee should be ready for the next repeat without an extra adjustment step.

## Class procedure

1. Walk the transition from bars 17–24 into bars 25–32.
2. Practise the tournee with the couple entering from the middle.
3. Dance bars 17–32 twice.
4. Dance the complete dance once, with the teacher calling only the entry to the tournee.
5. Repeat if the class needs work on orientation.

---

# 5. Dance 3 — The Nut — 12 minutes

**RSCDS publication:** *Book 1 Scottish Country Dances*, No. 4.  
**Formation:** longwise, two couples.  
**Music:** jig.  
**Primary focus:** transferring the tournee principles to quicker pas de basque and a more energetic tempo.

## Full crib

**1–8:**  
1st man and 2nd woman: right-hand turn, finishing with 1st man facing up between 2nd couple and 2nd couple facing down. 1st man and 2nd couple balance in line while 1st woman dances under their arms once round 1st man, down on the women’s side and up on the men’s side.

**9–16:**  
1st couple lead down the middle and up.

**17–24:**  
1st and 2nd couples: poussette.

## Teaching and coaching points

Although this dance contains a **poussette**, not a tournee, it is useful as a final application dance because it reinforces the same requirements of shared timing, pas de basque, hand connection, and controlled turning.

### Bars 1–8: right-hand turn and balance in line
- The right-hand turn must finish in the correct facing positions.
- The balance in line should be clear and stable.
- The dancer travelling under the arms must have a definite pathway: down the women’s side and up the men’s side.
- Avoid lifting the arms excessively or allowing the arch to collapse.

### Bars 9–16: lead down and up
- Maintain a comfortable promenade hold.
- Use the full phrase and arrive ready for the poussette.
- The couple should not rush the final upward steps.

### Bars 17–24: poussette
RSCDS manual guidance:
- the poussette is usually a method of progression;
- it is danced using pas de basque;
- each man begins with the left foot and each woman with the right;
- if a change of foot is necessary, it normally occurs at the end of the previous eight-bar phrase and again at the end of the poussette.

For this dance:
- establish the correct starting foot before beginning;
- keep the pas de basque on the line of the formation;
- move as a pair rather than pushing or pulling;
- maintain turnout and accurate third position;
- complete the progression by the end of bar 24.

## Class procedure

1. Walk the poussette once, identifying the direction of travel.
2. Practise four bars of pas de basque with the correct handhold.
3. Dance the poussette slowly, then at jig tempo.
4. Dance bars 9–24.
5. Dance the complete dance twice, changing roles where possible.

### Advanced correction
Ask dancers to distinguish between:
- a genuine pas de basque with three beats and a clear jeté; and
- a hurried side-step caused by trying to travel too far.

The RSCDS teaching guidance stresses:
- three distinct beats;
- the knee lifting on beat 1;
- accurate third position;
- a strong, extended jeté;
- correct outward rotation;
- good poise.

---

# 6. Final consolidation — 4 minutes

Return to **Argyll Strathspey** or **Out of Thin Air** and dance the final eight bars twice.

### First time
Teacher calls:
- “Prepare.”
- “Shared centre.”
- “Transfer.”
- “Turn together.”
- “Finish.”

### Second time
Dance without calling.

Finish with a brief review:

- Did the dancers enter the tournee in the correct orientation?
- Was the handhold supportive but relaxed?
- Did both partners transfer weight together?
- Was the movement centred rather than pulled around?
- Did the dancers complete the phrase and exit cleanly?

## Teacher’s observation priorities

Because only 45 minutes are available, correct in this order:

1. **Formation and orientation**
2. **Timing and phrasing**
3. **Weight transfer**
4. **Handhold and shared centre**
5. **Foot position and turnout**
6. **Styling and refinement**

Avoid giving several corrections at once. Demonstrate the desired action, have the class repeat it, then immediately put it back into the dance.

#### gpt-5.6-luna+reasoning — PASS (56.4s, 21 tool calls, 50641+5067 tokens)
- ✅ rscds_only: 3 dances linked; non-RSCDS: none
- ✅ min_dance_links: 3 linked (need 3)
- ✅ required_tools: missing: none; used: ['get_dance_detail', 'get_full_crib', 'get_teaching_guidance', 'get_teaching_points_for_dance', 'search_cribs', 'search_manual']
- ✅ expect_any: hits: ['tournée']
- tools: search_cribs, get_dance_detail, get_dance_detail, get_dance_detail, get_dance_detail, get_dance_detail, get_dance_detail, search_cribs, search_cribs, search_cribs, get_full_crib, get_teaching_points_for_dance, get_full_crib, get_teaching_points_for_dance, get_full_crib, get_teaching_points_for_dance, get_teaching_guidance, search_manual, search_manual, search_manual, search_manual

# 45-Minute Advanced Lesson: Developing the Tournée

**Theme:** Smooth, accurate, flowing tournée in strathspey time  
**Class level:** Advanced  
**Dances:** Three RSCDS-published dances, all strathspeys so that the technique can be reinforced consistently  
**Suggested progression:** Begin with the tournée at the end of a 2-couple dance, then practise it in a 3-couple setting, and finish with the more demanding Gaelic Mod, where it occurs in the opening phrase.

The three dances have been checked as RSCDS-published:

- [Alltshellach](https://my.strathspey.org/dd/dance/109/) — RSCDS Book 23
- [Argyll Strathspey](https://my.strathspey.org/dd/dance/221/) — RSCDS Book 35
- [Gaelic Mod](https://my.strathspey.org/dd/dance/2371/) — Imperial Book, Volume 4/5 and More

---

## Learning objectives

By the end of the lesson, dancers should be able to:

1. Enter the tournée from the sidelines without hesitation.
2. Maintain a comfortable promenade hold while travelling anticlockwise.
3. Coordinate the men’s shoulder-to-shoulder start and the partners’ passage across.
4. Release the promenade hold at the correct point, without stopping the flow.
5. Complete the final one-and-a-half turns with accurate hand use and finish on own sides.
6. Preserve strathspey posture, length of step and phrasing while dancing the formation at tempo.
7. Apply the technique consistently in different formations and positions.

---

# Timing overview

| Time | Content |
|---:|---|
| 0:00–0:04 | Warm-up: posture, strathspey travelling step and musical phrasing |
| 0:04–0:12 | Isolated tournée technique and class exercise |
| 0:12–0:21 | Dance 1: Alltshellach |
| 0:21–0:31 | Dance 2: Argyll Strathspey |
| 0:31–0:41 | Dance 3: Gaelic Mod |
| 0:41–0:45 | Final tournée consolidation and recap |

Keep explanations short and use walking stages rather than lengthy verbal descriptions. With an advanced class, correct one point at a time and return quickly to dancing.

---

# 0:00–0:04 — Warm-up and preparation

### 1. Establish the strathspey carriage

Remind dancers:

- Upright, dignified posture without stiffness.
- Weight controlled over the supporting foot.
- Steps should be long and flowing rather than hurried.
- Avoid rising and falling excessively through the body.
- Partners should remain connected without pulling or leaning.

### 2. Strathspey travelling step

Use the rhythmic description:

> **Step, close, step, through.**

The RSCDS manual describes the step as:

- Bend the supporting knee and take the first step forward.
- Close the other foot into third position.
- Take the second step forward with the supporting leg extended.
- Gently draw the rear foot through, with a small, controlled hop as it passes.

For this lesson, particularly observe:

- The first step has length and depth.
- The close is controlled and upright.
- The second step does not collapse at the knee.
- The foot is drawn through smoothly rather than kicked.
- The step remains continuous and elegant.

Have the class travel for four bars, then retire for four bars using:

> **Back, close, back, through.**

---

# 0:04–0:12 — Isolated tournée practice

Arrange the class in 2-couple sets, beginning with the couples on their own sidelines.

The RSCDS manual defines the tournée as an **eight-bar progression in strathspey time**, danced by two couples from the sidelines.

## Tournée: technical breakdown

### Bars 1–2: Entry and promenade hold

- First couple dance towards each other.
- First man pulls back by the left.
- They finish facing their own side, with his partner on his right, in promenade hold.
- Second couple dance towards each other.
- Second woman pulls back by the right.
- They finish facing their own side, with her partner on her left, in promenade hold.

At this point:

- The two couples are in a line up and down the middle.
- The men are left shoulder to left shoulder.
- The promenade hold should be comfortable and clearly established before travelling begins.

**Teaching point:** The entry is not a sharp turn or a sudden change of direction. It should feel like a continuous gathering-in from the sidelines.

### Bars 2–4: Anticlockwise travel

- Both couples dance halfway round anticlockwise.
- The two men bring their partners across in front of them.
- First couple release the right hand.
- Second couple release the left hand.
- Release towards the end of bar 4.

At the end of this section:

- All four dancers are again in a line up and down the middle.
- The women face towards the men’s side.
- The men face towards the women’s side.

**Teaching points:**

- The men guide rather than drag their partners.
- The women travel across the front with confidence and an even step.
- Keep the movement circular; do not cut across the centre too abruptly.
- Do not release the hold early.
- Avoid allowing the promenade hold to become an arm-only connection.

### Bars 5–8: Final turns and exit

- Second couple, with the right hand, and first couple, with the left hand, turn one-and-a-half times.
- Dance out to finish on own sides, having changed places.

**Teaching points:**

- Make the final turn a travelling turn, not a stationary spin.
- Keep the turning hand at a useful height and avoid lifting the arm.
- The final half-turn should place the dancers on their own sidelines cleanly.
- The tournée finishes on the last bar; do not arrive early and wait.
- Partners should emerge with space between them and a clear sense of the next phrase.

## Practice exercise

1. Walk the full eight bars without music.
2. Walk again while the teacher counts:
   - “Gather in”
   - “Round”
   - “Release”
   - “Turn and out”
3. Dance the formation to slow strathspey music.
4. Repeat with the class changing roles and positions.
5. Add the previous and following four bars from Alltshellach to practise the transition into and out of the tournée.

---

# 0:12–0:21 — Dance 1: Alltshellach

**Formation:** Longwise 4 couple, 2-couple dance  
**Purpose:** Establish the tournée after a 16-bar sequence and practise its entry from the sidelines.

## Full crib

> **1–**  
> : 1c+2c set | turn BH, into ; 1c+2c ½Poussette, finishing in the middle, facing down  
> **9–**  
> : 2c+1c lead down the middle ; (2c divides) 1c+2c lead up to (1,2)  
> **17–**  
> : Reel4 across the dance, 1W and 2M pass Lsh to begin, and finish with a loop on own side  
> **25–**  
> : Tournée

## Teaching focus

### Bars 1–8: Half poussette into the middle

This prepares the dancers for the tournée by requiring control of:

- Two-handed connection.
- Strathspey travelling step.
- Smooth directional change.
- Finishing in the middle facing down.

The RSCDS manual describes a strathspey poussette as:

- A two-couple formation beginning from the sidelines.
- Non-progressive.
- Danced with long, sweeping movements.
- Led through the hands rather than pushed through the arms.

Observe the change of foot required by the entry and exit of the poussette. The movement should remain continuous, with no jerking or stopping.

### Bars 9–16: Lead down and up

The manual distinguishes between:

- **“Lead” down the middle:** right hands are used.
- **“Dance” down the middle:** nearer hands are used.

In this dance, make the hand connection and the division of the second couple clear. The first couple should arrive ready for the reel of four, not rush the final travelling step.

### Bars 17–24: Reel of four

The first woman and second man pass left shoulder to begin.

Observe:

- Correct left-shoulder entry.
- Even spacing across the dance.
- A definite loop at the end on own sides.
- The dancers should finish with enough time to prepare for the tournée.

### Bars 25–32: Tournée

Use this dance to reinforce the basic eight-bar technique already practised. The important transition is:

> **Reel of four — loop on own side — gather immediately into the tournée.**

Do not allow the end of the reel to become a pause. The final loop should place dancers naturally on the sidelines and ready to move towards their partners.

## Suggested use of the nine minutes

- **2 minutes:** Explain and walk bars 1–16.
- **2 minutes:** Walk the reel-to-tournée transition.
- **2 minutes:** Dance the tournée alone from the sidelines.
- **3 minutes:** Dance the complete dance twice, focusing first on entry and then on the final turn.

---

# 0:21–0:31 — Dance 2: Argyll Strathspey

**Formation:** Longwise 4 couple, 3-couple dance  
**Purpose:** Transfer the tournée technique to a 3-couple set and develop spatial awareness when other couples are active.

## Full crib

> **1–**  
> : 1c+2c+3c ½ RH turn and remain in middle, swivel R and dance out to opposite side ; repeat, to own places  
> **9–**  
> : 1c+2c+3c Circle6 and back, 1c & 3c finish facing down / up the middle  
> **17–**  
> : 1c+3c R&L up / down, to own places  
> **25–**  
> : 1c+2c Tournée.

## Teaching focus

### Bars 1–8: Half right-hand turns and swivels

The dancers must remain in the middle after each half turn, swivel to the right, and dance out to the opposite side.

This is a useful preparation for the tournée because dancers must:

- Finish each turn with their body already organised for the next direction.
- Avoid opening out too early.
- Maintain even spacing in a crowded 3-couple set.
- Use the supporting foot and torso to turn smoothly.

### Bars 9–16: Circle six and back

The first and third couples must finish facing down and up the middle respectively.

Emphasise:

- A strong but controlled circle.
- No over-travelling on the final step.
- Accurate orientation at the end of the circle.
- Awareness that the tournée uses only the first and second couples.

### Bars 17–24: Rights and lefts

The first and third couples dance rights and lefts up and down the set.

Use the final two bars to prepare the first and second couples for the tournée. The third couple should complete the phrase and remain out of the way without distracting the active couples.

### Bars 25–32: Tournée

The tournée is danced by the first and second couples. In this 3-couple setting:

- The active couples must keep the formation compact and centred.
- The third couple must maintain their place and avoid encroaching.
- The first and second couples should not widen the circular pathway merely because there is more space in the set.
- The finishing places must be unambiguous before the next repetition.

## Suggested use of the ten minutes

- **2 minutes:** Walk bars 1–16 with all three couples.
- **2 minutes:** Practise the ending of the rights and lefts into the tournée.
- **2 minutes:** Dance the tournée with the third couple standing in place.
- **4 minutes:** Dance the complete dance twice, changing lines or positions as necessary.

**Correction priority:** Do not correct every detail simultaneously. First correct the men’s and women’s entry directions; then correct the release and final hand turns.

---

# 0:31–0:41 — Dance 3: Gaelic Mod

**Formation:** Longwise 4 couple, 3-couple dance  
**Purpose:** Challenge advanced dancers by placing the tournée at the beginning and then following it with rapid orientation changes, petronella turns and reels.

## Full crib

> **1–**  
> : 1c+2c Tournée (2,1,3)  
> **9–**  
> : 2c+3c chase 1 place clw **as** 1c petronella, into facing lines3 | All set ; repeat  (3x,1x,2x)  
> **17–**  
> : ½ Reels3 on sides, 1c Rsh to 2cnr (2x,1x,3x) ; ½ Reels3 across. 1c Rsh to 4cnr (2,1,3)  
> **25–**  
> : All M cross & pass behind P Rsh | All M cross back, P loops and starts to follow ; All W pass Rsh behind P and cross to own side (2,1,3)

## Teaching focus

### Bars 1–8: Tournée

This is an excellent final test because dancers must begin the tournée immediately and finish in the progressed order:

> **(2,1,3)**

Check that:

- First and second couples identify themselves before the music starts.
- The entry begins from the sidelines.
- The men’s left-shoulder-to-left-shoulder alignment is maintained.
- The couples travel anticlockwise without breaking the circular flow.
- The final turns finish decisively on own sides.
- The progression is completed before bar 9.

### Bars 9–16: Chase and petronella

The second and third couples chase one place clockwise as the first couple dances petronella, ending in facing lines of three.

The RSCDS manual describes petronella as a two-bar turning movement on the diagonal:

- It turns to the right.
- It uses two setting steps.
- It may travel from the sidelines to the centre or from the centre to the sidelines.
- It may be preceded or followed by setting.

The advanced challenge is the simultaneous contrast between the chasing couples and the petronella couple. Stress that dancers should know their pathway rather than react to neighbouring dancers.

### Bars 17–24: Half reels of three

- Half reels of three on the sides.
- First couple pass right shoulder to second corners.
- Half reels of three across.
- First couple pass right shoulder to fourth corners.

Observe:

- The first couple’s right-shoulder passes.
- Correct corner identification after the progression.
- Reels should remain compact and rhythmically even.
- Avoid allowing the tournée’s circular feeling to carry into the reels and distort the straight reel pathways.

### Bars 25–32: Men’s and women’s crossing sequence

The men cross and pass behind their partners right shoulder. They cross back while partners loop and begin to follow. The women then pass right shoulder behind their partners and cross to own sides.

This final phrase requires precise orientation and should be walked once if the class is not already familiar with the dance.

## Suggested use of the ten minutes

- **2 minutes:** Walk the tournée into the progressed order.
- **2 minutes:** Walk the transition from the tournée to chase/petronella.
- **2 minutes:** Dance the first 16 bars twice.
- **2 minutes:** Add bars 17–32.
- **2 minutes:** Dance the complete dance once or twice, depending on confidence.

If time is short, prioritise a successful first 16 bars over repeatedly dancing the entire dance.

---

# 0:41–0:45 — Final consolidation

Return to 2-couple sets and dance the tournée several times without the rest of the dances.

Use the following sequence:

1. **Once slowly:** Teacher counts and names the phases.
2. **Once to music:** Teacher coaches minimally.
3. **Once at performance tempo:** No verbal intervention unless necessary.

## Final checklist

Ask dancers to self-assess:

- Did we begin from the correct sidelines?
- Were the men left shoulder to left shoulder after the entry?
- Did we maintain a true anticlockwise curve?
- Did we bring partners across rather than pull them?
- Did we release hands near the end of bar 4?
- Did the final one-and-a-half turns travel out to own sides?
- Did we finish on the last bar rather than early?
- Did the movement retain strathspey flow and dignity?

## Main faults to watch for

- Entering the middle too sharply and losing the circular shape.
- Men pulling partners across instead of guiding them.
- Women stepping too far ahead of the men.
- Releasing promenade hold too early.
- Turning on the spot in bars 5–8.
- Lifting the turning arm or bending the elbow excessively.
- Finishing early and waiting for the phrase.
- Leaning into the partner instead of maintaining independent posture.
- Allowing the tournée to become cramped in a 3-couple set.

The central correction throughout the lesson is:

> **Keep the tournée flowing: gather, travel round, release, turn and travel out—without stopping between phases.**

