# Task 1 notes

`public_levels/catalog.py` maps public names to level builders and records known-best scores. Level layouts live in `public_levels/intro.py` and `public_levels/challenges.py`.

## Version history

| Version | Change |
| --- | --- |
| `v1-0` | Uniform-cost search. |
| `v1-1` | First-action A* with `str(grid)` state keys. |
| `v1-2` | Real-state caching. |
| `v1-3` | MST heuristic. |
| `v1-4` | Gem-order heuristic with Manhattan/Speed estimates. |
| `v1-5` | Reduced wall/gem/exit cache. |
| `v1-6` | Cached wall-BFS gem-order heuristic. |
| `v1-7` | Compact static A* over position and remaining gems. |
| `v1-8` | Compact power-up planner. |
| `v1-9` | Full-state fallback reconstructs and replays a winning plan. |
| `v1-10` | Optional coins ignored on static maps. |
| `v1-11` | Compact keys-and-doors planner. |
| `v1-12` | Compact static planner reconstructs and replays its complete plan. |
| `v1-12-1` | Adds optional RSS and cache-footprint telemetry. |
| `v1-13` | Compact power-up planner handles zero or repeated power-ups; repeated shields stack their uses. Adds compact Sokoban planner for static boxes. |
| `v1-14` | Adds compact mixed-mechanics A* for keys/doors, lava, repeated power-ups, and gems. |
| `v1-15` | First bounded optional-coin detour experiment; retained as a stepping stone only. |
| `v1-16` | Bounded coin-bundle subset DP: considers 12 promising coins, inserts explicit `PICK_UP` actions, and retains the route only when it improves the mandatory-plan score. Current version. |

## What the agent supports now

- Static walls, gems, exits, and optional coins: compact A* state `(position, remaining_gem_mask)`. On no-gem coin levels, a bounded 12-coin subset-DP post-pass compares a reward-aware route against the mandatory compact route. Coins never expand the main A* state.
- Static routes are reconstructed once and replayed. B3 reaches known-best `-315` in about 1.0–1.4 s rather than repeatedly solving a shrinking suffix.
- Zero or repeated ghost, boots, and shield power-ups: explicit `PICK_UP`, effect timers, two-substep boots moves, lava damage, health, and stacking shield charges. This fixes A8, B5, B7, and B8.
- Static keys and locked doors: compact state `(position, remaining_gems, remaining_keys, opened_doors, held_keys)` with explicit `PICK_UP` and `USE_KEY` following the engine's adjacent-door unlock order. B4 reaches known-best `-387` in about 2.4–2.7 s.
- Static box-only maps: compact Sokoban state `(position, sorted_box_positions, remaining_gems)` with legal pushes. This fixes B6.
- Mixed static keys/doors, lava, and power-ups: compact state adds remaining power-ups, effect timers, shield uses, health, keys, opened doors, and held keys. This fixes B10 without `GridState` cloning.
- All other mechanics: wall-aware, full-`GridState` A* fallback. It reconstructs and replays a complete solution rather than performing the same expensive simulation every turn; this fixes A10.

The planner selects the narrowest applicable model: replayed static, mixed mechanics, key/door, power-up, boxes, then full-state fallback. Compact action matching must use exact `UP`, `DOWN`, `LEFT`, and `RIGHT` names; suffix matching accidentally included `PICK_UP` and disabled the fast path.

## Telemetry

`Agent.telemetry()` emits one record per real environment turn; the notebook diagnostic cell writes it to `<level>-telemetry.txt`.

- `search_ms`, `popped`, `visited`, `successors`, and `max_frontier` measure search size and time.
- `grid_step_ms`, `key_ms`, and `heuristic_ms` locate planning cost. High `grid_step_ms`/`key_ms` means avoid full-state simulation/serialization; high `heuristic_ms` means cache or simplify the heuristic.
- `cache_distance_entries` counts persistent wall-BFS entries. The `cache_*_plan_actions` fields give the remaining size of every stored compact or fallback plan.
- When `psutil` is installed, `rss_mb` and `rss_peak_mb` give sampled process resident memory. They are intentionally coarse, low-overhead episode diagnostics; cache counters identify the likely source of growth. Telemetry remains functional without `psutil`.

## Current results

