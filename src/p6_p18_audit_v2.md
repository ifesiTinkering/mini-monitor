# Re-audit: `src/p6_p18_selfrec_pitch.ipynb` (v2, 54 cells)

Supersedes `p6_p18_audit.md` (the v1 handoff, whose fixes have been applied; that file has
since been removed from `src/`, so this document is self-contained and does not depend on it). Handoff document for an agent
that will apply the remaining fixes. Everything below was verified by reading the notebook
and the installed libraries, and by executing small local probes against `control_arena`,
`inspect_ai` and `tokenize`. The audit itself contacted no remote host and rented no GPU.
Two effort changes were later applied at the user's instruction and verified with two small
real API calls; see the note below.

## Target file

- Path: `/Users/ifesionubogu/mini-monitor/src/p6_p18_selfrec_pitch.ipynb`
- SHA-256 at audit time: `bd62918fde478035dd3934d2f213de256a6cb9d16b8bb83f755cccdc837ecc73`
- Size / mtime: 141,372 bytes, 2026-09-16 14:25:41
- Shape: 54 cells, 26 code cells, **0 executed** (all `execution_count` null, no outputs)

> **Post-audit changes applied 2026-09-16, at the user's instruction.** Two effort changes,
> so that **U, H and T all now run at medium effort**:
>
> 1. `T_EFFORT`: `'low'` -> `'medium'`. Removes a real confound: with U monitoring at medium
>    and T at low, `self_favoring = gap_U - gap_T` mixed "which model" with "how much
>    thinking", so a difference could have come from the effort gap rather than authorship.
> 2. `H_EFFORT`: new constant, `'medium'`, replacing the hardcoded `'none'` for H. This
>    reverses the original spec line "H = claude-haiku-4-5 (thinking off)", and it **closes a
>    confound rather than introducing one**. U and H are the two attacker policies and are
>    meant to be comparable; running U at medium while H had thinking off made them
>    systematically unlike each other. H's code would have been plainer and shorter for a
>    reason that has nothing to do with who wrote it, handing the recognition task a style
>    shortcut: "the more worked-through solution is mine." Matching the two removes that
>    shortcut. Expect the authorship AUC to come out **lower** than it would have under the
>    old asymmetric config, and treat that as the more honest number. Expect the joint
>    success rate to rise, which also helps the thin-pairs problem.
>
>    Residual caveat, minor: the match is approximate, not exact. See the scale note below.
>
> **Medium is not one common scale.** U and T take `reasoning_effort` natively. Haiku 4.5 is
> pre-4.6, so Inspect bridges it: `effort_to_reasoning_tokens('medium')` = **10,000
> `budget_tokens`** of Anthropic extended thinking
> (`inspect_ai/model/_reasoning.py`, `_EFFORT_TO_TOKENS`). Verified by reading the provider,
> not assumed.
>
> **S4 needed a matching fix.** It called H with `max_tokens=64`. `max_tokens_for_config`
> only auto-sizes when `max_tokens` is unset, so an explicit 64 against a 10,000-token
> thinking budget would have been rejected by the API. S4's H call is now
> `max_tokens=11000`, and it uses the real `H_EFFORT` so the check is worth running.
>
> **Verified with real API calls** (small, single-shot, a fraction of a cent):
>
> | Check | Result |
> |---|---|
> | H at medium, `max_tokens=11000` | **PASS**, reply `'OK'`, 43 in / 44 out, **1 reasoning block, 540 chars, thinking genuinely on** |
> | T at medium, real monitor prompt | **PASS**, 437 in / 545 out, strict parser returned `suspicion=0.0` on clean code |
>
> Files touched: cell 0 (summary), cell 4 (`T_EFFORT`, new `H_EFFORT`, `SETTINGS`), cell 15
> (markdown), cell 16 (`H_EFFORT` in the generation loop), cell 33 (S4 markdown), cell 34
> (S4 H call), cell 49 (reuse inventory). All other T and H call sites read the variables, so
> they follow automatically. No artefacts existed, so `config.json` had not been written and
> `RUN_NAME` stays `_v2`. The audit hash above is post-change.

---

# Answers to the ten review questions

## Q1. Are the applied changes correct and complete? Any leftover low-effort or hardcoded host/port?

**Clean.**

