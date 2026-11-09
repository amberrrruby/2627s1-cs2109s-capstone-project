# Review NOTES.md and next steps

> ```
> py
>
>     reference_logits = model(verification_input)
> ```
>
> ... It does. Skip that line?

<details><summary>2 previous messages</summary>

> Yes—if you only want to validate that the already-exported loader runs, the reference-model comparison is unnecessary and still depends on having rebuilt `model` in this runtime. I’ll change that verification cell to check the loaded TorchScript model’s output shape and finite logits only.
>
> <details><summary>Edited a file, ran a command</summary>
>
> - Wrote `./task-2.ipynb` (+5 -5)
> - Ran `$null = Get-Content -Raw task-2.ipynb | ConvertFrom-Json; rg -n -C 2 "Inline-loader smoke|embedded_logits.shape|reference_logits" task-2.ipynb`
>
> </details>
</details>

Done. The inline-loader verification now only loads the exported model and checks that it returns finite `(3, 14)` logits. It no longer calls `model(...)` or compares against the checkpoint.

The stricter equality check remains only in the standalone TorchScript export cell, where `model` is necessarily already present to perform the export.

> Export the model to `\exports` ?

Yes. The new export cell saves the file to:

`PROJECT / "exports" / "tile_multilabel_cnn_best.torchscript.pt"`

So, in your Colab layout, it will be in the project’s `exports` folder. It creates the folder earlier via `EXPORTS`, then writes the TorchScript file there.

> But I'm not seeing an output. I reran it - I think the cell hasn't done that yet.

<details><summary>2 previous messages</summary>

> I’ll check the notebook’s export-path setup and make the file-export cell create `exports` explicitly and print the resolved absolute output path, so it is obvious where Colab wrote it.
>
> <details><summary>Edited a file, ran a command</summary>
>
> - Ran `Get-Content task-2.ipynb | Select-Object -Skip 225 -First 60; Get-Content task-2.ipynb | Select-Object -Skip 950 -First 55`
> - Wrote `./task-2.ipynb` (+5 -1)
>
> </details>
</details>

You likely reran the “Inline-loader smoke test,” which only tests the existing embedded loader—it does not write a `.torchscript.pt` file.

Run the cell under:

`## File-based TorchScript export for local iteration`

I’ve made that cell print both the checkpoint source and destination before exporting. Its output should include:

```text
Exporting checkpoint: .../checkpoints/tile_multilabel_cnn_best.pt
TorchScript destination: .../exports/tile_multilabel_cnn_best.torchscript.pt
TorchScript file saved to: ...
File-based TorchScript verification passed.
```

If you don’t see that first pair of lines, you’re running a different cell or Colab still has the older notebook copy.

> ```python
> py
>
> BEST_CHECKPOINT = CHECKPOINTS / 'tile_multilabel_cnn_best.pt'
>
> # Export a standalone TorchScript file for local use.
> # This assumes TileMultiLabelCNN, IMAGE_SIZE, BEST_CHECKPOINT, and EXPORTS
> # have been defined by the earlier notebook cells.
> if not BEST_CHECKPOINT.exists():
>     raise FileNotFoundError(f'Best checkpoint not found: {BEST_CHECKPOINT}')
>
> EXPORTS.mkdir(parents=True, exist_ok=True)
> TORCHSCRIPT_PATH = EXPORTS / 'tile_multilabel_cnn_best.torchscript.pt'
> print(f'Exporting checkpoint: {BEST_CHECKPOINT.resolve()}')
> print(f'TorchScript destination: {TORCHSCRIPT_PATH.resolve()}')
>
> best_checkpoint = torch.load(BEST_CHECKPOINT, map_location='cpu')
> model = TileMultiLabelCNN()
> model.load_state_dict(best_checkpoint['state_dict'])
> model.eval()
>
> example_inputs = torch.zeros(1, 4, IMAGE_SIZE, IMAGE_SIZE, dtype=torch.float32)
> # tracing is appropriate here: the CNN has a fixed tensor-only forward path.
> scripted_model = torch.jit.trace(model, example_inputs, strict=True)
> torch.jit.save(scripted_model, TORCHSCRIPT_PATH)
>
> # Verify the on-disk artifact, not the in-memory traced object.
> reloaded_model = torch.jit.load(TORCHSCRIPT_PATH, map_location='cpu').eval()
> verification_input = torch.rand(3, 4, IMAGE_SIZE, IMAGE_SIZE)
> with torch.no_grad():
>     reference_logits = model(verification_input)
>     torchscript_logits = reloaded_model(verification_input)
> torch.testing.assert_close(reference_logits, torchscript_logits, rtol=1e-5, atol=1e-6)
> print(f'TorchScript file saved to: {TORCHSCRIPT_PATH}')
> print(f'TorchScript size: {TORCHSCRIPT_PATH.stat().st_size / 1024:.1f} KiB')
> print('File-based TorchScript verification passed.')
> ```
>
> Setup's a bit messy, but we'll just try to get it work. The issue here is the same - needs a `model` binding.