- Known-best: A3 `-63`, A4 `-33`, A10 `-84`, B3 `-315`, B4 `-387`.
- v1-16 validation: all public GridState levels pass at best effective performance. A2 and B2 now use the bounded coin-bundle policy; B2 reaches its known-best `-65`.
- v1-13 validation: B5 wins at `-210` (70-action plan), B7 at `-111` (37-action plan), and B8 at `-93` (31-action plan). Their compact searches take about 6 ms, 90 ms, and 5 ms respectively in a fresh course-environment process.
- v1-13 validation: B6 wins at `-213` with a 71-action compact Sokoban plan (564 popped, 712 visited states in a fresh course-environment process).
- v1-14 validation: B10 wins at `-162` with a 54-action mixed-mechanics plan. Its compact initial search takes roughly 60–90 ms, replacing the previous ~98-second full-state fallback search.
- Full public gridstate suite: all 22 levels pass. Measured suite runtimes range from 0.02 s to 2.66 s; B10 completes in 0.91 s.

# Task 2

## Goal

Task 2 keeps the Task 1 planner and replaces only its structured-state input.
`ImageObservation` supplies an RGBA board image plus limited structured metadata;
the agent must reconstruct a usable `GridState` before planning. Graded cases use
unseen visual variants of known entity classes, so exact sprite/template matching
is not sufficient.

```text
ImageObservation
  |
  +-- image: RGBA board -------------------------------------------+
  |                                                                |
  +-- info: grid size, turn, score, health, inventory/status -----|--+
                                                                   |  |
                                                                   v  v
                                                     known grid dimensions
                                                                   |
                                                                   v
                                                        split into tile crops
                                                                   |
                                                                   v
                                                     batched multi-label CNN
                                                                   |
                                                                   v
                                                   labels + confidences/cell
                                                                   |
                                                                   v
                                                structural/layer constraint pass
                                                                   |
                                                                   v
                                      Python entities + `GridState` adapter
                                                                   |
                                                                   v
                                                   replayed Task 1 planner
                                                                   |
                                                                   v
                                                                `Action`
```

## Already available

- `ImageObservation["info"]["config"]` supplies `width`, `height`, seed, and
  turn limit. Tile boundaries can therefore be split deterministically; board
  detection is not an ML problem.
- `info` also supplies current turn, score, game phase/message, and agent
  health/inventory/status. Treat these as the source of truth rather than
  attempting to infer numbers or effects from pixels.
- `Agent.parse()`, `split_cells()`, and `predict()` in `v1-16.py` already show
  the required adapter shape. `predict()` is only a public-asset `_1` template
  matcher and must be replaced.
- `data/assets/` contains public visual variants for all classes: floor, wall,
  lava, exit, human, gem, coin, key, locked/opened door, box, boots, ghost,
  and shield.
- `ImageRenderer`, `DEFAULT_ASSET_ROOT`, `create_env(...,
  observation_type="image")`, and Task 2 public checks can create paired
  rendered observations and true `GridState` labels locally.
- `utils.generate_torch_loader_snippet(...)` can turn a trained PyTorch model
  into an inline TorchScript loader for Coursemology submission; no separate
  model file can be submitted.

## Perception architecture

Use a compact per-tile CNN, evaluated as one batch for the whole board. Resize
each crop to a fixed small resolution (initially `48x48` or `64x64`), then use
three to four convolution blocks, global-average pooling, and independent
sigmoid output logits. Keep the model well below a few hundred thousand
parameters so CPU inference and embedded submission remain cheap.

The output is a multi-label semantic vector per cell, not a single softmax
class. Read each label independently using calibrated confidence thresholds.
This supports layered cells such as agent-on-exit or agent-on-collectible.

```text
tile RGBA crop --> small CNN --> [wall, lava, exit, locked/opened door,
                                  box, agent, gem, coin, key,
                                  boots, ghost, shield, empty/floor]
                                      |             |
                                      +-- sigmoid --+-- confidence thresholds
```

The decoder maps accepted labels to the corresponding Python entity classes,
combines valid layers, injects dynamic fields from `info`, and creates the
`GridState` expected by the existing planner. Apply simple board constraints:
exactly one agent, at least one exit, and no incompatible entity combinations.

## Dataset and validation pipeline

