# Hermes v2 → v2.1 Roadmap

**Date:** 2026-06-01 (revised from 2026-05-31)
**Reviews:** Musk + Karpathy architecture review
**Current state:** 7-stage pipeline working end-to-end (~185s), 4 conclusions from 21 analyzed items, evidence-based confidence (43-50%), web UI with evidence drawer, cross-domain edges, graceful degradation

---

## What's Done (since v2 plan)

| Phase | Item | Commit | Status |
|-------|------|--------|--------|
| 0.1 | Open all RSS sources (13/13 enabled) | config.yaml | Done |
| 0.2 | Cron trigger (`hermes cron`, trigger_type) | 7fd6fba | Done |
| 0.3 | Merge prefilter+analyze+postfilter → unified assess | assess.py | Done |
| 0.4 | Parallelize per-item LLM calls (8 workers) | assess.py | Done |
| 0.5 | Remove Obsidian vault reader | 7fd6fba | Done |
| 1.1 | Cross-run conclusion semantic matching | 82a6583 | Done |
| 1.2 | `hermes audit` CLI + manual grading | 82a6583 | Done |
| 2.1 | Surprise score computation | run.py Stage 4.5 | Done |
| 2.5 | Evidence decomposition with counter-arguments | f255ebc | Done |
| 3.2 | Prompt regression testing (10 assess + 4 synth fixtures) | 2b4aa1c | Done |
| — | Cross-domain semantic edges in knowledge graph | app.js (uncommitted) | Done |
| — | Graceful DB degradation (all API endpoints) | app.py (uncommitted) | Done |
| — | Related items in evidence drawer | app.js (uncommitted) | Done |
| 1.3 | Fix domain classification (`_match_domain`) | assess.py (uncommitted) | Done |

---

## Phase 1: Make It Produce Real Value (next 2 weeks)

Goal: Musk's question — "Has this system ever produced a conclusion that changed your mind?" If not, it's an expensive RSS reader.

### 1.1 Conclusion quality metric (NEW — highest priority)

**Why:** Musk: "4 conclusions at 43-50% confidence. That's worse than a coin flip. If accuracy is below 70%, fix prompts before adding any features." Karpathy: "The march of nines for intel quality — you need to know if a 50% confidence conclusion actually holds up."

**What:**
- After each pipeline run, manually review 2 random conclusions:
  - Read the original source articles
  - Grade each conclusion: correct / partially_correct / incorrect / unverifiable
- Track ratio over time in a simple log file or DB table
- Target: >70% correct-or-partial rate before Phase 2
- If ratio < 70%: stop feature work, iterate on assess prompt, re-audit

### 1.2 Grow the prompt regression fixture set

**Why:** Karpathy: "10 fixtures is a start. The test set should grow with the system." Every run produces analyzed items — some are clearly right, some are clearly wrong. Both belong in the test set.

**What:**
- After each run, flag 1-2 items as "good analysis" or "bad analysis"
- Add good ones as positive fixtures, bad ones as negative fixtures (expected to catch specific errors)
- Add to `tests/fixtures/` with manual annotation of expected output
- Target: 30+ assess fixtures by end of Phase 1
- Run `hermes test-prompts` before every prompt change

### 1.3 Commit and deploy current uncommitted work

**Why:** Domain classification fix, cross-domain edges, graceful degradation, and related items drawer are all working but uncommitted. Ship them.

**What:**
- Review uncommitted changes in assess.py, app.py, app.js, index.html
- Write/update tests for domain matching and cross-domain edges
- Commit as a single changeset

---

## Phase 2: Surprise and Discovery (2-3 weeks)

Goal: Karpathy's "sort by loss descending" — the most valuable intel is what you didn't know to look for.

### 2.1 Upgrade surprise score from vector-only to LLM-informed

**Why:** Current `surprise = 1 - max(cosine similarity)` only measures embedding distance. Real surprise = new info that contradicts beliefs or reveals an untracked dimension. Karpathy: "Vector distance is not surprise. Let the LLM tell you what's surprising."

**What:**
- Add `surprise_rationale` field to assess prompt output: "What about this information challenges conventional understanding or existing conclusions in this domain?"
- Blend quantitative surprise (vector distance) with qualitative surprise (LLM judgment)
- Expose in web UI: show surprise rationale alongside surprise score
- Items with high qualitative surprise get priority in synthesize stage

### 2.2 Build the prediction dashboard

**Why:** Backtester exists but has no UI. Predictions are being stored but invisible. You can't calibrate confidence without a feedback loop.

**What:**
- Add `/predictions` page to web UI:
  - Pending predictions sorted by deadline (countdown)
  - Verified predictions with result badges (correct/incorrect/partial)
  - Simple accuracy stat: "X of Y predictions correct"