<details><summary>2 previous messages</summary>

> The pasted cell creates its own `model`; the only prior binding it genuinely needs is the `TileMultiLabelCNN` class, because your `.pt` is a `state_dict`, not a fully serialized model. I’ll make the verification independent of `model` anyway, but you still need the model-class definition once to reconstruct weights for tracing—no training required.
>
> <details><summary>Edited a file, ran a command</summary>
>
> - Ran `Get-Content task-2.ipynb | Select-Object -Skip 545 -First 70`
> - Wrote `./task-2.ipynb` (+10 -3)
>
> </details>
</details>

I removed the extra reference-model verification from the file export cell too.

One distinction: the cell must still reconstruct a `model` internally to convert its checkpoint `state_dict` into TorchScript:

```python
model = TileMultiLabelCNN()
model.load_state_dict(best_checkpoint['state_dict'])
```

That is not retraining, and it does not need an existing `model` variable. It only needs `TileMultiLabelCNN` to have been defined once. I added a direct error message if the class is missing.

After export, verification now only loads `tile_multilabel_cnn_best.torchscript.pt` and checks it returns finite 14-label logits.

> Right. Downloaded. How do we then reference / import it from our local notebook? Add the import / reference code into `v2-1.py` - I'll be copying it into the local notebook I'm working on.

<details><summary>4 previous messages</summary>

> I’ll inspect the current submission agent’s model-loading and image-preprocessing path, then add a local-development loader that uses the downloaded TorchScript file while keeping the self-contained submission path intact.
>
> <details><summary>Ran 3 commands</summary>
>
> - Ran `rg --files -g "v2-1*.py" -g "*.py" | Sort-Object; rg -n -C 4 "def get_model|torch\.jit|TileMultiLabel|model\(|Image|predict\(" v2-1-submit.py v1-16.py 2>$null`
> - Ran `Get-Content v2-1.py | Select-Object -First 180; rg -n -C 4 "get_model|_model|torch|predict\(|def parse|split_cells" v2-1.py`
> - Ran `Get-Content v2-1.py | Select-Object -Skip 170 -First 100; Get-Content v2-1.py | Select-Object -Skip 1620 -First 125`
>
> </details>
>
> I’ll add a local-only, lazy TorchScript loader to `v2-1.py`. It will look for `exports/tile_multilabel_cnn_best.torchscript.pt` relative to the notebook’s working directory, load it once on CPU, and keep it cached on the agent—without changing the current parser yet or touching the submission file.
>
> <details><summary>Edited a file, ran a command</summary>
>
> - Wrote `./v2-1.py` (+28 -0)
> - Ran `python -m py_compile v2-1.py`
>
> </details>
</details>

Added local TorchScript loading to [v2-1.py](./v2-1.py).

Put the downloaded file here relative to your local notebook:

```text
exports/tile_multilabel_cnn_best.torchscript.pt
```

Then, when CNN inference is wired into parsing, call:

```python
model = self._get_tile_model()
```

It loads the model once on CPU via `torch.jit.load(...)`, sets evaluation mode, and caches it for the episode. The current parser behavior is unchanged for now.

This is local-development-only; Coursemology must continue using the embedded loader because it cannot access a separate model file.

> `a2-task2-telemetry.txt` dumped.

<details><summary>2 previous messages</summary>

> I’ll inspect the A2 Task 2 telemetry and identify where the image-mode runtime is going.
>
> <details><summary>Ran a command</summary>
>
> - Ran `Get-Item a2-task2-telemetry.txt | Select-Object Name,Length,LastWriteTime; Get-Content -Raw a2-task2-telemetry.txt`
>
> </details>
</details>

A2 won at `-27` in 10 turns. Planner performance is excellent:

- Initial static A* search: `0.60 ms`, 26 visited states.
- Remaining 9 turns: reused the cached plan in `0.01–0.02 ms`.
- RSS stayed stable: `82.5 → 83.3 MB`.

But this telemetry has no perception timings (`split_ms`, `cnn_ms`, `decode_ms`, `parse_ms`). So it does not yet test or explain the Task 2 Coursemology timeouts—the local run is only reporting planner work. Next, we should wire the TorchScript model into batched parsing and add those image-pipeline timings before profiling another episode.

> Right. How much telemetry for perception do we have - probably none? Can we wire that up first? In `v2-2.py` - update the `name` entry for the `Agent` and also update `NOTES.md` with our progress.

<details><summary>2 previous messages</summary>