1. Generate labelled tile crops synthetically by compositing valid entity
   layers over randomly selected floor variants from `data/assets/`.
2. Generate labelled board examples by creating valid `GridState`s and
   rendering them with the official renderer. The source `GridState` provides
   exact per-cell, per-layer labels.
3. Augment only visual presentation: brightness/contrast/saturation changes,
   small translation/crop shifts, interpolation/scale variation, light blur,
   noise, and compression artifacts. Never change game semantics.
4. Split train/validation by source asset variant, not generated image. Hold
   out variants from every entity class to test the required visual
   generalization.
5. Train and export in Google Colab, then verify the exported inline
   TorchScript model inside the local agent before relying on it.

Validation has three levels: held-out tile classification, exact reconstructed
board semantics against paired rendered `GridState`s, and end-to-end image-mode
episodes that should match the Task 1 planner's wins and scores.

## Observability

Keep visual debug artifacts off during normal evaluation, but add bounded,
lightweight telemetry and optional diagnostics:

- Timings: `split_ms`, `cnn_ms`, `decode_ms`, `parse_ms`, followed by the
  existing planning timings.
- Per-class confidence summaries and predicted entity counts per board.
- Structural checks: agent count, exit count, incompatible layer count, and
  whether the parser produced a trustworthy state.
- Offline validation: per-class precision/recall and a confusion matrix,
  including empty-floor and layers.
- Optional debug overlay: original board with grid lines, decoded labels and
  confidences, and low-confidence/invalid cells highlighted.
- A compact parser trust score in `info()` so perception failures are clearly
  distinguished from planner failures. Do not retain raw image history in the
  agent.

## Current implementation progress (2026-11-05)

- Colab notebook: `task-2.ipynb`. Assets are mounted from Drive and split by
  source PNG variant, not generated image: 80% train / 20% validation per
  class. A source variant is never in both splits.
- The synthetic dataset generates `64x64` RGBA tiles on demand. It composites
  a floor and valid entity layers, including agent-on-floor and agent-on-item
  cases. Training-only visual augmentation applies minor scale/crop,
  brightness/contrast/saturation, blur, JPEG artefacts, and light noise.
- Labels are 14-way multi-label outputs: `floor`, `wall`, `lava`, `exit`,
  `locked`, `opened`, `box`, `agent`, `gem`, `coin`, `key`, `boots`, `ghost`,
  and `shield`. `floor` means a bare empty tile only; it is not set behind an
  entity layer.
- Model: compact RGBA CNN (~185k parameters), trained with
  `BCEWithLogitsLoss` for 15 epochs on 24,000 synthetic tiles per epoch and
  validated on 6,000 held-out-variant tiles. Best held-out macro-F1 was
  `0.9994` at epoch 15. The best checkpoint was saved in Colab Drive as
  `checkpoints/tile_multilabel_cnn_best.pt`.
- Default threshold inspection found 7/6,000 tiles with any error: 7 ghost
  false positives and 1 gem false negative, all concentrated on visually
  similar agent-on-gem examples. Locked decoder thresholds are default `0.50`,
  with `gem=0.40` and `ghost=0.90`; this achieved 0/6,000 held-out synthetic
  tile errors. Do not use the sweep's arbitrary `0.95` tie-break thresholds
  for otherwise-perfect labels.
- Export: the course helper `generate_torch_loader_snippet(...)` writes the
  embedded loader source to `exports/tile_model_loader.py` and verifies it by
  executing the saved file and comparing logits against the checkpoint model.
  The generated `get_model(...)` must ultimately be pasted inline at module
  scope in the submission; `v2-1-submit.py` has a TODO placeholder for it.
- Submission cleanup: `v2-1-submit.py` has had public telemetry/RSS/`info()`
  diagnostics removed and currently compiles locally.

## Current Task 2 blocker

Coursemology results were poor: only the first test case completed; every
other case timed out. This is the active issue for the next thread. Do not
assume the synthetic tile metrics imply usable end-to-end performance. Audit
the submission path for repeated model loading, per-cell/non-batched inference,
template-matcher fallback, parser reconstruction cost, and planner invocation
or cache invalidation on every image turn. Profile locally against image-mode
episodes before changing the perception model or retraining.