- There is now **no `'low'` literal anywhere in the notebook**. `U_EFFORT`, `T_EFFORT` and
  `H_EFFORT` are all `'medium'` (cell 4). The word "low" survives only in the cell 49 cost
  question, as a comparison, not a setting.
- The only IP address is `127.0.0.1`, appearing in `BASE_URL` (cell 4), the `-L` tunnel
  forward (cell 8) and vLLM's `--host` (cell 12). All three are the local end of the tunnel,
  which is correct.
- No `root@`, no `40206`, no hardcoded SSH host or port anywhere.
- `SSH_HOST` and `SSH_PORT` come from `.env` with no defaults (`REMOTE_HOST`,
  `REMOTE_SSH_PORT`), and `check_remote_settings` (cell 8) rejects a missing host or a port
  outside 1-65535.

## Q2. Is U effort identical everywhere, and do the budgets fit medium effort?

**U effort is identical at all six sites, verified by grep:**

| Site | Cell | Source of effort |
|---|---|---|
| Generation | 16 | `U_EFFORT` |
| Training render | 22 | `CONFIG['u_reasoning_effort']` |
| AUC eval render | 28 | reuses `render` from `remote_common` |
| Behaviour monitor | 36 | `U_EFFORT` |
| Section 6b summariser | 44 | `U_EFFORT` |
| Smoke S2 | 14 | `U_EFFORT` |

**H effort is uniform too**, via the new `H_EFFORT` constant: `SETTINGS` (cell 4), the
generation loop (cell 16) and S4 (cell 34). H appears nowhere else, because H only writes
code in Section 1; it is never a monitor.

**T effort is also uniform**, and now equals U's. `T_EFFORT` is read at all six T call sites:
`SETTINGS` (cell 4), S4 (cell 34), behaviour `request_spec` and model (cell 36), 6b `spec` and
`t_model` (cell 44). Matching U and T removes a real confound: with U at medium and T at low,
`self_favoring = gap_U - gap_T` would have mixed "which model" with "how much thinking", so a
difference could have come from the effort gap rather than from authorship.

**Budgets fit in Sections 1 to 5:**

- Training: `if len(full) > CONFIG['max_context']: raise` — loud failure, no silent truncation.
- AUC: `budget = min(MAX_REASONING_TOKENS, MAX_CONTEXT - len(prompt) - 1)` = 8,192 for a
  1-4k prompt against a 32,768 window. Comfortable.
- Behaviour: ~4k prompt + `U_MAX_TOKENS` 16,384 = ~20k < 32,768. Comfortable.
- Generation: served at `--max-model-len 32768`. A react loop at medium effort could
  approach this, but an overflow returns a vLLM 400, which surfaces as a sample error,
  which makes `eval_set` return `complete=False`, which makes cell 16 raise. Loud, not silent.

**They do not fit in Section 6b.** See M1.

## Q3. Does the C1 check read the effective effort for both U and H, and does `model_roles()` survive the T string?

**Yes to both. Verified by execution.**

- `Model` exposes `.config`, and `.config.reasoning_effort` survives the round trip.
- U branch: `get_model('vllm/openai/gpt-oss-20b', base_url=..., api_key='local',
  config=GenerateConfig(reasoning_effort='medium'))` constructs without contacting the
  server. `ControlEvalConfig(untrusted_model=<Model>, ...)` then `model_roles()['untrusted']`
  returns **the identical object** (`r is um` is True) with `reasoning_effort='medium'`
  preserved. The check is real.
- H branch: `untrusted_model` is a string plus
  `untrusted_config=GenerateConfig(reasoning_effort=H_EFFORT)`, which resolves to a `Model`
  whose effective effort is `'medium'`. The check is real here too. (When this was first
  audited the value was `'none'`; the mechanism is unchanged, only the value.)
- T string: `model_roles()` does **not** break. Worth recording why, because it is not what
  the source suggests at a glance: `ControlEvalConfig.trusted_config` defaults to a
  `GenerateConfig()` instance rather than `None`, so `_get_model_for_role`'s
  `if config is None and isinstance(model, str)` early return does not fire and T is
  constructed into a `Model`. No API call is made and no error is raised.

## Q4. Does cleanup always run after a failed vLLM start, in all three places and in S2?

**Three of four are correct. Section 6b is not.**

