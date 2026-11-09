# Vidroa — Code Audit: Why Image Prompts Don't Match the Narration

**Date:** 2026-11-09
**Scope:** Read-only audit of the prompt-generation pipeline in `~/workspace/vidroa`. No code was edited.
**User-reported symptom:** image prompts are low quality — images irrelevant, not matching the narration.
**Verdict:** The symptom is real and structural, not a tuning issue. There are **three independent root causes**, any one of which alone produces mismatched images:
1. **Scene boundaries cut narration mid-sentence** in both live code paths, so the "exact narration moment" a prompt is supposed to depict is often a sentence fragment.
2. **No part of the pipeline ever checks narration↔prompt alignment** — the audit that is supposed to catch mismatches is hard-coded to one specific story (Caesar/Constantinople) and is blind to generic mismatches.
3. **The quality gate does not block anything** — a failed audit still ships, and the job is marked COMPLETED as long as any scenes exist.

On top of that, the tuned system-prompt file for the prompt-generation stage is loaded and then never used, and the two desktop code paths diverge so that the "Generate" button can silently skip the two planning stages entirely.

---

## 0. Which code path the user actually hits

There are **two live planning paths**, and which one runs depends on which UI button the user pressed first.

**Path A — "Plan Storyboard & Build Bible" first, then Generate (the intended path)**
- `app/ui/main_window.py:1898-1911` — button 1 launches `ParallelPipelineWorker`.
- `app/ai/parallel_pipeline_worker.py` — runs Stage 1 analysis → Stage 2 continuity save → **Stage 3 visual planning** → **Stage 4 temporal scheduling** → approval grid. Scenes land in `project.state.scenes`.
- `app/ui/main_window.py:2057-2078` — button 2 launches `CloudJobWorker` with `scenes_to_generate=self.project.state.scenes`.
- `app/ai/job_worker.py:166-167` — pre-planned scenes are used as-is; Stage 2 is skipped.

**Path B — Generate without planning first (the silent fallback)**
- `app/ai/job_worker.py:176` — if `scenes_to_generate` is empty, the worker runs the **old `Stage2Planner`** instead, and **skips Stage 3 and Stage 4 entirely**.
- The user gets no warning that a different, older planner ran.

Both paths then converge on Stage 5 (prompts) → Stage 6 (audit) → Stage 7 (replan, max 3 rounds) → Stage 8 (validation) → COMPLETED.

The backend-API orchestrator (`backend/pipeline/orchestrator.py`) is a third path used only by the API (`backend/api/router.py:167`); the desktop app never calls it.

---

## 1. Findings

### F1 — HIGH — Stage 5's tuned system prompt is loaded and then never passed to the model
- **File:** `backend/pipeline/stage5_prompts.py:121, :250, :305`
- **What happens:** `execute()` calls `load_system_prompt()` at line 121, which reads `config/system_prompts/stage4_prompts.txt` into a local variable `system_prompt`. That variable is **never referenced again**. The batch generation call at line 250 passes a hardcoded one-liner instead: `system_prompt="You are a master AI video prompt architect. Output strictly valid JSON only."` The single-scene retry at line 305 passes an even thinner hardcoded string: `"Output strictly valid JSON only."`
- **Why it hurts:** Whatever style, grounding, and quality rules were written into `stage4_prompts.txt` have zero effect on the prompts the user actually gets. The model is instructed only to "output JSON" — nothing about depicting exactly the spoken words, nothing about the visual style, nothing about continuity. This is the single most direct cause of generic/irrelevant prompts.
- **Severity:** High