> We currently have no perception telemetry: the A2 log only covers the planner. I’ll inspect `v2-2.py`, add lightweight parse-stage timings and model-load/cell-count diagnostics, update the agent name, and record the progress in `NOTES.md`.
>
> <details><summary>Edited 2 files, ran 6 commands</summary>
>
> - Ran `Get-Item v2-2.py, NOTES.md | Select-Object Name,Length,LastWriteTime; Get-Content v2-2.py | Select-Object -First 100; rg -n -C 3 "def __init__|def parse|def split_cells|def predict|def info\(|name\"|tile_model|torch" v2-2.py; Get-Content NOTES.md | Select-Object -Last 55`
> - Ran `Get-ChildItem -Name v2-*; Test-Path v2-2.py; Test-Path NOTES.md; Get-Location`
> - Ran `Get-Content v2-2.py -TotalCount 120; rg -n -C 3 "def __init__|def parse|def split_cells|def predict|def info\(|tile_model|torch" v2-2.py; Get-Content NOTES.md -Tail 50`
> - Ran `Get-Content v2-2.py | Select-Object -Skip 1648 -First 145; Get-Content v2-2.py | Select-Object -Skip 1760 -First 70; rg -n "_last_search_stats|_search_stats_history|telemetry\(" v2-2.py`
> - Ran `Get-Content v2-2.py | Select-Object -Skip 390 -First 62; Get-Content v2-2.py | Select-Object -Skip 1300 -First 80; Get-Content v2-2.py | Select-Object -Skip 1580 -First 82`
> - Wrote `./v2-2.py` (+43 -7)
> - Wrote `./NOTES.md` (+19 -0)
> - Wrote `./v2-2.py` (+2 -1)
> - Ran `python -m py_compile v2-2.py; rg -n -C 2 "perception telemetry|tile_inference_ms|Task 2 image agent|Latest local" v2-2.py NOTES.md`
>
> </details>
</details>

Perception telemetry is now wired into [v2-2.py](./v2-2.py), and progress is recorded in [NOTES.md](./NOTES.md).

Each image-mode turn will now include:

- `parse_ms`
- `split_ms`
- `tile_inference_ms` — currently the old template matcher; later becomes the batched CNN stage
- `gridstate_init_ms`
- cell, decoded-entity, and agent counts
- `model_loaded`

These metrics are merged into the existing per-turn telemetry rows, and `Agent.info()` now shows a compact perception summary. I also updated the displayed agent name to identify it as the instrumented Task 2 image agent.

`v2-2.py` compiles successfully.

> Then this cell?
> ```python
> from pathlib import Path
> from public_levels.intro import build_level_maze_turns
> import pandas as pd
>
> env = create_env(
>     build_level_maze_turns,
>     observation_type="image",
>     seed=42,
> )
>
> agent = Agent()
> state, _ = env.reset()
> win = lose = False
> total_reward = 0
>
> while not (win or lose):
>     action = agent.step(state)
>     state, reward, win, lose, _ = env.step(action)
>     total_reward += reward
>
> telemetry = pd.DataFrame(agent.telemetry())
>
> memory_columns = [
>     "rss_mb",
>     "rss_peak_mb",
>     "cache_distance_entries",
>     "cache_static_plan_actions",
>     "cache_powerup_plan_actions",
>     "cache_keydoor_plan_actions",
>     "cache_box_plan_actions",
>     "cache_fallback_plan_actions",
> ]
> available_memory_columns = [
>     column for column in memory_columns if column in telemetry.columns
> ]
>
> if available_memory_columns and not telemetry.empty:
>     memory_telemetry = telemetry[available_memory_columns]
>     memory_summary = pd.DataFrame(
>         {"max": memory_telemetry.max(), "last": memory_telemetry.iloc[-1]}
>     ).to_string()
> else:
>     memory_summary = "No memory telemetry was recorded."
>
> output_path = Path("a2-task2-telemetry.txt")
> output_path.write_text(
>     "\n".join(
>         [
>             f"win={win}, lose={lose}, total_reward={total_reward}",
>             "",
>             "LATEST AGENT INFO",
>             str(agent.info()),
>             "",
>             "PER-TURN TELEMETRY",
>             telemetry.to_string(index=False),
>             "",
>             "SUMMARY STATISTICS",
>             telemetry.describe().to_string(),
>             "",
>             "MEMORY AND CACHE SUMMARY",
>             memory_summary,
>         ]
>     ),
>     encoding="utf-8",
> )
>
> print(f"Telemetry written to: {output_path.resolve()}")
> ```

Yes—run that cell after swapping in `v2-2.py`. It will already capture the new perception columns because `agent.telemetry()` includes them automatically.

I’d add an explicit perception section after the memory summary:

```python
perception_columns = [
    "parse_ms",
    "split_ms",
    "tile_inference_ms",
    "gridstate_init_ms",
    "perception_cells",
    "perception_entities",
    "perception_agents",
    "model_loaded",
]
available_perception_columns = [
    column for column in perception_columns if column in telemetry.columns
]

if available_perception_columns and not telemetry.empty:
    perception_telemetry = telemetry[available_perception_columns]
    perception_summary = pd.DataFrame(
        {
            "mean": perception_telemetry.mean(),
            "max": perception_telemetry.max(),
            "last": perception_telemetry.iloc[-1],
        }
    ).to_string()
else:
    perception_summary = "No perception telemetry was recorded."
```

Then add these lines to the `"\n".join(...)` list just before `"MEMORY AND CACHE SUMMARY"`:

```python
"",
"PERCEPTION SUMMARY",
perception_summary,
```

The current per-turn table and full `describe()` output will also include the new fields, but this makes the bottleneck obvious at a glance.

> Dumped. What do we see?

<details><summary>2 previous messages</summary>

> I’ll read the updated A2 dump and separate image parsing cost from planning cost.
>
> <details><summary>Explored a file</summary>
>
> - Read `./a2-task2-telemetry.txt`
>
> </details>
</details>

The timeout cause is now clear: perception, not planning.

- Mean parse time: **1.89 s per turn**
- Range: **1.62–2.49 s per turn**
- Of that, splitting costs only **~0.10 ms**; the per-cell template classifier costs essentially all of it.
- Planner work is negligible: first search **1.23 ms**, then **0.00–0.47 ms** while replaying.
- `model_loaded=0`: the TorchScript CNN is not being used yet.

On this 63-cell board, the current matcher opens the floor asset plus every entity asset separately for every cell—roughly 14 × 63 ≈ **882 image-file loads per turn**. That explains the 1–2.5-second latency and Coursemology timeouts.

The next change should replace `split_cells()` + nested `predict()` calls with a single batched TorchScript inference pass over all 63 crops, then decode its 14 logits per tile.

> Proceed with the changes - changes to `Agent` definition goes only in `v2-3.py` which currently is a copy of `v2-2.py` for organization and submission purposes. If TorchScript file is needed to be edited, make a copy. Do not directly edit the original file (keep a history record).

<details><summary>4 previous messages</summary>

> I’ll implement the CNN-backed, batched parser exclusively in `v2-3.py`, preserving `v2-2.py` and the original TorchScript artifact untouched. I’ll first verify the downloaded model location and recover the training-time preprocessing so inference matches it.
>
> <details><summary>Ran 2 commands</summary>
>
> - Ran `Get-Item v2-3.py, v2-2.py, NOTES.md | Select-Object Name,Length,LastWriteTime; Get-ChildItem -Recurse -File exports, checkpoints -ErrorAction SilentlyContinue | Select-Object FullName,Length,LastWriteTime; rg -n -C 5 "class SyntheticTileDataset|IMAGE_SIZE|ToTensor|interpolate|resize|RGBA|Normalize|LABELS|DECODER_THRESHOLDS" task-2.ipynb; rg -n -C 3 "class .*Entity|def __init__" . -g "*.py" | Select-Object -First 240`
> - Ran `Get-Content task-2.ipynb | Select-Object -Skip 480 -First 35; rg -n "class LockedDoorEntity|class AgentEntity|class GemEntity|class ExitEntity|class WallEntity" "$env:LOCALAPPDATA\Programs\Python\Python*" -g "*.py" 2>$null; rg -n "class LockedDoorEntity|class AgentEntity|class GemEntity|class ExitEntity|class WallEntity" . -g "*.py"`
>
> </details>
>
> The model was trained on raw RGBA pixels scaled to `[0, 1]` and resized to `64×64`, with no normalization—so we can reproduce preprocessing exactly. I’m replacing the template matcher in `v2-3.py` with batched crop preprocessing, one TorchScript forward call, thresholded multi-label decoding, and per-stage timing.
>
> <details><summary>Edited 2 files, ran a command</summary>
>
> - Wrote `./v2-3.py` (+31 -0)
> - Wrote `./v2-3.py` (+62 -49)
> - Wrote `./v2-3.py` (+11 -10)
> - Wrote `./v2-3.py` (+10 -8)
> - Wrote `./NOTES.md` (+22 -0)
> - Wrote `./v2-3.py` (+0 -2)
> - Ran `python -m py_compile v2-3.py; rg -n "DEFAULT_ASSET_ROOT|Image\.open|def predict\(" v2-3.py; rg -n -C 2 "Batched CNN parser|v2-3.py|preprocess_ms|cnn_ms|decode_ms" NOTES.md v2-3.py`
> - Wrote `./v2-3.py` (+3 -1)
>
> </details>
</details>

