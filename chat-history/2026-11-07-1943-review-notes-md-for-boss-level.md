# Review NOTES.md for boss level

> Read `NOTES.md` - we'll pick up where we left off. Tell me what you read. We're trying to improve our model to pass a hidden boss level image test case on Coursemology.

<details><summary>2 previous messages</summary>

> I’ll review the project notes and the current repository state, then summarize the precise checkpoint and likely next move for the hidden image case.
>
> <details><summary>Ran a command</summary>
>
> - Ran `Get-Content -Raw NOTES.md; git status --short; rg --files -g '!*node_modules*' | Select-Object -First 160`
>
> </details>
</details>

I read `NOTES.md`. The project is at the Task 3 stage: improving the image-observation agent for Coursemology’s hidden boss levels.

What is already working:

- The Task 1 planner handles all 22 public structured-state levels, including compact planners for keys/doors, power-ups, boxes, lava, and mixed mechanics.
- The Task 2 image agent uses a batched TorchScript CNN to decode the board into a `GridState`, then reuses a cached deterministic plan rather than re-running vision every turn.
- The lean Task 2 submission passed all Coursemology public image cases.
- Local image tests for public B levels and C1 reconstruct boards correctly and win; perception happens once per episode and route replay is essentially free.

The active failure is specific to Task 3 hidden boss image observations:

- All three hidden boss cases timed out at the full 15 seconds.
- They neither won nor lost, suggesting the agent likely fails to finish its initial reconstruction/planning phase before it can cache a route.
- This is probably not the old per-turn image-inference issue, because selective perception solved that.
- The strongest current hypothesis is state explosion in the initial mixed-mechanics planner on larger boss maps, though initial image parsing must be measured too.

The notes’ recommended next work is:

1. Add external timing around the entire first hidden-like episode / initial `agent.step`, without putting heavy diagnostics back into the submission.
2. Stress-test and profile `_mixed_fast_plan()` on larger synthetic mixed-mechanics layouts.
3. Put a strict search budget and fallback strategy around the mixed planner before attempting optional-coin optimization—the immediate problem is completing at all, not improving score.

I also noticed the workspace contains `v2-6.py`, which is newer than the versions described in the notes; that is likely the first file to inspect for the current in-progress approach.

You’re right on both points.

`v2-6.py` is the designated working copy of `v2-5.py`; new changes should go there, preserving all earlier versions as baselines. I should not have implied it was an unexplained newer direction. :codex-annotation{index="1"}

And Coursemology gives no per-case trace or timing breakdown—only the final aggregate timeout result—so we cannot instrument the actual hidden cases externally. The practical replacement is to construct locally “boss-like” stress maps, then measure the initial parse-and-plan work there. That lets us identify and bound the worst-case behavior before pasting the lean code into Coursemology. The submission itself should stay lean. :codex-annotation{index="2"}

The next concrete path is therefore:

- Use `v2-6.py` as the only editable working version.
- Inspect the mixed-planner search and make it reliably bounded on large maps.
- Build or locate local high-complexity mixed maps—many gems, doors/keys, lava, power-ups, and optional coins—to reproduce the likely state-growth pattern.
- Ensure the planner can return a valid, perhaps non-optimal, route quickly when its preferred search becomes too expensive. A lower score can still pass; a 15-second pre-action timeout cannot.

> Let's proceed.

<details><summary>6 previous messages</summary>