## Latest local instrumentation (2026-11-05)

- `v2-2.py` is the local Task 2 profiling copy. It has a lazy local
  TorchScript loader for `exports/tile_multilabel_cnn_best.torchscript.pt`, but
  the parser is still the old per-cell public-asset template matcher; the CNN
  is **not yet invoked** during an episode.
- Perception telemetry is now merged into each planner telemetry record:
  `parse_ms`, `split_ms`, `tile_inference_ms`, `gridstate_init_ms`, cell count,
  decoded entity count, agent count, and whether the TorchScript model has
  loaded. `Agent.info()` exposes the same compact perception summary and names
  the agent as the instrumented Task 2 image agent.
- `a2-task2-telemetry.txt` confirms the planner itself is not the timeout:
  A2 won at `-27`; its initial compact search took `0.60 ms`, later actions
  reused the plan in `0.01–0.02 ms`, and RSS stayed near `83 MB`. That dump
  predates perception instrumentation, so it contains no image-pipeline data.
- Next: run image-mode A2 with `v2-2.py` and inspect the new perception fields.
  Then replace the template matcher with one batched TorchScript inference call
  and separate CNN/preprocess/decode timings before profiling the public suite.

## Batched CNN parser (2026-11-07)

- `v2-3.py` is the successor profiling/submission candidate. It alone was
  changed; `v2-2.py` remains the template-matcher baseline and the original
  TorchScript file was not edited or replaced.
- It removes all public-asset/template matching from the image path. Every
  board is split deterministically, converted from RGBA `uint8` to the exact
  training representation (`float32`, `[0, 1]`, CHW, bilinear `64x64`), and
  passed through the local TorchScript model in one batch.
- Its 14 logits are decoded independently with the calibrated thresholds:
  default `0.50`, `gem=0.40`, and `ghost=0.90`. Entity labels are decoded into
  layered `GridState` contents, so agent-on-item tiles preserve both entities.
- Per-turn perception telemetry now separates `preprocess_ms`, `cnn_ms`, and
  `decode_ms`, as well as one-time `model_load_ms`; `tile_inference_ms` retains
  their combined value for comparisons with `v2-2.py`.
- The model file is not present in this workspace, so `v2-3.py` has only passed
  static compilation here. Copy the downloaded artifact to
  `exports/tile_multilabel_cnn_best.torchscript.pt` beside the local notebook,
  then re-run the A2 image telemetry cell. The next validation is: exactly one
  agent, a win, matching or sensible reward, and a large reduction from the
  previous 1.6–2.5 seconds of template inference per turn.

## Selective perception replay (2026-11-07)

- Local telemetry for `v2-3.py` won A2, A3, A5, A7, and A10, verifying that
  the batched classifier and decoder reconstruct usable boards. Planning stayed
  below a few milliseconds, but the CNN still consumed roughly 153–332 ms per
  turn on average (and A3 spent about 8.4 seconds in perception over 22 turns).
- `v2-4.py` adds selective perception without changing `v2-3.py`. It fully
  parses an image at episode start, then skips crop/CNN/decode work only while
  a complete deterministic planner route remains. A reset, level change, or
  missing/exhausted route falls back to full live image parsing.
- Its telemetry adds `perception_reused`: `0` for a full parse and `1` for a
  replayed turn. Reused rows report zero parse/preprocess/CNN/decode cost while
  retaining the preceding board counts for readable summaries.
- Next validation: rerun the same five A-tier image episodes with `v2-4.py`.
  Each successful deterministic episode should have one non-reused initial row
  and all subsequent plan-replay rows marked `perception_reused=1`.

## B-tier selective-replay results (2026-11-07)

- `v2-4.py` solved the local image-mode validation episodes at the exact
  known-best rewards: B2 `-65`, B3 `-315`, B4 `-387`, B6 `-213`, and B10
  `-162`. Every reconstruction had exactly one agent.
- Selective perception works: only the initial row is a full parse; later
  rows have `perception_reused=1` and zero crop/preprocess/CNN/decode time.
  Reuse rates were B2 97.6%, B3 99.1%, B4 99.2%, B6 98.6%, and B10 98.2%.