### F2 — HIGH — Nothing anywhere checks whether a prompt matches its narration
- **File:** `backend/pipeline/stage6_audit.py:65, :100-105, :151-470, :505-530`
- **What happens:** The audit is the only alignment checkpoint, and it has no generic narration↔prompt check:
  - The LLM audit sees only truncated excerpts — `narration[:70]`, `visual_subject[:50]`, `prompt[:70]` (line 65) — with `max_tokens=850` for the **entire** storyboard's audit JSON (lines 100-105). For a 20+ scene board the JSON is almost certainly truncated, and `repair_and_parse_json` silently recovers only the completed elements.
  - Every deterministic check is hard-coded to Caesar/Constantinople specifics: cannon-cluster counting (lines 151-165), cannon+wall pairs (185-196), cannon windows (223-246), premature wall breach (258-272), Mehmed-intro detection (274+), premature overland-ship transport (~380), premature discarded insignia/crown (~400), anachronism keywords (`tokyo`, `laser`, `neon skyscrapers`, `denim`, `holographic`, `astronaut`, ~420), stickman style phrases (~440). For any other story these are no-ops.
  - The only token-overlap check compares **consecutive visual_subjects** (repetition), never narration vs prompt.
  - Worse, LLM-suggested repairs are **discarded unless a deterministic check already flagged that same scene** (merge loop ~505-512: a repair is accepted only `if has_issue` from the deterministic findings). So even if the LLM spots a mismatch, no repair is produced for it.
- **Why it hurts:** A prompt that depicts something entirely different from its narration (sample scene 007: narration about doors, prompt about a man on a mattress) passes the audit by construction. There is no mechanism in the codebase that could ever catch it.
- **Severity:** High

### F3 — HIGH — A failed audit never blocks delivery; the job is COMPLETED anyway
- **File:** `app/ai/job_worker.py:292-294, :343-393`; `backend/pipeline/orchestrator.py:212-214, :264-293`; `backend/pipeline/stage8_validation.py:217-222`
- **What happens:** Both the desktop worker and the backend orchestrator replan at most 3 rounds (`max_rounds = 3`, `while audit_report.final_recommendation != "APPROVED" and repair_rounds < max_rounds`), then proceed to Stage 8 regardless of the audit outcome. Stage 8's `is_valid` (stage8_validation.py:217-222) only checks: no scene >10.5s, no overlaps, no duplicate boundary words, no disk failures. It does **not** include the audit score, alignment, or prompt quality. And the release gate itself only fails when `current_scenes` is empty (job_worker.py:354-375, orchestrator.py:264-280) — `is_valid=False` merely changes a status message from "Quality score: …" to "Pacing: …". The job is then marked `COMPLETED` at 100%.
- **Why it hurts:** The audit is advisory theatre. A storyboard full of mismatched prompts ships with a success message, so the user has no signal that anything went wrong until they look at the images.
- **Severity:** High

### F4 — HIGH — Scene boundaries cut narration mid-sentence in BOTH paths
- **File (Path A):** `backend/pipeline/stage4_scheduling.py:149-155, :295-301, :350-430`
- **File (Path B):** `backend/pipeline/stage2_planning.py:100-140, :331-332, :349`
- **What happens:**
  - **Stage 4, word-timestamp path:** beat→word-range mapping matches only the **last word** of the beat text within a search window (lines ~139-147). On no match it allocates proportionally — `allocated = max(4, rem_words // rem_beats)` (lines 149-155) — an arbitrary word-count cut with no sentence awareness.
  - **Stage 4, tail split:** if the final scene exceeds 8.00s it is split at the **word-count midpoint** `w_mid = len(l_words) // 2` (lines 295-301) with **no punctuation check at all** — a pure mid-sentence cut.
  - **Stage 4, no-timestamps path:** `_schedule_proportional_with_caps` (lines 350-430) splits beats by pure word-count arithmetic, `beat_words[p*sub_len:(p+1)*sub_len]` (line ~381). Also note line ~381: if a beat has no exact narration segment it falls back to `story_text[:100]` — the **first 100 characters of the whole story** as that scene's narration.
  - **Stage 2 (Path B):** `split_long_scene` (lines 100-140) splits long scenes by **equal time slices**; the narration excerpt comes from `get_excerpt_by_time`, i.e. whatever words fall in that time window — mid-sentence by design. The LLM fallback truncates the excerpt to 80 chars (`narration_excerpt = chunk_excerpt[:80]`, line 331) with a generic subject `f"{subject_preset.name} scene beat"` (line 332).
  - **No completeness check exists anywhere:** `narration_text` is just `" ".join(words in range)`; no stage verifies a scene's narration is a complete, speakable unit ending at a sentence/clause boundary.