Implemented the batched CNN parser in [v2-3.py](./v2-3.py), leaving [v2-2.py](./v2-2.py) unchanged as the template-matcher baseline. The original TorchScript file was not edited or copied because it does not need modification.

Changes in `v2-3.py`:

- Removes the per-cell public-asset/template matcher from the image path.
- Splits the board, converts each RGBA crop exactly as during training—`float32`, `[0,1]`, CHW, bilinear resize to `64×64`.
- Runs all board tiles in one TorchScript forward batch.
- Decodes all 14 independent labels using the locked thresholds: default `0.50`, `gem=0.40`, `ghost=0.90`.
- Reconstructs layered cells, including agent-on-item combinations.
- Records `preprocess_ms`, `cnn_ms`, `decode_ms`, and first-turn-only `model_load_ms`, alongside the existing parse/planning telemetry.
- Updates the displayed agent name to identify the batched TorchScript parser.

I also updated [NOTES.md](./NOTES.md) with the result and validation target.

`v2-3.py` passes static compilation. This workspace does not contain the downloaded model artifact, so runtime validation still needs you to place it at:

```text
exports/tile_multilabel_cnn_best.torchscript.pt
```

Then rerun the A2 image telemetry cell. The decisive check is that `model_loaded=1`, `cnn_ms` is populated, the board still has exactly one agent, and `tile_inference_ms` drops sharply from the prior 1.6–2.5 seconds per turn.

> A2 passed, a few A-tier levels still timed out (A3, A5, A7-A10), but there's an improvement. `{level}-task2-telemetry.txt for level in [a2, a3, a5, a7, a10]` are dumped.

<details><summary>2 previous messages</summary>

> I’ll compare the five telemetry dumps to distinguish remaining perception cost from planner-specific slowdowns and identify the next highest-impact issue.
>
> <details><summary>Ran a command</summary>
>
> - Ran `Get-ChildItem -File -Filter "a*-task2-telemetry.txt" | Select-Object Name,Length,LastWriteTime; rg -n "^win=|^\{'name'|PERCEPTION SUMMARY|^parse_ms|^mean |^max " a2-task2-telemetry.txt a3-task2-telemetry.txt a5-task2-telemetry.txt a7-task2-telemetry.txt a10-task2-telemetry.txt`
>
> </details>
</details>

The local dumps are much better than the earlier Coursemology outcome—and, notably, all five local episodes actually won:

| Level | Result | Reward | Mean parse time | Mean CNN time | Turns |
|---|---:|---:|---:|---:|---:|
| A2 | win | -21 | 303 ms | 251 ms | 18 |
| A3 | win | -63 | 381 ms | 331 ms | 22 |
| A5 | win | -39 | 390 ms | 332 ms | 14 |
| A7 | win | -42 | 365 ms | 311 ms | 15 |
| A10 | win | -84 | 182 ms | 153 ms | 29 |

So reconstruction is correct enough for these levels: every dump reports exactly one agent and `model_loaded=1`.

What remains:

- The asset-template bottleneck is gone. Splitting is below 1 ms; decoding is roughly 0.04–0.09 ms.
- CNN inference now dominates—about **250–330 ms/turn** on 99-cell boards, and **153 ms/turn** on A10’s 49-cell board.
- Planning is still negligible: usually below 1 ms, with only tiny initial searches.
- A3’s approximate perception time alone is `22 × 381 ms ≈ 8.4 seconds`, which readily explains a wall-clock timeout despite eventually winning locally.

The next meaningful optimization is therefore not planner tuning or decoder cleanup: it is to avoid running full-board CNN perception every real turn. These A levels have mostly static boards and replayable plans, so infer the initial board once, retain the reconstructed state/plan, and only resynchronize from images when a mechanic actually requires it.

> So the current implementation is eager-loading? And we'll be doing lazy-loading?

Not quite—two different things are involved.

The TorchScript model itself is already lazy-loaded:

- `Agent()` does not load it.
- The first call to `parse()` triggers `_get_tile_model()`.
- It remains cached for the rest of the episode.
- The telemetry’s first-turn-only `model_load_ms` measures that cost.

What is currently eager is board perception:

```text
every environment turn
  → split every tile
  → preprocess every tile
  → run the CNN over the whole board
  → rebuild the whole GridState
```

The next optimization is lazy or selective perception: parse the initial image fully, retain the reconstructed board/plan, and skip full CNN inference on later turns when the agent already knows the state evolution. We would only re-parse/resynchronize when needed for mechanics where visual confirmation matters.

> Proceed in `v2-4.py`. I'll then check again.

<details><summary>2 previous messages</summary>