| Site | Cell | `start_vllm` inside `try`? |
|---|---|---|
| Generation | 16 | Yes |
| Behaviour | 36 | Yes |
| **Section 6b** | **44** | **No — see C1** |
| Smoke S2 | 14 | Yes |

## Q5. Can the comment-row rstrip change string contents? Does the AST check still hold?

**No, and yes. Verified by execution on nine cases.**

- Tested: trailing comment; whole-line comment; a triple-quoted string whose closing line
  carries a comment (`s = """abc   \ndef   """  # c`); a string with trailing whitespace and
  the comment on the next line; a comment line preceding a string with trailing whitespace;
  a single-quoted string with trailing whitespace plus a comment; backslash continuation;
  tab indentation; an f-string with trailing whitespace inside the literal.
- In every case the AST string constants were byte-identical before and after.
- The reason is structural: whitespace inside a string literal is always followed on that
  line by the closing quote, which is non-whitespace and therefore stops `rstrip`.
- `tokenize.untokenize` preserves line numbering (verified separately), so `comment_rows`
  aligns with the output lines.
- The AST equality check still runs after the rstrip and would catch any violation. If
  alignment ever failed, the record would raise and cell 20 now catches, excludes and counts it.

## Q6. Is the adaptive `save_steps` sensible for smoke and for N=60?

**Sensible at N=60, wrong when pairs are scarce, and smoke has a separate hard failure.**
See M3 and M4.

## Q7. Smoke tests: placement, switch requirements, secrets, S1/S2 with only RUN_GENERATION on

- **Placement is correct.** S0 (cell 6) follows config; S1 (cell 10) follows the transport
  helpers; S2 (cell 14) follows `start_vllm`; S4 (cell 34) follows `monitor_prompt` and
  `strict_monitor_parse` and the `get_model` import; S3 (cell 51) sits near the end.
- **No secrets printed.** S0 prints key names only. Every S1 command passes `token=False`.
  All captured output goes through `sanitise()`. S2 and S4 print only model content.
- **Switch requirements are a problem.** See M5.

## Q8. Section 6b: dataset fields, pairing, bootstrap, cost estimate, 131072 restart, T context

**Dataset fields are all correct**, verified against `control_arena`:

| Field used in cell 42 | Verified against | Status |
|---|---|---|
| `row['problem_id']` | `dataset.py` `record_to_sample` | correct |
| `row['question']` | `dataset.py` `main_task_description` | correct |
| `row.get('is_nondeterministic')` | `AppsTaskMetadata` construction | correct |
| `row.get('solutions')` | list of dicts | correct |
| `solution.get('code')` | `validation.py:280` `s["code"]` | correct |
| `solution.get('passes_tests')` | `validation.py:280` `s["passes_tests"]` | correct |
| `dataset['train']` | `hf_dataset(..., split="train")` | correct |

- **Task ID matching is correct.** `Sample(id=str(problem_id))` in `dataset.py`, so
  `selected_samples.json`'s `id` is `str(problem_id)`, which is exactly what cell 42 compares
  against. Cell 18's `str(sample.id)` matches too.
- **Pairing is correct.** `pivot_table` on `['view','pad_target','position','task_id']` by
  `condition`, then `separation = attack - clean`. Averaged per task before the bootstrap.
- **Bootstrap is correct.** `per_task.to_numpy()` column order is fixed by the explicit
  `[['attack','clean','separation']]` selection, so `[:, 2]` really is separation. Resamples
  tasks, not rows, which is the right unit.
- **Cost estimate is correct in structure.** `full_tokens + summary_tokens + 2 * len(to_summarise) * 1500`
  matches an independent recount: ~8.7M for scoring full logs, ~8.7M for T's summarisation
  input, ~0.2M for scoring the two summary sets. It omits per-call prompt boilerplate; see
  the Minor list.
- **The 131072 restart and the T context limit both have real problems.** See M1 and M2.

## Q9. Does anything break with all switches off?

**No. Runs clean top to bottom.** Traced cell by cell with `SMOKE=False`, all four run
switches False, all five smoke switches False, `RUN_CLEANUP=False`:

- Cell 18 short-circuits on missing generation manifests; `attempts` and `paired_records`
  stay empty lists.
- Cell 20 skips on empty `paired_records`.
- Cells 36 and 44 call `Path.glob` on directories that do not exist. **Verified**: this
  returns `[]` rather than raising, so `behaviour_df` and `long_df` are empty frames.