- After 3-4 weeks of accumulation, compute first accuracy numbers
- If prediction accuracy correlates with analysis confidence → confidence scores have meaning
- If not → recalibrate confidence formula

### 2.3 Enrich synthesize with contradiction detection

**Why:** Current synthesize looks for thematic clusters. But the most valuable synthesis is when two sources disagree. Karpathy: "Finding where sources contradict each other is more valuable than finding where they agree."

**What:**
- During synthesize, for each cluster, ask LLM: "Do any items in this cluster contradict each other? Are there opposing viewpoints?"
- Surface contradictions explicitly in the theme output (already have `counter_evidence` field, use it more aggressively)
- In web UI: highlight contradictory items in the conclusion evidence drawer

---

## Phase 3: Calibration & Trust (ongoing, starts after Phase 1)

Goal: Know whether the system's confidence numbers mean anything. This is Karpathy's march of nines.

### 3.1 Confidence calibration tracking

**Why:** Karpathy: "Does a 50% confidence conclusion actually hold up 50% of the time? You won't know until you verify. Track from day one."

**What:**
- After Phase 1.1 establishes baseline accuracy, start bucketing conclusions by confidence
- Track: 0.3-0.5 bucket accuracy vs 0.5-0.7 vs 0.7+
- If low-confidence bucket has high accuracy → system is underconfident
- If high-confidence bucket has low accuracy → system is overconfident
- Add `/api/calibration` endpoint with calibration plot data

### 3.2 Prompt drift detection (lightweight)

**Why:** LLM behavior changes over time. But with daily runs and small sample size, statistical monitoring won't catch drift for weeks. Karpathy: "The test fixtures are your drift detector."

**What:**
- Run `hermes test-prompts` weekly, log scores
- If any fixture score drops >1 point from baseline → investigate
- Simple: log token count, JSON parse failure rate, confidence distribution per run
- Skip the 2σ statistical approach until you have 60+ runs of data
- `hermes health` already exists — add fixture score trend to its output

---

## Phase 4: Entity Resolution (deferred until 200+ analyzed items)

**When:** After Phase 2, only if item count justifies it.

### 4.1 Lightweight entity resolution

**Why:** "OpenAI" and "OpenAI Inc." are different strings in JSONB. But Musk: "Don't build entity resolution before you have enough entities to resolve." Target: 200+ analyzed items before starting.

**What:**
- `entities` table (name, canonical_name, type)
- `item_entities` join table
- Normalize: lowercase, strip suffixes (Inc., Ltd., Corp.)
- Fuzzy match within same type
- Entity page in web UI: click entity → all items + conclusions

---

## What NOT to do (reinforced)

- **Don't add more pipeline stages.** Musk: "7 stages is already complex. Merge, don't add."
- **Don't optimize for scale.** Single user, ~50 items/day. No Redis, no message queues, no microservices.
- **Don't add UI features before data quality is proven.** Musk: "4 conclusions on a graph with domain color coding. The graph is empty. Stop styling nodes." Fix the conclusion count and quality first.
- **Don't automate the human out of the loop.** Karpathy: "Iron Man suit, not Iron Man robot." The user should confirm, challenge, and guide conclusions. The system is an intelligence amplifier, not a replacement.
- **Don't trust LLM confidence numbers without calibration.** A confidence of 0.43 vs 0.50 is floating-point noise until you have verified outcomes.
- **Don't add entity resolution yet.** Wait until 200+ analyzed items.
- **Don't go past 2 weeks without verifying conclusion quality manually.** Phase 1.1 is the most important task. If the LLM is hallucinating analysis, everything built on top is garbage.

---

## Revised Timeline

| When | What | Effort | Impact |
|------|------|--------|--------|
| **This week** | Commit uncommitted work (domain fix, cross-domain edges, graceful degradation) | 1 hr | Bug fixes shipped |
| **This week** | Phase 1.1: Conclusion quality metric + manual review process | 1 hr setup + 30 min/run | Trust in output |
| **Week 1-2** | Phase 1.2: Grow fixture set to 30+ | 2 hrs | Prompt change safety |
| **Week 2-3** | Phase 1.3: Fix prompts if accuracy < 70% | 2-4 hrs | Core quality |
| **Week 3-4** | Phase 2.1: Upgrade surprise score | 3 hrs | Find what you missed |
| **Week 3-4** | Phase 2.2: Prediction dashboard | 2 hrs | Close feedback loop |
| **Week 4-5** | Phase 2.3: Contradiction detection in synthesize | 2 hrs | Richer synthesis |
| **Week 5+** | Phase 3.1: Calibration tracking | 2 hrs | Confidence meaning |
| **Week 5+** | Phase 3.2: Lightweight drift detection | 1 hr | Catch silent degradation |
| **Deferred** | Phase 4: Entity resolution | 4 hrs | Wait for 200+ items |