> I’ll add selective perception to `v2-4.py`: fully parse the initial image, then reuse the cached reconstructed state only while a complete replayable plan remains. If a plan is exhausted or a new episode starts, it resumes full image parsing. This is safer than assuming every image episode is static.
>
> <details><summary>Edited 2 files, ran 3 commands</summary>
>
> - Ran `Get-Item v2-4.py | Select-Object Name,Length,LastWriteTime; rg -n -C 3 "def step\(|_static_plan|_powerup_plan|_keydoor_plan|_mixed_plan|_box_plan|_fallback_plan" v2-4.py | Select-Object -First 280; Get-Content v2-4.py | Select-Object -Skip 1300 -First 180; Get-Content v2-4.py | Select-Object -Skip 1690 -First 120`
> - Wrote `./v2-4.py` (+35 -0)
> - Wrote `./v2-4.py` (+31 -2)
> - Wrote `./v2-4.py` (+3 -1)
> - Wrote `./NOTES.md` (+17 -0)
> - Ran `python -m py_compile v2-4.py; rg -n -C 3 "reused_image_state|_has_replayable_image_plan|perception_reused|Selective perception" v2-4.py NOTES.md; Get-Content v2-4.py | Select-Object -Skip 1390 -First 62`
> - Ran `python -c "from grid_adventure.grid import GridState; import inspect; print(inspect.getsourcefile(GridState)); print(getattr(GridState, '__dataclass_params__', None)); print(GridState.__slots__ if hasattr(GridState, '__slots__') else 'no slots')"`
>
> </details>
</details>

Implemented selective perception in [v2-4.py](./v2-4.py) only. [v2-3.py](./v2-3.py) remains unchanged.

How it works:

- First image of each episode: full crop → preprocess → batched TorchScript → decode → plan.
- Subsequent image turns: if the same episode still has a complete cached route, it skips all image processing and replays the plan.
- Reset, changed level metadata, or no remaining route: it reverts safely to a full live parse.
- Reused perception deliberately bypasses dynamic-cache reconciliation, because it operates only while following the planner’s already-computed deterministic suffix.

Telemetry now adds:

- `perception_reused=0` on actual CNN parses.
- `perception_reused=1` on cached-plan turns.
- Reused rows report `0` for parse, preprocess, CNN, and decode time.

I also updated [NOTES.md](./NOTES.md) with the v2-4 design and expected validation outcome.

`v2-4.py` compiles successfully here. When you rerun A2/A3/A5/A7/A10, a normal successful episode should show exactly one `perception_reused=0` row—usually the initial action—and all later replay rows as `1`.

> This cell dumps telemetry for task 2:
> ```python
> from pathlib import Path
> from public_levels.intro import build_level_combined_mechanics
> import pandas as pd
>
> env = create_env(
>     build_level_combined_mechanics,
>     observation_type="image",
>     seed=42,
> )
>
> agent = Agent()
> state, _ = env.reset()
> win = lose = False
> total_reward = 0
>
> while not (win or lose):
>     action = agent.step(state)
>     state, reward, win, lose, _ = env.step(action)
>     total_reward += reward
>
> telemetry = pd.DataFrame(agent.telemetry())
>
> memory_columns = [
>     "rss_mb",
>     "rss_peak_mb",
>     "cache_distance_entries",
>     "cache_static_plan_actions",
>     "cache_powerup_plan_actions",
>     "cache_keydoor_plan_actions",
>     "cache_box_plan_actions",
>     "cache_fallback_plan_actions",
> ]
> available_memory_columns = [
>     column for column in memory_columns if column in telemetry.columns
> ]
>
> if available_memory_columns and not telemetry.empty:
>     memory_telemetry = telemetry[available_memory_columns]
>     memory_summary = pd.DataFrame(
>         {"max": memory_telemetry.max(), "last": memory_telemetry.iloc[-1]}
>     ).to_string()
> else:
>     memory_summary = "No memory telemetry was recorded."
>
> perception_columns = [
>     "parse_ms",
>     "split_ms",
>     "tile_inference_ms",
>     "gridstate_init_ms",
>     "perception_cells",
>     "perception_entities",
>     "perception_agents",
>     "model_loaded",
> ]
> available_perception_columns = [
>     column for column in perception_columns if column in telemetry.columns
> ]
>
> if available_perception_columns and not telemetry.empty:
>     perception_telemetry = telemetry[available_perception_columns]
>     perception_summary = pd.DataFrame(
>         {
>             "mean": perception_telemetry.mean(),
>             "max": perception_telemetry.max(),
>             "last": perception_telemetry.iloc[-1],
>         }
>     ).to_string()
> else:
>     perception_summary = "No perception telemetry was recorded."
>
> output_path = Path("b2-task2-telemetry.txt")
> output_path.write_text(
>     "\n".join(
>         [
>             f"win={win}, lose={lose}, total_reward={total_reward}",
>             "",
>             "LATEST AGENT INFO",
>             str(agent.info()),
>             "",
>             "PER-TURN TELEMETRY",
>             telemetry.to_string(index=False),
>             "",
>             "SUMMARY STATISTICS",
>             telemetry.describe().to_string(),
>             "",
>             "MEMORY AND CACHE SUMMARY",
>             memory_summary,
>             "",
>             "PERCEPTION SUMMARY",
>             perception_summary,
>         ]
>     ),
>     encoding="utf-8",
> )
>
> print(f"Telemetry written to: {output_path.resolve()}")
> ```
>
> I see myself always manually changing the level name and the import.
>
> In fact, `public_levels\catalog.py` is where I copy from. Can this be automated? Write me a new cell - I give `B2` - the imports and the telemetry file name follows.