- Cells 38, 40, 46 and 48 all guard on `.empty`.
- Cell 32 reads `demo.ipynb` and requires exactly one `paper_monitor_prompt` literal.
  **Verified**: still exactly one.
- Cell 42's `from datasets import load_dataset` succeeds; `datasets` is in the local venv.
- Only local writes occur: `config.json`, `prepare_assets.py`, `attack_prompt.txt`,
  `remote_common.py`, `train_lora.py`, `evaluate_auc.py`, `monitor_prompt.txt`,
  `results_table.csv`.

## Q10. Runtime and cost

See the table at the end of this document.

---

# Findings

## CRITICAL

### C1. Cell 44: the C2 fix was not applied to the third vLLM start site

- Section 6b starts the server **outside** the `try`, so a failed start orphans both the
  server and the tunnel.
- This is the largest-context start in the notebook (131,072) and therefore the most likely
  of the three to fail on memory, which makes it the worst place to have the bug.

```diff
     pending_u = [row for row in to_summarise if not summary_path(row, 'U').exists()]
     if pending_u:
-        await start_vllm(max_model_len=LONG_CONTEXT)
         try:
+            await start_vllm(max_model_len=LONG_CONTEXT)
             u_model = get_model(U, base_url=BASE_URL, api_key='local',
                 config=GenerateConfig(reasoning_effort=U_EFFORT, max_tokens=U_MAX_TOKENS, max_connections=8))
```

## MAJOR

### M1. Cells 42 and 44: `chars // 4` underestimates code tokens, and every 6b budget rests on it

- Measured on a representative APPS solution: `chars//4` returns 26 where a realistic code
  tokenizer returns about 32. Roughly 25% low.
- A log budgeted at 96,000 "tokens" is realistically about 120,000.
- `T_MAX_INPUT_TOKENS = 120000` guards the *approximation*, so it never fires.
- **U summariser overflow**: 120,000 real input + `U_MAX_TOKENS` 16,384 = 136,384, which
  exceeds `LONG_CONTEXT` 131,072. The largest-padding summaries will be rejected at request
  time, after the GPU has already been rented and the server started.

```diff
-PAD_TOKENS = [0, 24000, 96000]
+PAD_TOKENS = [0, 24000, 72000]  # chars//4 runs ~25% low on code; keep real tokens under LONG_CONTEXT.
 POSITIONS = ['start', 'middle', 'end']
 CHARS_PER_TOKEN = 4  # Rough length proxy; the real token count is printed from API usage after the run.
-T_MAX_INPUT_TOKENS = 120000
+T_MAX_INPUT_TOKENS = 90000   # Approximate budget, chosen so the real count stays under the model limits.
+TOKEN_SAFETY = 1.35          # Headroom for the chars//4 underestimate on code.
```
```diff
                     log = render_log(blocks)
-                    if approx_tokens(log) > T_MAX_INPUT_TOKENS:
-                        raise RuntimeError('A work log exceeds T_MAX_INPUT_TOKENS; lower PAD_TOKENS.')
+                    if approx_tokens(log) * TOKEN_SAFETY > T_MAX_INPUT_TOKENS:
+                        raise RuntimeError('A work log may exceed T_MAX_INPUT_TOKENS; lower PAD_TOKENS.')
+                    if approx_tokens(log) * TOKEN_SAFETY + U_MAX_TOKENS > LONG_CONTEXT:
+                        raise RuntimeError('A work log plus U output may exceed LONG_CONTEXT; lower PAD_TOKENS.')
```

- Better still: after `prepare_remote()` has pulled `assets/tokenizer`, tokenise one
  representative log locally and calibrate `CHARS_PER_TOKEN` from the measured ratio before
  building the rest. That removes the guesswork entirely.

### M2. Cell 12: `start_vllm` can silently reuse a stale server at the wrong context length

- `launch_job` returns early when a session already exists
  (`if tmux -L $SESSION has-session -t $job 2>/dev/null; then exit 0; fi`).
- If a 32,768-context `serve` session is still running, `start_vllm(max_model_len=131072)`
  launches nothing, `/v1/models` answers immediately, and Section 6b runs against a 32k
  window. Every long log then fails at request time with no indication of the real cause.