- **Why it hurts:** A prompt can only match its narration if the narration is a coherent moment. When scene 003's narration is "Below on Elm Street they wander in stuttering," (ends mid-sentence, comma) and scene 004 continues "lurching rhythms, … You", the model is asked to illustrate a fragment — and the fragment's continuation is a different scene's prompt. Mismatch is baked in before prompt generation starts.
- **Severity:** High

### F5 — HIGH — Token budget too small for the batch; truncation silently degrades to generic fallbacks
- **File:** `app/ai/groq_engine.py:233-235, :239`; `backend/pipeline/stage5_prompts.py:118, :174-175, :246-252, :320-360`; `backend/pipeline/stage3_visual_planning.py:180-181`; `backend/pipeline/stage6_audit.py:100-105`
- **What happens:** `GroqEngine.generate_text` caps `max_tokens` at **950 for all qwen models** (lines 233-235, comment "Qwen OTPM limit is 1000"). Stage 5 asks for 1024 tokens for a **4-scene batch** of full image prompts (batch_size clamped to 2–4, lines 118/174-175) — capped to 950. Four production-ready prompts at ~150-200 words each need ~800-1,200 tokens **of output alone**, before JSON scaffolding. Stage 3 asks 850 tokens for **3 beats × 7 fields**; Stage 6 asks 850 tokens for a **whole-storyboard audit JSON**. When output is truncated, `repair_and_parse_json` silently recovers only the completed JSON elements, and every missing scene/beat is filled with a generic template instead of erroring (stage 5 fallback lines 320-360; stage 3 fallback lines 196-214).
- **Why it hurts:** The pipeline's failure mode for "model ran out of tokens" is indistinguishable from success — the user gets plausible-looking but generic prompts (see F6) with no warning. This is the mechanism that turns a token ceiling into "irrelevant images".
- **Severity:** High

### F6 — HIGH — Fallback prompts are generic keyword-matched templates, not narration-grounded
- **File:** `backend/pipeline/stage5_prompts.py:78-110, :320-360`; `backend/pipeline/stage3_visual_planning.py:196-214`; `backend/pipeline/stage4_scheduling.py:26-57`
- **What happens:**
  - `derive_contextual_environment` (stage5:78-110) picks the environment by keyword matching on the narration: senate/curia/pompey → Roman Senate; street/forum/crowd → Roman forum; nightmare/domus/bed → Roman house; rubicon/battle → "Panoramic vista of classical territories"; constantinople/byzantine → Theodosian walls; **anything else → `f"Authentic {period} setting with period architecture and atmospheric lighting"`**. A zombie story, a Dorothea Dix story, any non-Roman/non-Constantinople story mostly lands in the generic branch.
  - The stage-5 fallback prompt (lines 320-360) is assembled as `"{style} aesthetic. {env}. Action: {subj}. {comp}, authentic historical period details, cinematic lighting."` — a fill-in-the-blank, not a description of the moment.
  - Stage 3's missing-beat fallback is `primary_visual_concept: "Historical scene depicting {u_text[:70]}"` (line 199).
  - `derive_progressive_subsegment_concept` (stage4:26-57) builds sub-segment concepts from the **first 5 words longer than 3 characters** of the segment — e.g. "Dramatic focal perspective highlighting {first 5 long words}". Keyword salad, not a visual concept.
- **Why it hurts:** Whenever the LLM path truncates, fails, or a scene is split, the prompt that reaches the image generator is a generic template with the narration's keywords sprinkled in. That is exactly "image not matching the narration".
- **Severity:** High

