# Revision 3: audit fixes and offline verification

Target: `src/p6_p18_selfrec_pitch.ipynb`  
SHA-256: `b913b4e4a338387bb043007e647ec548695bf7ed0d220f40bb43e9929f860ad7`  
Shape: 54 cells; 26 code cells; zero execution counts and outputs.  
Run namespace: `_v3`, preserving earlier immutable artefacts. U, H and T remain at medium effort; N_TASKS remains 60. All pipeline, smoke and cleanup switches default to False.

## Verdict

All actionable findings in `p6_p18_audit_v2.md`, plus the additional review blockers, have been addressed. Fifteen offline regression tests pass. The revised notebook is ready for staged smoke testing by the user. This is not a claim that remote dependencies, hardware or model endpoints have passed runtime verification. No notebook cells were executed, no credentials were loaded by the checks, and no API calls, SSH connections, model downloads or installations were made for this revision.

The tests compile notebook text and embedded scripts, and extract individual definitions into controlled namespaces. Transport and HTTP endpoints are fakes. They do not run the notebook top to bottom, load its configuration or call its models.

## Finding closure

| Finding | Change and evidence |
|---|---|
| C1: Section 6b starts outside cleanup | Startup is inside try/finally. All four start sites are statically checked for a cleanup guard. |
| M1: character proxy used for context budgets | Padding uses the pinned U tokenizer. Remote preparation exports native chat framing and pulls tokenizer assets. Each full monitor and summary prompt is counted before U startup. T uses its model-specific tiktoken encoding with an explicit chat allowance. U reserves output tokens and an additional context margin. Actual summary prompts are checked again before T calls. Boundary rejection is tested with fakes. |
| M1 proposed patch contradiction | Did not copy the 72k x 1.35 versus 90k contradiction. Targets are now 0/24k/72k actual U content tokens, with independent request limits. Unknown real inputs fail before model requests; no arbitrary character ratio is treated as exact. |
| M2: stale context window | A run-owned server configuration records the command, revision and requested context. Unknown or different live sessions are stopped and restarted. The `/v1/models` response must also advertise the requested context; a marker alone is insufficient. Unknown/stale live values are rejected. Fake endpoint regressions pass. |
| M3: excessive checkpoints | Ceiling division gives at most the configured number of distinct evaluated checkpoints, including the deduplicated final step, for this batch-one, one-epoch configuration. Tested for 1 through 100 examples and both checkpoint targets. |
| M4: empty smoke training split | Smoke requires at least two pairs. Split bounds ensure both train and test are nonempty. Tested for 2 through 100 pairs. Pair scarcity remains a legitimate reason for a smoke run to stop. |
| M5: smoke requires arming pipeline | S1/S2 grant helper access independently. S1 does not require HF_TOKEN; token-bearing commands do. Pipeline preparation remains guarded by pipeline switches; S2 explicitly performs missing preparation itself. Documentation updated. |
| Minor: cleanup masks startup error | `cleanup_vllm` validates settings before any connection and attempts stop and tunnel close independently. Errors become explicit warnings rather than masking the original exception. Tested. |
| Minor: unnecessary token transmission | AUC file-existence probes, polling, push directory creation, GPU queries and server marker commands use token=False. S1 round-trip helpers no longer transmit the token. |
| Minor: absent attack or clean condition | Reindex before dropping missing pairs. Zero surviving pairs gets an explicit unavailable branch, avoiding the subsequent empty-frame sort failure too. Regression tests cover absent conditions and all failures. |
| Minor: isolated zero-padding baseline | Reuse the single baseline in each position curve for plotting only. No repeated API requests or duplicated statistical observations. |
| Minor: silent reference-data work | Print a download notice and preparation progress every 250 rows. Reference data is still cached by the dataset library. |
| Minor: omitted prompt boilerplate | Input-cost estimate includes the full T monitor/summarisation prompts, chat allowances and summary-monitor boilerplate. Summary content length remains estimated; output/reasoning costs remain additional. |
| Minor: stale configuration prose | Corrected attempted-task count, pair floor, padding values, checkpoint semantics and smoke permissions. |
| Additional: AnyIO polling keyword failure | `functools.partial` binds token=False to run_remote, rather than passing it to AnyIO. Successful and failed fake remote jobs are tested. |
| Additional: weak S3 PASS checks | Selection checks count and uniqueness; split checks disjointness, nonempty sets and one U/H pair per task; AUC requires base/real/shuffled valid rows and held-out tasks; behaviour requires unique successfully parsed requests. S3 raises when any check fails. Negative regression cases pass. |
| Additional: effort interpretation | Removed claims that the same effort label equalises compute or predicts lower AUC/higher joint success. Native and bridged settings are explicitly different scales. |
| Additional: rental accounting | Documented that stopping vLLM does not stop instance billing. The user must stop or destroy the rental. The v2 dollar/time table is an assumption-based estimate, not a verified budget. |
| Additional: long-input reuse | Long-input build configuration is immutable and includes split/pair hashes, tokenizers, padding and prompts. Changed inputs require a new run, instead of silently loading mismatched saved logs. |
| Additional: cleaned-task population | Long-context needles must belong to the saved train/test split, so tasks excluded during comment cleaning cannot reappear. |

## Verification

Command:

```sh
uv run --no-sync python -m unittest discover -s tests -p test_p6_p18_notebook_audit.py -v
```

Result: **15 tests passed**. Test file: `tests/test_p6_p18_notebook_audit.py`.

Checks include syntax compilation for every code cell and embedded remote script; empty execution state; disabled switches; remote permission isolation; polling; cleanup; all startup guards; configuration restart and live-window validation; split/checkpoint arithmetic; empty long-result handling; token budgets including request framing and output reserve; and strengthened S3 assertions.

## Remaining runtime gates and interpretation limits

1. Start with S0 locally, then S1 with only its switch enabled. S1 checks SSH/tools/storage but does not install or run models. An existing rented host may still be billed while idle.
2. S2 is a paid remote smoke check. It verifies startup and a chat/final-answer path at the requested context. It does not prove tool calling, LoRA memory fit, or exact final-logit extraction.
3. Run the separately guarded S4 for the current H/T API configuration when intended. The v2 audit records earlier API probes; this revision did not repeat them.
4. Use the small end-to-end SMOKE run and require S3 to pass before enabling the full 60-task run. Model revision/template assertions, parser compatibility, CUDA dependencies and memory fit remain fail-closed runtime gates. Two successful pairs are required; three attempts do not guarantee them. Increasing smoke task attempts is preferable to weakening labels or mixing tasks across splits.
5. Treat RUN_LONG as a separate decision after the shorter experiment. It needs pulled tokenizer assets and a current user-supplied T input price. The T chat allowance is conservative, not an exact provider wire-token count. Stored reference solutions passing finite tests do not prove they are free of subtle bugs.
6. Interpret long-context complete-case plots alongside exclusions: if failures differ across views or padding levels, the populations can differ. A future inferential comparison should restrict to shared complete task/position sets across all compared views.
7. Same-labelled effort, one seed, few retained tasks, code-style cues and a selected maximum test AUC do not establish equal compute, a capability ceiling or causal self-favouring. The notebook retains these limitations.

No known unresolved blocker remains within the listed offline audit findings. Remote operational success is deliberately not certified without executing the smoke gates.