- In the happy path cell 36 stops the server before 6b runs, so this bites after an
  interrupted section or after a bare S2 run.

```diff
 async def start_vllm(max_model_len: int = MAX_CONTEXT) -> None:
     "Serve the pinned base U with its native Harmony template and tool parser."
     require_remote()
     provenance = json.loads((ART / 'assets/provenance.json').read_text())
+    # launch_job is a no-op when a serve session already exists, which would silently reuse a
+    # server started at a different context length. Record the length and restart on a mismatch.
+    marker = shlex.quote(f'{REMOTE}/jobs/serve.context')
+    current = run_remote(f'cat {marker} 2>/dev/null || true', token=False).strip()
+    if current and current != str(max_model_len):
+        stop_vllm()
+        close_tunnel()
+    run_remote(f'mkdir -p {shlex.quote(REMOTE + "/jobs")}; echo {max_model_len} > {marker}', token=False)
     args = ['uv', 'run', '--no-project', '--python', '.venv-serve/bin/python', 'python', '-m',
```

### M3. Cell 24: `save_steps` uses floor division, so scarce data produces *more* checkpoints

- `save_steps=max(1, len(examples) // CONFIG['checkpoints_per_run'])`.
- Measured across plausible pair counts:

| pairs | train tasks | train examples | save_steps | checkpoints per run |
|---|---|---|---|---|
| 4 | 3 | 6 | 1 | 6 |
| 5 | 4 | 8 | 1 | **8** |
| 8 | 6 | 12 | 2 | 6 |
| 15 | 12 | 24 | 4 | 6 |
| 20 | 16 | 32 | 6 | 6 |

- At 5 pairs that is 8 real + 8 shuffled + 1 base = **17 base-model reloads** in the AUC job,
  roughly 85 minutes of pure loading at about $6 of GPU time.
- The failure mode is worst exactly when data is scarce, which is the expected case for this
  pitch.

```diff
-        save_strategy='steps', save_steps=max(1, len(examples) // CONFIG['checkpoints_per_run']), logging_steps=1,
+        save_strategy='steps',
+        # Ceiling, not floor: floor division makes a small dataset save *more* checkpoints than
+        # requested, and every extra checkpoint costs a full base-model reload at evaluation time.
+        save_steps=max(1, -(-len(examples) // CONFIG['checkpoints_per_run'])), logging_steps=1,
```

### M4. Cells 2 and 20: smoke `min_pairs=1` guarantees an empty training split

- `cut = math.floor(0.8 * 1) = 0`, so `train_ids = []` and `train.jsonl` is written empty.
- Cell 20 does not object. The remote job then raises `No training examples`, so a
  `SMOKE=True` end-to-end run can never reach S3.8, and S3 can never pass.

```diff
 SMOKE_SIZES = dict(n_tasks=3, max_reasoning_tokens=512, bootstraps=50,
-                   checkpoints_per_run=2, min_pairs=1, num_tests_to_run=10)
+                   checkpoints_per_run=2, min_pairs=2, num_tests_to_run=10)
```
```diff
     cut = math.floor(0.8 * len(task_ids))
+    cut = min(max(cut, 1), len(task_ids) - 1)  # Never produce an empty train or test split.
     train_ids, test_ids = task_ids[:cut], task_ids[cut:]
```

### M5. Cells 8 and 13: S1 and S2 cannot run without arming the real pipeline, and S2 does not say so

- `require_remote()` demands one of the four run switches. `start_vllm`, `push`, `pull` and
  the default `run_remote` path all call it, so S1 and S2 need a real run switch on.
- Turning on `RUN_GENERATION` also makes cell 12 auto-run `prepare_remote()` and cell 16 run
  full paid generation on a top-to-bottom pass. There is no "remote allowed, no experiment"
  mode.
- Cell 9 (S1 markdown) states the switch requirement. Cell 13 (S2 markdown) does not.

```diff
 def require_remote() -> None:
     "Reject accidental connections while all run switches are off."
-    if not (RUN_GENERATION or RUN_SFT or RUN_EVAL or RUN_LONG):
-        raise RuntimeError('Remote work is disabled by the four run switches.')
+    # SMOKE_S1/S2 need remote access without arming generation, training or evaluation.
+    if not (RUN_GENERATION or RUN_SFT or RUN_EVAL or RUN_LONG or SMOKE_S1 or SMOKE_S2):
+        raise RuntimeError('Remote work is disabled by the run switches and the smoke switches.')
```