### F7 — MED — Two divergent planning paths; the default Generate silently skips Stages 3+4
- **File:** `app/ai/job_worker.py:166-176`; `app/ui/main_window.py:1898-1911, :2057-2078`
- **What happens:** See §0. If the user clicks Generate without first running "Plan Storyboard & Build Bible", `CloudJobWorker` runs the old `Stage2Planner` and never touches the newer Stage 3 visual planner or Stage 4 temporal scheduler. There is no UI indication of which planner ran.
- **Why it hurts:** The user can get two completely different qualities of output from the same button depending on invisible prior state. Worse, Path B is the weaker path (time-based splits, no word indices — see F10), so the "just press Generate" flow is the one most likely to produce the reported symptom.
- **Severity:** Medium

### F8 — MED — Stage 3 visual concepts get thin context: last 2 beats, 60 chars each
- **File:** `backend/pipeline/stage3_visual_planning.py:38-39, :123-129, :141-143`
- **What happens:** Each planning batch sees only the previous **2 beats' concepts, truncated to 60 characters each** (lines 123-129). The character bible is truncated to 6 characters with appearance cut to 80 chars, locations to 4 (lines 38-39). The prompt's own fallback context strings are Roman defaults: `'Historical figures and senators'`, `'Ancient Roman locations'`, era default `"Ancient Roman Republic (44 BC)"` (lines 40, 141-143).
- **Why it hurts:** The visual planner cannot maintain continuity or ground a concept in the story's actual characters/settings beyond a 60-char glimpse of the last two beats. Concepts drift generic and repeatable across beats.
- **Severity:** Medium

### F9 — MED — Hard-coded Caesar/Constantinople leakage in prompts, bibles, and checks
- **File:** `backend/pipeline/stage5_prompts.py:46, :226`; `backend/pipeline/stage3_visual_planning.py:150-157`; `backend/pipeline/stage1_analysis.py:1-36` (inline `STAGE1_SYSTEM_PROMPT`); `backend/pipeline/stage7_replanning.py` (Cimber guard, `int(sid) < 46`); `backend/pipeline/stage1_analysis.py` (fallback bibles); `app/models/planning.py` via `to_script_analysis` (hard-coded `high_risk_repetition_concepts: ["Identical military formations", "Unchanged wall ruins"]`)
- **What happens:** Story-specific rules leak into shared code at every stage: stage 5's batch prompt forbids "premature reveals of overland ship transport or discarded crowns" (line 226) for **every** story; stage 3's user prompt contains Caesar/Rome and Constantinople spoiler rules (lines 150-157); `resolve_stickman_characters` defaults the protagonist to **"Caesar"** (stage5:46) and hard-codes Brutus/Cassius/Casca names in its docstring/rules; stage 1's fallback bibles are hard-coded Constantinople / Cortés / Dorothea character and location lists chosen by keyword match, with a generic "Narrative Protagonist" / "Central Historical Setting" fallback for everything else; stage 7 rejects repairs mentioning "Cimber … daggers concealed" for scene IDs < 46.
- **Why it hurts:** For any story that is not Caesar or Constantinople, these rules are noise that consumes prompt tokens and can actively misdirect the model (e.g. a "discarded crown" rule in a zombie story); for the two hard-coded stories they are brittle magic numbers. It also means the pipeline was effectively built and tested against one story, and every other story runs on the generic fallback paths (F6).
- **Severity:** Medium