<details><summary>2 previous messages</summary>

> I’ll inspect the public-level catalog’s naming convention and give you a drop-in notebook cell where one code such as `"B2"` selects the builder and derives the telemetry filename automatically.
>
> <details><summary>Ran a command</summary>
>
> - Ran `Get-Content -Raw public_levels\catalog.py; rg -n "build_level_combined_mechanics|B2|catalog" public_levels -g "*.py"`
>
> </details>
</details>

Yes—and this also avoids a subtle mismatch in the current cell: `build_level_combined_mechanics` is **A10**, not B2. The following cell resolves the builder directly from `public_levels.catalog`, so the code, builder, expected reward, and telemetry filename remain aligned.

```python
from pathlib import Path

import pandas as pd

from public_levels.catalog import (
    PUBLIC_LEVEL_BUILDERS,
    PUBLIC_LEVEL_MAX_REWARDS,
)

# Change only this value.
LEVEL_CODE = "B2".upper()
SEED = 42

matching_labels = [
    label
    for label in PUBLIC_LEVEL_BUILDERS
    if label.split(maxsplit=1)[0].upper() == LEVEL_CODE
]

if len(matching_labels) != 1:
    available_codes = ", ".join(
        label.split(maxsplit=1)[0] for label in PUBLIC_LEVEL_BUILDERS
    )
    raise ValueError(
        f"Unknown or ambiguous level code {LEVEL_CODE!r}. "
        f"Available codes: {available_codes}"
    )

level_label = matching_labels[0]
level_builder = PUBLIC_LEVEL_BUILDERS[level_label]
expected_reward = PUBLIC_LEVEL_MAX_REWARDS[level_label]
output_path = Path(f"{LEVEL_CODE.lower()}-task2-telemetry.txt")

print(f"Running {level_label}")
print(f"Expected best reward: {expected_reward}")
print(f"Telemetry file: {output_path.resolve()}")

env = create_env(
    level_builder,
    observation_type="image",
    seed=SEED,
)

agent = Agent()
state, _ = env.reset()
win = lose = False
total_reward = 0.0

while not (win or lose):
    action = agent.step(state)
    state, reward, win, lose, _ = env.step(action)
    total_reward += reward

telemetry = pd.DataFrame(agent.telemetry())

memory_columns = [
    "rss_mb",
    "rss_peak_mb",
    "cache_distance_entries",
    "cache_static_plan_actions",
    "cache_powerup_plan_actions",
    "cache_keydoor_plan_actions",
    "cache_mixed_plan_actions",
    "cache_box_plan_actions",
    "cache_fallback_plan_actions",
]
perception_columns = [
    "parse_ms",
    "split_ms",
    "preprocess_ms",
    "cnn_ms",
    "decode_ms",
    "tile_inference_ms",
    "gridstate_init_ms",
    "model_load_ms",
    "perception_reused",
    "perception_cells",
    "perception_entities",
    "perception_agents",
    "model_loaded",
]

def summarize_columns(columns, summary_kind):
    available = [column for column in columns if column in telemetry.columns]
    if not available or telemetry.empty:
        return f"No {summary_kind.lower()} telemetry was recorded."

    values = telemetry[available]
    return pd.DataFrame(
        {
            "mean": values.mean(),
            "max": values.max(),
            "last": values.iloc[-1],
        }
    ).to_string()

memory_summary = summarize_columns(memory_columns, "Memory/cache")
perception_summary = summarize_columns(perception_columns, "Perception")
statistics_summary = (
    telemetry.describe().to_string()
    if not telemetry.empty
    else "No per-turn telemetry was recorded."
)

output_path.write_text(
    "\n".join(
        [
            f"level={level_label}",
            f"seed={SEED}",
            f"expected_best_reward={expected_reward}",
            f"win={win}, lose={lose}, total_reward={total_reward}",
            "",
            "LATEST AGENT INFO",
            str(agent.info()),
            "",
            "PER-TURN TELEMETRY",
            telemetry.to_string(index=False),
            "",
            "SUMMARY STATISTICS",
            statistics_summary,
            "",
            "MEMORY AND CACHE SUMMARY",
            memory_summary,
            "",
            "PERCEPTION SUMMARY",
            perception_summary,
        ]
    ),
    encoding="utf-8",
)

print(f"Telemetry written to: {output_path.resolve()}")
```

