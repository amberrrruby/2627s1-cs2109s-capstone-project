# CS2109S Capstone Project

This repository archives the development, training, evaluation, and final
submission materials for the CS2109S capstone project. The agent combines a
compact search-based planner with a learned visual parser: structured
`GridState` observations can be planned from directly, while image
observations are split into cells, classified by a compact multi-label CNN,
reconstructed into a usable state, and passed to the same planner.

## Submission status

- **Final submitted agent:** [`v2-5-submit.py`](v2-5-submit.py) (**Later unsuccessful experiment:** [`v2-6.py`](v2-6.py))
- **Training notebook run in Colab:** [`colab-task-2.ipynb`](colab-task-2.ipynb)
- **Draft / local copy of the training notebook:** [`task-2.ipynb`](task-2.ipynb)

`v2-5-submit.py` is the authoritative submission artifact. It includes the
trained TorchScript model inline so that the Coursemology submission does not
depend on an external model file. It passed every Task 2 test set.

`v2-6.py` was created after the final submission as an attempt to address the
three hidden Task 3 boss image timeouts. It replaces the factorial gem-order
heuristic on large gem sets with a cached minimum-spanning-tree bound and uses
weighted A* on those larger cases. The experiment still failed to pass the
boss level and must not be treated as the submitted or successful version.

## Approach

### Task 1: structured-state planning

The Task 1 agent evolved from uniform-cost search into a family of compact
planners selected according to the mechanics present on a board. The final
planner supports:

- static walls, gems, exits, and optional coins;
- repeated ghost, boots, and shield power-ups, including effect timers,
  two-substep boots movement, lava damage, health, and stacked shields;
- keys and locked doors with explicit `PICK_UP` and `USE_KEY` actions;
- box-only maps using a compact Sokoban state; and
- mixed keys/doors, lava, power-ups, and gems.

The agent selects the narrowest suitable state representation. Static routes
are reconstructed once and replayed instead of solving the same suffix on
every turn. A wall-aware full-`GridState` A* search remains as the fallback for
mechanics not covered by a compact model.

The main Task 1 development milestones were:

| Version | Main change |
| --- | --- |
| `v1-0`–`v1-3` | Uniform-cost search, then A* with caching and an MST heuristic. |
| `v1-4`–`v1-7` | Gem-order and wall-distance improvements, culminating in a compact static A*. |
| `v1-8`–`v1-12` | Power-up, fallback, key/door, and complete route-replay planners. |
| `v1-13` | Repeated power-ups and a compact Sokoban planner. |
| `v1-14` | Mixed-mechanics compact A*. |
| `v1-15`–`v1-16` | Bounded optional-coin routing, ending with a 12-coin subset-DP post-pass. |

All 22 public structured-state levels passed. Recorded public results include
A3 `-63`, A4 `-33`, A10 `-84`, B2 `-65`, B3 `-315`, B4 `-387`, B5 `-210`,
B6 `-213`, B7 `-111`, B8 `-93`, and B10 `-162`.

### Task 2: image-to-state reconstruction

Task 2 retains the planner and replaces its structured input with a learned
perception pipeline:

```text
RGBA board image + structured metadata
                 |
                 v
      deterministic cell splitting
                 |
                 v
       batched multi-label CNN
                 |
                 v
  layered entities + structural checks
                 |
                 v
       reconstructed GridState
                 |
                 v
          Task 1 planner
```

The CNN accepts `64 x 64` RGBA cell crops and predicts 14 independent labels:
`floor`, `wall`, `lava`, `exit`, `locked`, `opened`, `box`, `agent`, `gem`,
`coin`, `key`, `boots`, `ghost`, and `shield`. Independent sigmoid outputs
allow layered cells such as agent-on-gem or agent-on-exit. Numeric game state,
including health, inventory, status, score, and turn count, is taken from the
observation metadata rather than inferred from pixels.

**<u>No external or independently generated dataset was created or used. The
training input came exclusively from the image assets supplied with the
project under `data/assets/`.</u>** During training, the Colab notebook formed tile
examples on demand by selecting and, where appropriate, layering those
provided assets. Source PNG variants were separated into an 80/20
train/validation split so a sprite variant could not appear in both
partitions. The complete data pipeline is recorded in
[`colab-task-2.ipynb`](colab-task-2.ipynb), including the training-only
augmentation steps: small crop/scale changes, brightness, contrast,
saturation, blur, JPEG artefacts, and light noise. These operations varied the
presentation of the supplied assets without introducing new semantic classes
or external training images.

The compact RGBA CNN has approximately 185,000 parameters and was trained for
15 epochs with `BCEWithLogitsLoss` on 24,000 on-demand asset compositions per
epoch. It was validated on 6,000 examples formed only from held-out supplied
asset variants. The best recorded macro-F1 was `0.9994`. Error analysis
motivated conservative decoder thresholds of `0.40` for gems, `0.90` for
ghosts, and `0.50` for all other labels; this policy produced zero errors on
that held-out validation set.