### F10 — MED — Word indices that would prove prompt↔narration coverage are empty in Path B, and the conversion can substitute action text for narration
- **File:** `app/ai/job_worker.py:214, :219`; `app/models/scene.py:77-78`; `app/models/planning.py:112-126`; `backend/pipeline/stage4_scheduling.py:283-284`
- **What happens:** `VisualScene` has `start_word_index` / `end_word_index` fields (scene.py:77-78) and `ScheduledScene` has `source_word_start` / `source_word_end` (planning.py:125-126) — the fields exist to prove a prompt covers exactly its narration. Stage 4 populates them (stage4:283-284) and the parallel worker passes them through, so Path A has them. But `Stage2Planner` **never sets them**, so in Path B the job-worker conversion passes `getattr(s, "start_word_index", None)` → `None` (job_worker.py:219). The same conversion does `narration_text = s.narration_excerpt or s.action` (line 214) — if the excerpt is empty, the **action description is silently used as if it were narration**, so the prompt is then "grounded" in its own action text instead of the script.
- **Why it hurts:** There is no auditable link between a prompt and the exact words it should depict in the most common path, and the fallback actively masks missing narration instead of failing loudly.
- **Severity:** Medium

### F11 — MED — Stage 1 bible is real, but Stage 5 truncates it and Stage 3 truncates it further
- **File:** `backend/pipeline/stage5_prompts.py:165-170`; `backend/pipeline/stage3_visual_planning.py:38-39`; `backend/pipeline/stage1_analysis.py:221`
- **What happens:** Stage 1 does build a real continuity bible (characters, locations, objects, time period) and its system prompt **is** correctly loaded and passed (`stage1_analysis.py:221`, `load_stage1_system_prompt()`). But downstream, stage 5 uses only the **first 6 characters and first 4 locations** (stage5:165-170), and stage 3 cuts each character's appearance to 80 chars (stage3:38-39). The bible also exists as saved `.txt` files (`save_story_bibles`) that no prompt-generation stage ever reads back.
- **Why it hurts:** Character/location consistency — the thing the bible exists for — is mostly discarded before prompt generation, so recurring characters drift between scenes.
- **Severity:** Medium

### F12 — MED — Stage 7 replan can only repair what the deterministic checks already flagged
- **File:** `backend/pipeline/stage7_replanning.py:59` (prompt file IS loaded and used); merge-gate in `backend/pipeline/stage6_audit.py:505-512` (see F2); `backend/pipeline/stage7_replanning.py` fallback repair block
- **What happens:** Stage 7 itself is correctly wired (its system prompt file `stage6_replanning.txt` is loaded at line 59 and passed to the model), and its repair prompt includes the full narration of failing scenes. But it only receives scenes from `audit_report.scene_repairs`, which — per F2 — can only contain scenes the Caesar-specific deterministic checks flagged (LLM repairs are gated out). Its own deterministic fallback repair rebuilds prompts from the same generic templates (`derive_contextual_environment` + `sanitize_action_summary` + "Action: {concept}").
- **Why it hurts:** The repair loop spends up to 3 rounds "fixing" scenes while being structurally unable to address the actual defect class (narration↔prompt mismatch), then the pipeline ships anyway (F3).
- **Severity:** Medium

### F13 — LOW — Dead code and dead prompt files create a false sense of coverage
- **File:** `backend/pipeline/stage4_validation.py` (no callers — only imported in `backend/pipeline/__init__.py:7,14`); `config/system_prompts/stage4_validation.txt` (never loaded by any code); `config/system_prompts/stage3_scheduling.txt` (loaded by `stage4_scheduling.py:16-17`, `load_system_prompt()` never called); `config/system_prompts/stage5_validation.txt` (loaded by `stage6_audit.py:24-25`, never called); `app/ai/prompt_builder.py:61` `build_stage2_prompt` (no callers anywhere); `backend/pipeline/stage3_prompts.py` (`Stage3PromptGenerator`, the better bible-aware 50-90-word prompt builder) is used **only** for single-scene regeneration (`app/ai/job_worker.py:456`, `backend/api/router.py:242`, `backend/pipeline/stage4_validation.py:62`) — never for batch generation.
- **What happens:** Four prompt files and a whole validation stage exist but never run. The best prompt builder in the codebase (`Stage3PromptGenerator`) is not the one batch generation uses.
- **Why it hurts:** Anyone reading the repo (or the prompt files) reasonably assumes these quality controls are live. They are not. Fixes applied to the dead files change nothing.
- **Severity:** Low (as a defect class; the underlying live defects are rated above)