With `LEVEL_CODE = "B2"`, this selects **`B2 The Vault`** and writes `b2-task2-telemetry.txt`. Change only that one assignment for any A/B/C public level.

> B2 - B4, B6, B10 timed out, all A-tier levels passed. New telemetry dumped in `{level}-task2-telemetry.txt`- what else do we see?
> Cell output for some of the close calls: (pasted)
>
> (Update our progress and our next steps in `NOTES.md`. We'll end the thread here and continue in a new one, context is growing.)
>
> User context
>
> Attachments:
> - <div> <style scoped> .dataframe tbody tr th:only-of-type { vertical-align: midd…: `~/.codex/attachments/fd7033e5-c7f5-4190-9133-4770d8e4021c/Pasted text.txt`

<details><summary>4 previous messages</summary>

> I’ll compare the new B-tier telemetry with the pasted close-call output, identify whether the remaining timeouts are perception, first-search, or plan-replay related, then capture the findings and next steps in `NOTES.md`.
>
> <details><summary>Ran 2 commands</summary>
>
> - Ran `Get-Content -Raw "C:\Users\User\.codex\attachments\fd7033e5-c7f5-4190-9133-4770d8e4021c\Pasted text.txt"; Get-ChildItem -File -Filter "b*-task2-telemetry.txt" | Select-Object Name,Length,LastWriteTime; rg -n "^level=|^expected_best_reward|^win=|^\{'name'|PERCEPTION SUMMARY|^parse_ms|^mean |^max " b2-task2-telemetry.txt b3-task2-telemetry.txt b4-task2-telemetry.txt b6-task2-telemetry.txt b10-task2-telemetry.txt 2>$null`
> - Ran `Get-Content b2-task2-telemetry.txt | Select-Object -First 22; Get-Content b4-task2-telemetry.txt | Select-Object -First 22; Get-Content b6-task2-telemetry.txt | Select-Object -First 22; Get-Content b10-task2-telemetry.txt | Select-Object -First 22; Get-Content b2-task2-telemetry.txt | Select-Object -Skip 70 -First 20; Get-Content b4-task2-telemetry.txt | Select-Object -Skip 160 -First 20`
>
> </details>
>
> The selective-replay mechanism is behaving as intended: each dumped B-tier episode has exactly one expensive image parse and then reuses perception for 97.5–99.2% of turns. I’m recording the remaining timeout pattern and the next measurement needed to isolate evaluator/environment overhead from the agent itself.
>
> <details><summary>Edited a file, ran a command</summary>
>
> - Wrote `./NOTES.md` (+25 -0)
> - Ran `Get-Content NOTES.md -Tail 48`
>
> </details>
</details>

The key finding is that `v2-4` is now functionally correct and selective perception works; the remaining failures are deadline overruns, not bad reconstruction or planning.

| Level | Local result | Initial parse | Initial planning | Coursemology runtime | Coursemology result |
|---|---:|---:|---:|---:|---|
| B2 | win, -65 | 1.082 s | 582 ms | 5.87 s | timeout |
| B3 | win, -315 | 1.190 s | 51 ms | 5.75 s | timeout |
| B4 | win, -387 | 901 ms | 50 ms | 8.15 s | timeout |
| B6 | win, -213 | 1.078 s | 13 ms | 5.21 s | timeout |
| B10 | win, -162 | 1.117 s | 318 ms | 5.19 s | timeout |

The perception-cache evidence is strong:

- Each episode performs exactly one full board parse.
- All later turns show `perception_reused=1`.
- Subsequent crop, preprocessing, CNN, and decode time is zero.
- Subsequent planner calls are about `0.01 ms`.
- Every local reconstruction reports exactly one agent and reaches the known-best reward.

Coursemology still reports `win=True` and the correct reward for the five failing B levels, but assigns zero effective performance because its 5-second gameplay deadline is exceeded. So the next question is not “can the model see or plan?”—it can. We need to measure the entire local episode wall time, separately timing `agent.step(...)` and `env.step(...)`, to determine whether the remaining time is environment/image overhead or submission-side overhead outside the planner telemetry.

I updated [NOTES.md](./NOTES.md) with these results, the exact measurements, and the next-thread plan.