> I’ll work in `v2-6.py` only. First I’ll inspect its mixed-planning path and the available public level builders so I can add a safe bounded fallback without regressing the already-passing Task 2 behavior.
>
> <details><summary>Ran 3 commands</summary>
>
> - Ran `rg -n "mixed_fast_plan|def parse|def step|def _.*plan|time\.|perf_counter|heapq" v2-6.py; rg -n "C1|Heist|mixed|def .*boss|def c" public_levels\*.py`
> - Ran `Get-Content v2-6.py | Select-Object -Skip 890 -First 210; Get-Content v2-6.py | Select-Object -Skip 1360 -First 215; rg -n "def .*c|C1|Heist|mixed" public_levels`
> - Ran `Get-Content v2-6.py | Select-Object -First 180; Get-Content v2-6.py | Select-Object -Skip 300 -First 225; Get-Content public_levels\challenges.py | Select-Object -Skip 240 -First 150`
>
> </details>
>
> I found a likely hidden-level scaling fault: the mixed planner’s heuristic enumerates every remaining-gem ordering on every explored state. That is fine for the public maps’ small gem counts, but it becomes factorial work on a boss map. I’m replacing only the large-gem heuristic with a cached wall-distance lower bound, leaving the exact public-map heuristic in place.
>
> <details><summary>Edited a file, ran 2 commands</summary>
>
> - Ran `Get-Content v2-6.py | Select-Object -Skip 160 -First 150; rg -n "_static_heuristic\(" v2-6.py`
> - Wrote `./v2-6.py` (+50 -0)
> - Ran `python -m py_compile v2-6.py; Get-Content public_levels\play.py -Raw; Get-Content public_levels\catalog.py -First 120`
>
> </details>
>
> The large-gem fallback is now in `v2-6.py`. It uses “distance to a gem + minimum spanning tree across remaining gems + distance from a gem to an exit,” cached by gem subset. This remains a safe lower bound, while avoiding factorial permutations once more than five gems remain. I’m checking that public boss behavior remains intact and then I’ll run a deliberately gem-heavy mixed-map stress case.
>
> <details><summary>Edited a file, ran 5 commands</summary>
>
> - Ran `python -c "import importlib.util,time; s=importlib.util.spec_from_file_location('candidate','v2-6.py'); m=importlib.util.module_from_spec(s);s.loader.exec_module(m); from public_levels.challenges import build_level_the_heist; a=m.Agent(); st=build_level_the_heist(); t=time.perf_counter(); act=a.step(st); print(act, round((time.perf_counter()-t)*1000,2), len(a._mixed_plan), len(a._gem_mst_costs))"`
> - Wrote `./v2-6.py` (+12 -2)
> - Ran `Get-Content v2-6.py | Select-Object -Skip 520 -First 95; Get-Content v2-6.py | Select-Object -Skip 950 -First 155; python -m py_compile v2-6.py; git -C C:\Users\User\Documents\School\cs2109s\capstone-project diff -- v2-6.py`
> - Ran `rg -n -C 4 "heuristic_weight" v2-6.py; Get-Content v2-6.py | Select-Object -Skip 1050 -First 70`
> - Ran `Get-Content v2-6.py | Select-Object -Skip 840 -First 80; Get-Content v2-6.py | Select-Object -Skip 1100 -First 50; Get-Content v2-6.py | Select-Object -Skip 1060 -First 35`
> - Wrote `./v2-6.py` (+9 -9)
> - Ran `rg -n -C 3 "heuristic_weight" v2-6.py; python -m py_compile v2-6.py; Get-FileHash v2-5.py,v2-6.py | Format-Table -AutoSize`
> - Wrote `./v2-6.py` (+6 -1)
>
> </details>
</details>

Implemented the first boss-scaling fix in [v2-6.py](./v2-6.py).

The mixed planner previously computed an exact permutation over all remaining gems for every A* state. That is factorial-time per state, so a hidden map with many gems can stall before it produces its first action.

Now it behaves in two modes:

- **Five or fewer gems:** unchanged exact ordering heuristic, preserving public-level behavior and scores.
- **More than five gems:** uses a cached lower bound:
  - current position → nearest remaining gem
  - minimum spanning tree across remaining gems
  - remaining gem → nearest exit

The boss-size mode also uses weighted A* (`2 × heuristic`) in the mixed planner. It is intentionally biased toward finding a valid complete route quickly instead of spending most of the deadline proving that route is shortest. Public-size boards continue using ordinary A*.

I also cleared the new MST cache whenever a new episode is indexed, so it cannot leak geometry from one board to another.

Verification completed:

- `v2-6.py` compiles successfully.
- Only `v2-6.py` was changed; `v2-5.py` remains untouched as the passing baseline.

I could not run an actual course-environment episode locally because this shell environment does not have the `grid_adventure` package installed. The next practical validation is to paste the updated `v2-6.py` submission version—with the embedded model loader retained—into Coursemology and see whether the boss cases begin producing wins rather than all reaching 15 seconds.

> Replace the model part with a `TODO:` block so I can paste the inline model in for submission.

<details><summary>2 previous messages</summary>

> I’ll update only `v2-6.py` so its local-file model loader is replaced by a clear module-scope `TODO` placeholder compatible with the existing one-time inference optimization.
>
> <details><summary>Edited a file, ran 2 commands</summary>
>
> - Ran `rg -n -C 6 "load_local_tile_model|LOCAL_TILE_MODEL_PATH|_get_tile_model|get_model" v2-5-submit.py v2-6.py v2-5.py`
> - Wrote `./v2-6.py` (+10 -20)
> - Ran `python -m py_compile v2-6.py; rg -n -C 4 "TODO:|def get_model|def _get_tile_model" v2-6.py; rg -n "Path|load_local" v2-6.py`
>
> </details>
</details>

Done. [v2-6.py](./v2-6.py:66) now contains a module-scope `TODO` `get_model(...)` block.

Before submitting:

1. Generate or copy the inline `get_model(...)` loader source.
2. Replace the entire TODO function—from the comment through its `RuntimeError` body—with that generated function.
3. Leave `_get_tile_model()` unchanged; it already calls `get_model()` once and applies inference optimization.

I also removed the local-file loader and its unused `Path` import. The file still compiles successfully.