### F14 — LOW — Model and engine notes (verified, not defects — but easy to misread)
- **File:** `app/ai/groq_engine.py:18, :194`; `backend/inference/engine.py:370-390`; `app/ai/job_worker.py:97, :435`; `config/models.json`
- **What happens:**
  - The default model `qwen/qwen3.8-27b` **is a real Groq model** (verified against Groq docs 2026-11-09: Qwen 3.8 27B, Preview, 131K context, 16,384 max completion tokens). It is **not** a typo for qwen3-8b/qwen3-32b. Note it is a Preview model and its free-tier output-token-per-minute limit is low (~8K TPM on the Developer plan), which is why the 950-token cap in `groq_engine.py:233-235` exists.
  - Both desktop paths use `GroqInferenceEngine` (backend/inference/engine.py:370), which wraps `app/ai/groq_engine.py`'s `GroqEngine` — so the 950-token cap **does** apply to the desktop flow. Temperature defaults: 0.4 in `GroqInferenceEngine`, but every stage passes an explicit temperature (0.2-0.3), so the default rarely matters. Multi-key rotation with cooldown, `max_attempts = max(15, num_keys*3)`, 120s wait budget, then fallback to `openai/gpt-oss-120b` / `openai/gpt-oss-20b` (groq_engine.py:239, 417-426).
  - `config/models.json` lists Modal vLLM models (Qwen3-30B-A3B etc.) and is **not** used by the Groq desktop path; the Groq model is hard-coded in three places (groq_engine.py:18/194, engine.py:370, job_worker.py:97/435).
  - Footnote: `OpenAICompatibleInferenceEngine.generate_text` (backend/inference/engine.py:336-353, the Modal path) drops the `system_prompt` entirely — only the user message is sent. Not on the Groq desktop path, but the same class of bug as F1 if the Modal path is ever used.
- **Severity:** Low (informational; the token cap itself is F5)

---

## 2. Sample-output verification (`image_prompts.txt`, read back)

Parent finding (4) confirmed, and the mismatch is worse than one scene:

| Scene | Narration (as shipped) | Problem |
|---|---|---|
| 003 | "Below on Elm Street they wander in stuttering," | Ends mid-sentence with a comma. |
| 004 | "lurching rhythms, guided only by the lingering memory of hunger. You" | Starts mid-sentence; ends with the fragment "You". |
| 006 | "It's the sound of their fingernails absent mindedly scraping against locked screen" | Ends mid-sentence ("screen" with no object). |
| 007 | "doors, endlessly testing for a seam." | Fragment continuing scene 006's sentence. **Prompt shows the protagonist lying motionless on a bare mattress in a dim room** — the narration is about doors/fingernails testing seams; the prompt depicts a man on a mattress. Direct narration↔prompt mismatch. |

Scene 007 would **pass the Stage 6 audit**: the LLM audit input truncates the prompt to 70 chars (`"Layered paper-cutout illustration, wide establishing shot of a dimly lit interior ro…"`, stage6_audit.py:65) — the word "mattress" never reaches the auditor — and no deterministic check fires for it (no cannon/breach/Mehmed/crown/anachronism keywords).

---

## 3. Prompt-file liveness map (`config/system_prompts/`)