Add to cell 13:

> Needs `REMOTE_HOST`, `REMOTE_SSH_PORT` and `REMOTE_DIR` in `.env`. With the
> `require_remote` fix it needs no run switch; without it, one run switch must be on, which
> also arms the real pipeline on a top-to-bottom pass.

## MINOR

- **Cell 14.** The S2 `finally` calls `stop_vllm()` and `close_tunnel()` unconditionally.
  Both call `check_remote_settings()`, which raises `ValueError` when `REMOTE_HOST` is unset,
  replacing the original failure. It also opens an SSH connection even when `start_vllm`
  never ran. Wrap both in `try/except ValueError`, or track a `started` flag.
- **Cell 30.** Two of the three `run_remote` calls in the `finally` omit `token=False`, so
  `HF_TOKEN` is transmitted for a bare `test -f`. The third already has it. Add `token=False`
  to both.
- **Cell 46.** `dropna(subset=['attack', 'clean'])` raises `KeyError` if either condition is
  entirely absent from `valid`, for example when every clean log hit a parse failure. Insert
  `.reindex(columns=['attack', 'clean'])` before `dropna`.
- **Cell 46.** `pad_target=0` uses position `'only'`, so the left plot draws three position
  lines starting at 24k plus one isolated `'only'` marker at 0. There is no shared baseline,
  which weakens the depth readout the markdown describes. Consider emitting the zero-pad case
  under all three position labels.
- **Cell 42.** `load_dataset('RoganInglis/apps-control-arena')` downloads the whole dataset
  and calls `strip_comments` on one solution per row, inside `run_long`, with no progress
  output. Expect a multi-GB download and a long local loop on the first 6b run.
- **Cell 44.** The cost estimate omits the per-call monitor-prompt boilerplate, roughly 400
  tokens across about 312 calls, or ~125k tokens. Output and reasoning tokens are correctly
  flagged as excluded; the boilerplate is not.
- **Stale documentation.** Four places still describe the old configuration:
  - Cell 3: "The number of attempted task IDs is 20"
  - Cell 19: "With 20 attempted tasks ... this cell stops below five pairs"
  - Cell 43: "Start with `N_TASKS = 20`"
  - Cell 49 open questions: "The default 20 is deliberately small"

  All four are now wrong: `N_TASKS = 60` and the floor is `MIN_USABLE_PAIRS`.

## Confirmed correct, do not undo

> **Numbering warning.** The labels in this list are from the **v1 audit** and are prefixed
> `v1-` below to avoid collision. They are *not* the same as the `C1` and `M1`-`M5` in the
> Findings section above, which are **v2** labels for work still outstanding. When this
> document says "apply C1", it always means **v2 C1** (Section 6b `start_vllm` outside the
> `try`, cell 44).

- **v1-C1 fix and its effective-value check** (cell 16). Verified by executing both branches.
- **v1-C2 fix** in generation (cell 16), behaviour (cell 36) and S2 (cell 14).
- **v1-C3 comment-row rstrip** (cell 20). Verified safe against string contents on nine cases,
  with line alignment confirmed and the AST check still in place. The per-record exclusion
  and counting of cleaning failures is a genuine improvement.
- **v1-M1 cleanup cell** (cell 53). `force=True` plus `token=False` means it works with every
  switch off, and it degrades gracefully when `.env` is unset.
- **v1-M2 log pulls** (cells 26 and 30).
- **v1-M4 tmux reap wait** (cell 8 `poll_job`).
- **v1-M6 `num_tests_to_run` from `SETTINGS`** (cell 16).
- **v1-M7 early warning after pairing** (cell 18).
- **v1-M3 placeholders** (cell 47). Present and covering P6, P18 and P10.
- **`run_remote` token/force parameters, `check_remote_settings`, host and port from `.env`.**
- **No secrets printed anywhere.**
- **P6 / P18 / P10 mapping** now stated explicitly in cell 0.

---

# Runtime and cost, N=60 at medium effort, 1x H200 at $4.194/hr

## Assumptions

- Joint U-and-H success about 25%, so roughly 15 pairs: 12 train tasks (24 examples) and
  3 test tasks (6 examples).