- The single initial image parse is still material but bounded: B2 1082 ms,
  B3 1190 ms, B4 901 ms, B6 1078 ms, and B10 1117 ms. Initial planner time
  was B2 582 ms, B3 51 ms, B4 50 ms, B6 13 ms, and B10 318 ms. Subsequent
  planner calls take roughly 0.01 ms.
- Coursemology reports all A levels and B0/B1/B5/B7/B8/B9 as wins, but marks
  B2, B3, B4, B6, and B10 as timeouts even though it records `win=True` and
  the known-best reward. Runtimes were 5.87, 5.75, 8.15, 5.21, and 5.19 s,
  respectively. This exceeds the catalog's 5-second gameplay deadline and
  yields zero effective performance despite a correct plan.
- The dumps show agent perception is no longer a per-turn multiplier. The
  next thread should time the **whole local loop** separately (`agent.step`,
  `env.step`, and total wall time) for the failing B levels, then compare it
  against agent-only telemetry. This distinguishes unavoidable image-env
  overhead from submission-side overhead. Also prepare a lean submission copy
  with local telemetry/RSS/debug `info()` removed after profiling; retain the
  instrumented `v2-4.py` as the diagnostic baseline.

## Lean submission and Coursemology update (2026-11-07)

- `v2-5.py` is the lean local candidate. It retains one initial batched image
  parse and deterministic route replay, but removes per-turn telemetry history,
  RSS sampling, and detailed `info()` formatting. `v2-4.py` remains the
  instrumented diagnostic baseline.
- The TorchScript CNN is passed once through `torch.jit.optimize_for_inference`
  after loading. On a local 225-tile B4 board this reduced repeated isolated
  model passes from roughly 0.6--0.8 s to roughly 0.33--0.39 s, without a
  material logit difference (maximum observed absolute difference about
  `1e-5`).
- `v2-5-submit.py` is the Coursemology submission copy. Its local-file model
  loader has been replaced with a module-scope TODO/stub for the generated
  inline `get_model(...)` function. The generated loader must replace that
  entire block before submission; `_get_tile_model()` then applies the same
  one-time TorchScript inference optimization.
- Contrary to the earlier local timing concern, the Coursemology Task 2
  submission passed every test set. Do not infer Coursemology runtime from the
  local public image-loop timings: the environments have materially different
  performance characteristics.

## Local whole-loop timing diagnosis (2026-11-07)

- External notebook timing (not agent telemetry) separated `agent.step()` and
  `env.step()` for the public image levels. After the initial parse and plan,
  replayed agent calls are negligible: B3 used 3.35 ms over 105 replay turns;
  B4 used 4.13 ms over 129 replay turns (about 0.03 ms each).
- Local `env.step()` image work dominates long episodes: B3 used 3.828 s in
  total environment time (3.775 s after its first turn), and B4 used 5.042 s
  total (5.015 s after its first turn). This explained the previous local B3/
  B4 five-second classifications but was not predictive of Coursemology,
  where Task 2 passed.
- Public C1 image (`The Heist`) wins locally at `-162` in 55 actions versus
  known best `-158`. Its first agent call is roughly 0.8--1.3 s and replayed
  agent calls are again negligible. The current compact mixed planner ignores
  optional coins, which is a plausible explanation for the four-point gap.

## Current blocker: Task 3 hidden boss images (2026-11-07)

- Coursemology reports that all three cases in
  `test_graded_boss_image_observations(Agent)` timed out at the full 15-second
  Task 3 limit: `avg_performance=0.0`, `avg_total_reward=0.0`, `num_win=0`,
  `num_lose=0`, `num_timeout=3`, `num_error=0`, `avg_runtime=15.0`.
- This is not explained by the public C1 image loop (which finishes locally in
  about 4--5 s) and is distinct from the resolved Task 2 public timing issue.
  The hidden boss image cases likely make the initial image reconstruction or,
  more likely, the initial mixed-mechanics search exceed the deadline before a
  complete route is cached.
- Next investigation: restore *external* timing around the first hidden-like
  mixed episode without reintroducing submission telemetry; profile and bound
  `_mixed_fast_plan()` state growth on larger synthetic mixed maps. Consider a
  bounded reward-aware coin extension only after preserving a strict search
  time budget/fallback, since the immediate failure is timeout rather than the
  public C1 four-point score gap.