| File | Loaded by | Actually used? |
|---|---|---|
| `stage1_analysis.txt` | `stage1_analysis.py:221` via `load_stage1_system_prompt()` | **Yes** |
| `stage2_planning.txt` | `stage3_visual_planning.py:36` | **Yes** (stage 3). Also loaded by `prompt_builder.py:61` (`build_stage2_prompt`) — dead, no callers. |
| `stage3_prompts.txt` | `prompt_builder.py:106` | **Yes, but only for single-scene regeneration** (`Stage3PromptGenerator`), never for batch generation. |
| `stage4_prompts.txt` | `stage5_prompts.py:121` | **No — loaded into a local variable never passed to the model** (F1). |
| `stage3_scheduling.txt` | `stage4_scheduling.py:16-17` | **No — `load_system_prompt()` never called.** |
| `stage5_validation.txt` | `stage6_audit.py:24-25` | **No — `load_system_prompt()` never called;** a hardcoded auditor prompt is used instead (stage6_audit.py:54-57). |
| `stage6_replanning.txt` | `stage7_replanning.py:59` | **Yes** |
| `stage4_validation.txt` | Nothing | **Dead file** (and `stage4_validation.py` itself has no callers). |
| `base_system.txt` | `prompt_builder.py` | Only via prompt_builder. |

Pattern: three of the four "load but don't use" cases follow the same shape — a `load_system_prompt()` that reads the file, with the call site either missing or its result discarded. Any fix should grep for all of them, not just stage 5.

---

## 4. Prioritized fix list (max 8)

**Fix 1 — Pass the loaded system prompt to the model (F1).**
In `backend/pipeline/stage5_prompts.py`, use the `system_prompt` variable from line 121 in the `engine.generate_text()` calls at lines 250 and 305 instead of the hardcoded strings. Same one-line fix in `backend/pipeline/stage6_audit.py` (use the loaded `stage5_validation.txt` at the call at lines 100-105 instead of the hardcoded `auditor_system_prompt` at lines 54-57), and call `load_system_prompt()` in `backend/pipeline/stage4_scheduling.py` if stage 4 ever needs an LLM call. Then delete or rewrite `stage4_prompts.txt` so it contains the *actual* prompt-generation instructions (ground in the exact narration moment, no premature reveals, style + continuity rules) — currently it is unclear whether its contents are even the right instructions, since nothing ever executed them.

**Fix 2 — Make scene boundaries sentence-aware, and verify it (F4).**
Add a single post-scheduling assertion, run in both paths: every scene's `narration_text` must end at a sentence/clause boundary (`. ! ? , ; :` or end-of-script) and must not start mid-word. Enforce it where splits happen: replace the word-midpoint tail split (`stage4_scheduling.py:295-301`) and the proportional arithmetic split (`stage4_scheduling.py:350-430`) with the same punctuation search already used for long beats (lines ~185-200: search ±3-4 words for punctuation, with the disallowed-tail guard); do the same for `split_long_scene` in `stage2_planning.py:100-140` (split on word boundaries from `narration.get_excerpt_by_time`, falling back to the nearest preceding punctuation, never an equal-time slice). Fail the job loudly if any scene still ends mid-sentence after the fix — do not ship fragments.

**Fix 3 — Add a real narration↔prompt alignment check to the audit (F2).**
In `backend/pipeline/stage6_audit.py`, add a deterministic check that runs for *every* story: for each scene, extract the content nouns/verbs from `narration_excerpt` (minus stop-words) and require a minimum overlap with the nouns/verbs in `prompt` + `visual_subject` — flag scenes below threshold as `AlignmentFinding`s with `scene_repairs`. Feed the auditor the **full** narration and at least the first 300 chars of the prompt (not 70), and raise the audit `max_tokens` (see Fix 4). Remove the gate that drops LLM-suggested repairs unless a deterministic finding already exists (merge loop ~505-512). Scene 007 (doors vs mattress) must fail this check — use it as the regression test.

**Fix 4 — Fix the token budget so batches stop truncating into generic fallbacks (F5).**
Either reduce the stage-5 batch to 2 scenes per call at the current 950-token cap, or raise the cap: `app/ai/groq_engine.py:233-235` caps qwen output at 950 tokens because of a free-tier OTPM ceiling — if the user's keys are paid-tier, raise the cap to ~2,000 for stage 5; if free-tier, keep the cap and split batches. Apply the same reasoning to stage 3 (850 tokens for 3 beats × 7 fields) and stage 6 (850 tokens for a whole-board audit). And make truncation **loud**: if `repair_and_parse_json` recovers fewer items than requested, log a warning and retry once with a smaller batch instead of silently filling generic templates.