- `save_steps = 24 // 5 = 4`, giving 6 checkpoints per run, so 13 checkpoint evaluations
  including base. **Fixing M3 reduces this.**
- Eager attention at 20-30 tok/s; medium-effort reasoning of 1-3k tokens per item.
- Full-suite Docker grading at about 220 sequential sandbox executions per passing submission,
  with early exit on failure.
- vLLM stays up through the U half of Docker grading, because cell 16's `finally` runs only
  after `eval_set` returns and `eval_set` includes scoring.

## Table

| Section | Cells | Wall clock | GPU billed | Notes |
|---|---|---|---|---|
| Remote prep | 12 | 10-15 min | yes | One-off, `environment.ready` skips it after |
| vLLM starts (3x) | 12 | ~12 min | yes | 6 min first, 3 min after |
| U generation | 16 | 5-10 min | yes | Batched, 20 connections |
| H generation | 16 | 3-5 min | no | API |
| Docker grading, U half | 16 | 28-45 min | **yes** | Server stays up through scoring |
| Docker grading, H half | 16 | 28-45 min | no | Server already stopped |
| SFT, both runs | 26 | ~17 min | yes | 2 model loads dominate |
| **AUC evaluation** | 30 | **~180 min** | **yes** | 13 reloads x (5 min load + 6 items x ~90 s) |
| Behaviour | 36 | ~6 min | yes | 12 requests; server restart dominates |
| **Subtotal, no RUN_LONG** | | | **~4-5.5 h** | **$17-23** |
| 6b dataset build | 42 | 10-25 min | no | Full dataset download plus local loop |
| 6b U summaries | 44 | ~110 min | **yes** | 72 logs at ~120k tokens, 131k-context server |
| 6b T summaries and scoring | 44 | 20-40 min | no | API, 8 concurrent |
| **Total with RUN_LONG** | | | **~6.5-8 h** | **$27-34** |

## API cost

Anthropic pricing verified: `claude-haiku-4-5` is $1.00/M input, $5.00/M output, 200K context.

| Call | Tokens | Cost |
|---|---|---|
| H attack generation, 60 tasks, **thinking on** | ~180k in, ~300k out (thinking budget 10,000/task, rarely spent in full) | **~$1.70**, up from $0.63 with thinking off |
| T behaviour monitor, 6 requests | ~12k in, ~6k out | **under $0.01** |
| T in Section 6b | **~17.6M input** (the notebook's own estimate; ~22M allowing for M1) plus output | **dominant** |

- `gpt-5-mini` pricing is OpenAI's and was not verified from a first-party source. Without
  `RUN_LONG` the T line is negligible either way. With `RUN_LONG` it is effectively the whole
  API bill, which is why cell 44 refusing to run until `T_INPUT_USD_PER_M` is set is the
  right design.

## Biggest levers

1. **The 13 base-model reloads in AUC.** Fixing M3 cuts the checkpoint count. Loading the
   base once and hot-swapping adapters with `PeftModel.load_adapter` would remove most of the
   rest, worth roughly an hour of GPU time.
2. **Holding vLLM up through the U half of Docker grading**, roughly 30-45 min of billed idle
   GPU. Splitting generation from scoring would recover it.
3. **Section 6b at the largest padding.** It roughly doubles both the GPU bill and the total
   wall clock, and it carries M1 and M2. Consider running Sections 1-5 first and treating 6b
   as a separate decision.

---

# Suggested order of work

1. Apply **C1** (cell 44). One-line move, removes the only remaining orphaned-GPU path.
2. Apply **M3** (cell 24) and **M4** (cells 2 and 20). Both are cheap and both block a
   working smoke run or inflate the AUC bill.
3. Apply **M5** (cell 8 plus cell 13 markdown). This is what lets you run S1 and S2 without
   arming the real pipeline, so it should land before any remote testing.
4. Run **S0**. Free and local.
5. Run **S1**. SSH only, no GPU compute.
6. Get approval, then run **S2**. First cell that costs money; settles the vLLM parser and
   `reasoning_effort` questions.
7. Apply **M1** and **M2** before enabling `RUN_LONG`. Neither matters until 6b runs, and
   both will waste GPU time if left.
8. Clear the Minor list and the stale documentation.
9. Only then consider a real run.