The first CNN implementation ran perception on every turn. The final approach
performs one batched parse at the start of a deterministic episode, caches the
complete route, and reuses it while valid. This removed repeated CNN work from
long episodes. Local validation reproduced the known-best B2, B3, B4, B6, and
B10 rewards, and the final Coursemology submission passed all Task 2 test
sets.

### Task 3 and the final limitation

The public C1 image level (`The Heist`) was won locally at `-162` in 55 actions,
compared with the recorded known best of `-158`. However, all three hidden
Task 3 boss image cases timed out at the 15-second limit. The later `v2-6.py`
experiment tried to reduce large-gem search cost, but did not resolve those
timeouts. This remains the main known limitation of the project.

## Repository structure

```text
.
|-- README.md                         Project overview and archive guide
|-- NOTES.md                          Detailed chronological engineering notes
|-- v2-5-submit.py                    Final Coursemology submission
|-- v2-6.py                           Later failed boss-level experiment
|-- history/                          Earlier planner and image-agent versions
|-- chat-history/                     Exported AI-assistance conversations
|-- capstone-project.ipynb            Main local development/evaluation notebook
|-- colab-task-2.ipynb                Colab training/export notebook
|-- task-2.ipynb                      Earlier/local copy of the Task 2 notebook
|-- task-2-v1-1.md                    Explanatory notes for the training pipeline
|-- tile_model_loader.py              Generated inline TorchScript loader source
|-- tile_multilabel_cnn_best.torchscript.pt
|                                      Standalone exported TorchScript model
|-- telemetry/                        Saved performance and profiling records
|-- public_levels/                    Public level definitions and catalogue
|-- data/assets/                      Provided sprite assets used for training
|-- environment.yml                   Reproducible Conda environment
|-- utils.py                          Course/project utilities
|-- utils-copy.py                     Preserved utility working copy
|-- tutorial.ipynb                    Provided tutorial notebook
`-- untitled2.py                      Preserved exploratory script
```

Python bytecode and Jupyter checkpoint folders are local generated files and
are excluded by [`.gitignore`](.gitignore).

## Supplementary artifacts

The primary supplementary materials are:

1. [`colab-task-2.ipynb`](colab-task-2.ipynb), the Colab notebook used to form
   training examples exclusively from the supplied image assets, apply the
   documented augmentation pipeline, train the model, calibrate thresholds,
   and export it. [`task-2.ipynb`](task-2.ipynb) is an earlier/local copy and
   should not be mistaken for the final Colab run.
2. [`tile_model_loader.py`](tile_model_loader.py), the generated Python loader
   containing an inline encoded copy of the TorchScript model. This is the
   form incorporated into the single-file submission.
3. [`tile_multilabel_cnn_best.torchscript.pt`](tile_multilabel_cnn_best.torchscript.pt),
   the standalone exported TorchScript model for local inspection and reuse.
4. [`telemetry/`](telemetry/), the recorded profiling evidence used to separate
   perception, planning, and environment runtime.
5. [`history/`](history/), preserved intermediate versions showing the
   development path. These are records, not alternative submissions.
6. [`chat-history/`](chat-history/), exported Markdown records of the
   AI-assisted development conversations. The final conversation used to
   organise this archive must still be added after it concludes.

## Reproducibility notes

The local environment is described in [`environment.yml`](environment.yml)
and uses Python 3.13, PyTorch 2.7, torchvision 0.22, and the Grid Universe,
Grid Adventure, and Grid Play packages. The notebooks also depend on the
provided assets under `data/assets/`.

The final submission is deliberately self-contained, whereas the standalone
model and loader are retained to make the model provenance inspectable. The
validation results measure generalisation to held-out variants of the provided
assets; they are not, by themselves, evidence of perfect performance on all
hidden artwork or complete end-to-end levels.

## AI-use declaration and citations

The course permits AI use when it is properly cited. Its stated requirements
are to provide a shareable conversation link where possible (or screenshots
where a link cannot be shared) and to document changes made to AI-generated
code. The course advises using AI-generated code as produced and strongly
discourages alteration or obfuscation. This repository retains the development
conversations and intermediate source versions so that the assistance and
subsequent changes remain inspectable.

OpenAI Codex/ChatGPT was used throughout the project. Its roles included
researching the provided game documentation, explaining algorithms,
brainstorming and implementing search strategies, debugging, building and
refining the Task 2 notebook and image parser, suggesting profiling and
validation steps, interpreting results, reorganising notebooks, and preparing
this archive. Suggestions and code edits were tested through the notebooks,
local public-level runs, saved telemetry, and Coursemology. The author chose
which changes to retain and submitted `v2-5-submit.py`.

### Conversation records

The exported Markdown conversations currently available in
[`chat-history/`](chat-history/) are:

- [`Find Grid Adventure step costs`](chat-history/2026-10-8-1656-find-grid-step-costs.md)
- [`Summarize Grid Adventure mechanics`](chat-history/2026-10-08-1716-summarize-grid-adventure-mechanics.md)
- [`Explain frontier tuple structure`](chat-history/2026-10-18-1406-explain-frontier-tuple-structure.md)
- [`Add level-map caching`](chat-history/2026-10-18-1921-add-level-map-caching.md)
- [`Improve the A3 gem heuristic`](chat-history/2026-10-19-2129-improve-a3-gem-heuristic.md)
- [`Analyze remaining level performance`](chat-history/2026-10-31-2336-analyze-remaining-level-performance.md)
- [`Identify the next optimization goal`](chat-history/2026-11-01-1749-identify-next-optimization-goal.md)
- [`Find the project starting point`](chat-history/2026-11-02-1040-find-project-starting-point.md)
- [`Find the next step for Task 2`](chat-history/2026-11-05-1344-find-next-step-for-task-2.md)
- [`Review NOTES.md and Task 2 next steps`](chat-history/2026-11-05-1736-review-notes-md-and-next-steps.md)
- [`Reorder capstone notebook cells`](chat-history/2026-11-07-0823-reorder-capstone-notebook-cells.md)
- [`Find where NOTES.md left off`](chat-history/2026-11-07-1347-find-where-notes-md-left-off.md)
- [`Review the hidden boss-level work`](chat-history/2026-11-07-1943-review-notes-md-for-boss-level.md)

The conversation used to prepare this README and perform the final compliance
audit is still in progress and must be exported into `chat-history/` after the
work is complete.

These local Markdown exports make the development record readable in the
archive, but they do not currently contain share links to the original
conversations. To satisfy the policy literally, add a share link for each
conversation when the product permits one. When a conversation cannot be
shared by link, add screenshots that show the relevant prompts and responses.

### AI-assisted code and subsequent changes

AI-produced edits were generally applied directly to a new working version,
then preserved rather than overwritten when another iteration was needed.
Later changes are therefore visible both in the conversations and in the
versioned files under [`history/`](history/). The principal changes are:

| AI-assisted artifact or stage | Changes made after the initial AI-assisted version | Evidence |
| --- | --- | --- |
| Task 1 planner (`v1-0` through `v1-16`) | Successive versions changed the search key, heuristics, state representation, route replay, power-up semantics, key/door handling, Sokoban planning, mixed mechanics, and optional-coin routing. Earlier files were retained instead of obfuscated or silently replaced. | [`history/`](history/), [`NOTES.md`](NOTES.md), and the dated Task 1 conversations above |
| Task 2 training notebook | The pipeline was built incrementally, then run in Colab. The final notebook uses only supplied image assets, an asset-variant train/validation split, documented augmentation, held-out evaluation, and calibrated gem/ghost thresholds. | [`colab-task-2.ipynb`](colab-task-2.ipynb), [`task-2.ipynb`](task-2.ipynb), and the 5 November conversations |
| Image parser and planner integration (`v2-1` through `v2-5`) | The public-asset template matcher was replaced by one batched CNN call; later versions added selective perception reuse, removed submission telemetry, optimized the loaded TorchScript model once, and embedded the generated loader in the final single-file submission. | [`history/`](history/), [`NOTES.md`](NOTES.md), and the 5–7 November conversations |
| Generated model loader | The loader was produced by the provided course utility, not manually authored as a new dataset or model format. Its generated `get_model(...)` function was placed inline in the submission; surrounding integration loads and optimizes the model once. | [`tile_model_loader.py`](tile_model_loader.py), [`v2-5-submit.py`](v2-5-submit.py), and [`utils.py`](utils.py) |
| Post-submission boss experiment | `v2-6.py` added a cached MST lower bound and weighted A* for large gem sets. It remained unsuccessful and was not substituted for the final submission. | [`v2-6.py`](v2-6.py), [`v2-5-submit.py`](v2-5-submit.py), and the 7 November boss conversation |
| Project archive documentation | Codex drafted and revised this README from `NOTES.md`, the repository contents, the supplied AI policy, and the author's corrections. | This final conversation, to be exported after completion |

No attempt has been made to disguise AI involvement. Where later testing led
to changes, those changes and their motivation are recorded above and in the
chronological evidence.

Suggested declaration for the submission form:

> I used OpenAI Codex/ChatGPT for research assistance, algorithm explanation,
> brainstorming, implementation and debugging, profiling and validation
> suggestions, notebook organisation, and documentation. I retained the
> relevant conversations and intermediate source versions, documented later
> changes to AI-assisted code, tested the resulting work, and take
> responsibility for the submitted `v2-5-submit.py`.