**Fix 5 — Make the release gate actually gate (F3).**
In `app/ai/job_worker.py:354-393` and `backend/pipeline/orchestrator.py:264-293`, fail the job (do not emit COMPLETED, do not deliver scenes as "ready") when `audit_report.final_recommendation == "NEEDS_REPAIR"` after the 3 replan rounds, or when `Stage8FinalValidator.is_valid` is False. Add the audit score and alignment-finding count to `is_valid` in `backend/pipeline/stage8_validation.py:217-222` (currently it checks only timing/overlap/disk). The user should never again receive a "completed successfully" message for a storyboard the audit rejected.

**Fix 6 — Collapse to one planning path (F7, F10).**
Make the Generate button always run the Path A planner (Stage 1 → 3 → 4) and delete the `Stage2Planner` fallback in `app/ai/job_worker.py:166-176`, or at minimum show an explicit warning when the old planner runs. As part of this, populate `start_word_index`/`end_word_index` on every `VisualScene` in all paths (they exist as fields, `app/models/scene.py:77-78`, but are `None` in Path B), and change `job_worker.py:214` so a missing `narration_excerpt` is a hard error, never silently replaced by `s.action`.

**Fix 7 — De-genericize the fallbacks (F6, F9).**
Replace `derive_contextual_environment` (`stage5_prompts.py:78-110`) with a derivation from the stage-1 location bible for the current scene (it is already built — use it) instead of Roman/Constantinople keyword branches plus a generic else. Replace the stage-5 fallback prompt template (lines 320-360) and the stage-3 fallback (stage3:196-214) so they are built from the scene's actual narration nouns and the bible, not `"Authentic {period} setting"`. Move all Caesar/Constantinople-specific rules out of shared code into a per-story config (or delete them — the stage-5 batch prompt line 226, stage-3 lines 150-157, `resolve_stickman_characters` default `"Caesar"` at stage5:46, and the stage-1 hard-coded fallback bibles), so a new story never inherits another story's spoiler rules.

**Fix 8 — Give the visual planner real context (F8, F11).**
In `backend/pipeline/stage3_visual_planning.py`, pass the previous **5** beats' full concepts (not 2 beats × 60 chars, lines 123-129) and the full character/location bible entries relevant to the current unit (not 6 characters at 80 chars, lines 38-39). In `backend/pipeline/stage5_prompts.py:165-170`, pass the full bible (or at least all characters/locations referenced by the batch's scenes) instead of the first 6/4. This is the cheapest continuity win in the list.

---

## 5. Notes — things checked and cleared

- The Groq model ID `qwen/qwen3.8-27b` is **real** (Groq docs: Qwen 3.8 27B, Preview, 131K context, 16,384 max completion). It is not a typo. Its free-tier OTPM limit is the reason for the 950-token cap (F5) — the cap is a real constraint, the model ID is not a bug.
- Stage 1's system prompt **is** correctly loaded and used (`stage1_analysis.py:221`); stage 3's is too (`stage3_visual_planning.py:36`, passed at line 179); stage 7's is too (`stage7_replanning.py:59`). The dead-load pattern is specific to stages 4, 5, and 6.
- `Stage3PromptGenerator` (`stage3_prompts.py`) — the best prompt builder in the repo (50-90 word targets, action-first, bible-aware) — is only reachable via single-scene regeneration. If Fix 1-8 are too big a change, the smallest high-value swap is to route batch generation through it instead of stage 5's batch path.
- `config/models.json` is Modal vLLM configuration and is irrelevant to the desktop Groq path; do not "fix" the Groq model by editing it.
