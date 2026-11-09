# Improve A3 gem heuristic

> Progress so far:
>
> ## Version summary
>
> | Version   | Main change                                                                                                                | Result                                                                                                                                      |
> | --------- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
> | `v1-0.py` | Baseline uniform-cost search; each frontier item stores its full action path.                                              | Simple but path copying is costly.                                                                                                          |
> | `v1-1.py` | Tracks only the first action instead of full paths; uses `str(state.grid)` for visited states.                             | Faster baseline; avoids repeated states correctly.                                                                                          |
> | `v1-2.py` | Adds real-environment map/entity caching and an `h(...)` stub.                                                             | Cache is useful between real turns, but its search-state key changes caused severe expansion issues.                                        |
> | `v1-3.py` | Adds MST gem heuristic; restores grid-only visited keys and `visited.add(...)`. Later experimented with full-plan caching. | Better pruning, but the MST’s optimistic Speed/Manhattan distances remain weak on A3. Full-plan caching is intentionally not our direction. |
> | `v1-4.py` | Replaces MST with enumeration of all gem orders, at most `5! = 120`; retains grid-only visited keys.                       | Stronger gem-order lower bound, but still ignores walls and assumes Speed, so A3 still has too many promising states.                       |
>
> ## Next plan
>
> 1. Keep the all-gem-order approach from `v1-4.py`.
> 2. Replace its Manhattan/Speed distance estimates with cached static wall-aware BFS distances.
> 3. Use those distances in every gem permutation:
> ```vbnet
> agent → gem order → exit
> ```
>
> 4. Keep ignoring dynamic mechanics initially; this specifically targets static multi-gem mazes such as A3.
> 5. If needed afterward, carry compact per-node metadata—agent position and gem bitmask—to eliminate per-node grid scans and eventually replace `str(state.grid)`.
>
> (More context: read `capstone-project.ipynb`)
>
> We'll be working at v1-5 now. So now we're caching the level map's walls and gems and exit first, then for each gem sequence permutation, we solve the distances (straight-forward), then use that as hopefully a tighter heuristic. Am I understanding the plan correctly?

<details><summary>2 previous messages</summary>

> I’ll inspect the notebook and the v1-4 implementation to validate that interpretation against the actual state representation and mechanics.
>
> <details><summary>Ran 3 commands</summary>
>
> - Ran `rg --files | rg "(capstone-project\.ipynb|v1-4\.py|v1-5\.py)$"`
> - Ran `Get-Content -LiteralPath v1-4.py; Get-Content -LiteralPath v1-5.py`
> - Ran `rg -n -i "A3|speed|wall|bfs|heuristic|gem|movement|Action" capstone-project.ipynb`
>
> </details>
</details>

Yes—that is the intended v1-5 heuristic.

For each newly cached level:

1. Cache the static walls, all gem positions, and exit position.
2. Run ordinary four-neighbor BFS on the wall-only map to obtain shortest walking distances between relevant tiles.
3. For each search state, enumerate every ordering of its remaining gems and compute:

   `distance(agent, first gem) + … + distance(last gem, exit) + number of remaining PICK_UP actions`

4. Use the minimum total as `h(state)`.

That should be much tighter on A3 because routes that look close in Manhattan distance but are separated by maze walls now receive their true static detour cost.

Two important refinements:

- The BFS graph should treat walls as blocked but otherwise allow all tiles. That preserves admissibility by deliberately ignoring dynamic blockers/hazards/doors and special mechanics.
- Do **not** assume Boots/Speed in this initial version. Plain one-tile BFS produces a safe lower bound even if speed may later reduce the real route cost. A speed-aware estimate could overestimate unless it models whether/when Boots are reachable.

Since the map’s walls, gems, and exit are static, cache BFS distance maps once per level—ideally one reverse BFS from every gem and the exit. Then lookup is O(1), leaving only the at-most-120 permutation evaluation per heuristic call.

> Right. We'll first integrate a reduced map caching for v1-5. We can branch on this later, when we experiment with other objectives, so I think we can also include a few more if it's convenient while we're here.
>
> Aside from walls, gems, exit, what else can we cache? Power-ups? At that point we may as well cache the whole map but in a lighter IR?

Yes—the useful boundary is a cached, lightweight **static level IR**, not a copy of each evolving `GridState`.

Cache tile positions by category:

- Hard terrain: `walls`
- Goal structure: `initial_gems`, `exits`
- Static interactables: `keys`, `locked_doors`, `unlocked_doors`, `boxes`, `lava`
- Power-ups: `speed`, `shield`, `phasing`
- Optional reward-only objects: `coins`
- Dimensions and episode identity

For v1-5’s wall-aware gem heuristic, only `walls`, `initial_gems`, `exits`, and dimensions are required. The others are worth indexing now because later heuristic variants may want to recognize, for example, that a key makes a door traversable or that phasing makes walls effectively traversable.

I would keep the representation deliberately compact, e.g.:

```python
self._static = {
    "walls": frozenset(...),
    "gems": frozenset(...),
    "exits": frozenset(...),
    "keys": frozenset(...),
    "locked_doors": frozenset(...),
    "speed_powerups": frozenset(...),
    ...
}
```

Then separately maintain small dynamic facts:

```python
self._agent_position
self._remaining_gems
self._collected_powerups
self._opened_doors
```

One caveat: boxes can move, doors can change, gems disappear, and power-ups disappear after pickup—so their **initial locations** belong in static cache, but their current status must either be read from the search state or represented in dynamic metadata. In other words: cache the level blueprint; don’t mistake it for the current world state.

> Why a frozenset? We could make it mutable no? Is the sole reason caching?

It does not have to be a `frozenset`. A mutable `set` is perfectly fine.

I suggested `frozenset` because these particular entries represent the level’s immutable blueprint—walls and original layout—so it prevents accidental mutations during search. It also makes the distinction clearer:

```python
self._static["walls"]          # frozenset: never changes this episode
self._remaining_gems           # set: changes after PICK_UP
```

It is not needed for caching itself, and it is not a performance requirement. Use ordinary `set`s if you prefer; just avoid mutating the cached wall set accidentally.

> Right. Let's make a quick recap - we cached walls, gems and exits because all gems need to be collected before exiting, hence we make the current heuristic term from the problem "find the shortest route that passes through all gems then gets to the exit". And we now calculate the heuristic value, with knowledge of walls in map to get a tighter estimate, and hence we don't just take the Manhattan distance of each. But isn't that also computationally expensive? I'm not sure what's the bound for the map size, but 120 * cost of BFS or something could easily make it expensive like before.

Exactly—and the key is that we should **not run BFS 120 times per heuristic evaluation**.

For one level, do this once:

- Run one BFS from each static target: every gem plus the exit.
- With at most five gems, that is at most **6 BFS runs total**.
- Each BFS visits each walkable map tile at most once: `O(V + E)`—effectively `O(width × height)` on a grid.

Store each result as a distance map:

```python
distance_from[gem_a][position]
distance_from[exit][position]
```

Because ordinary cardinal movement on a wall-only map is symmetric:

```python
distance(agent, gem_a) = distance_from[gem_a][agent]
distance(gem_a, gem_b) = distance_from[gem_b][gem_a]
```

Then each call to `h(state)` performs no BFS. It only:

- determines the agent position and remaining gems;
- checks at most `5! = 120` orders;
- sums at most six already-cached integer distances per order.

So the online cost is bounded by roughly `120 × 6` dictionary/list lookups and additions—tiny compared with generating a single successor via `grid_step`.

The total shape is:

```text
Level initialization:
  ≤ 6 × BFS(map)                 # paid once

Every A* node:
  ≤ 120 permutations × ≤ 6 lookups
  no map traversal, no BFS
```

This is why caching the BFS maps matters. If instead every permutation triggered BFS, it would indeed be far too expensive.

One subtle point: if a tile cannot reach a target under the wall-only map, cache its distance as absent/`∞`. Any gem ordering that contains such a segment is impossible for that relaxed map and can be skipped; if all orders are impossible, return a safe fallback such as `0` rather than an infinite heuristic.

> Right. Got it.
>
> We'll implement the reduced-map caching in `v1-5.py` now. Nothing more, just the reduced-map caching.

<details><summary>2 previous messages</summary>

> I’ll limit this edit to the level’s reduced static cache—walls, original gems, and exits—while retaining the existing dynamic agent/gem bookkeeping. No BFS or heuristic changes yet.
>
> <details><summary>Edited a file, ran 2 commands</summary>
>
> - Ran `git status --short; rg -n "_positions|_remaining_gems|_exit_positions|def locations|def _cache_level" v1-5.py`
> - Wrote `./v1-5.py` (+31 -10)
> - Ran `python -m py_compile v1-5.py; rg -n -C 3 "Reduced static|def _cache_level|def locations|_positions" v1-5.py`
>
> </details>
</details>

Implemented the reduced-map cache in [v1-5.py](./v1-5.py:128).

It now caches only:

- `_walls`
- `_initial_gems`
- `_exit_positions`

Dynamic state remains separate through `_agent_position` and `_remaining_gems`. The existing heuristic and search behavior are unchanged; BFS distance caching has not been added. `v1-5.py` passes syntax compilation.

> In `v1-6.py`, implement the gem distance caching, then update the heuristic to use it.

<details><summary>2 previous messages</summary>

> I’ll build v1-6 from the reduced-map version, add one wall-only BFS distance map per gem and exit during level caching, then make the permutation heuristic use only cached lookups.
>
> <details><summary>Edited a file, ran 4 commands</summary>
>
> - Ran `Get-ChildItem -Name v1-6.py; Get-Content -LiteralPath v1-5.py -TotalCount 230`
> - Ran `Get-Item -LiteralPath v1-6.py | Select-Object Name,Length; Get-Content -LiteralPath v1-6.py -TotalCount 35`
> - Ran `python -c "import inspect; from grid_adventure.entities import SpeedPowerUpEntity; import grid_adventure.entities as e; print(inspect.getsource(SpeedPowerUpEntity))"`
> - Wrote `./v1-6.py` (+69 -21)
> - Wrote `./v1-6.py` (+2 -0)
> - Ran `python -m py_compile v1-6.py; rg -n -C 2 "def h|_wall_distances|_bfs_wall_distances|priority =" v1-6.py`
>
> </details>
</details>

Implemented v1-6 in [v1-6.py](./v1-6.py:42).

It now:

- Builds one wall-only cardinal BFS distance map for every initial gem and exit when a level is cached.
- Stores those maps in `_wall_distances`.
- Uses cached distance lookups—not BFS calls—while checking gem permutations in `h(...)`.
- Adds one `PICK_UP` action per remaining gem.
- Safely returns `0` if the wall-only relaxation has no complete route.
- Keeps the rest of search behavior unchanged.

`python -m py_compile v1-6.py` passes.

> ```yaml
> Running [1/22] A0 Basic Movement (gridstate)...
> Result: task: Task 1, public_level: A0 Basic Movement, observation_type: gridstate, status: WIN, level_name: Level basic movement (gridstate), performance: 1.0, total_reward: -9.0, win: True, lose: False, timeout: False, error: False, runtime (sec): 0.11, effective_performance: 1.0
> Running [2/22] A1 Maze Turns (gridstate)...
> Result: task: Task 1, public_level: A1 Maze Turns, observation_type: gridstate, status: WIN, level_name: Level maze turns (gridstate), performance: 1.0, total_reward: -27.0, win: True, lose: False, timeout: False, error: False, runtime (sec): 2.68, effective_performance: 1.0
> Running [3/22] A2 Optional Coin Path (gridstate)...
> Result: task: Task 1, public_level: A2 Optional Coin Path, observation_type: gridstate, status: WIN, level_name: Level optional coin (gridstate), performance: 0.42857142857142855, total_reward: -27.0, win: True, lose: False, timeout: False, error: False, runtime (sec): 1.99, effective_performance: 0.42857142857142855
> Running [4/22] A3 Multiple Required Gems (gridstate)...
> Result: task: Task 1, public_level: A3 Multiple Required Gems, observation_type: gridstate, status: TIMEOUT, level_name: Level required multiple (gridstate), performance: 1.0, total_reward: -63.0, win: True, lose: False, timeout: True, error: False, runtime (sec): 21.4, effective_performance: 0.0
> Running [5/22] A4 Key and Door (gridstate)...
> Result: task: Task 1, public_level: A4 Key and Door, observation_type: gridstate, status: WIN, level_name: Level key door (gridstate), performance: 1.0, total_reward: -33.0, win: True, lose: False, timeout: False, error: False, runtime (sec): 1.67, effective_performance: 1.0
> Running [6/22] A5 Hazard Detour (gridstate)...
> Result: task: Task 1, public_level: A5 Hazard Detour, observation_type: gridstate, status: WIN, level_name: Level hazard detour (gridstate), performance: 1.0, total_reward: -39.0, win: True, lose: False, timeout: False, error: False, runtime (sec): 4.63, effective_performance: 1.0
> Running [7/22] A6 Pushable Box (gridstate)...
> Result: task: Task 1, public_level: A6 Pushable Box, observation_type: gridstate, status: WIN, level_name: Level pushable box (gridstate), performance: 1.0, total_reward: -21.0, win: True, lose: False, timeout: False, error: False, runtime (sec): 0.47, effective_performance: 1.0
> Running [8/22] A7 Shield Powerup (gridstate)...
> Result: task: Task 1, public_level: A7 Shield Powerup, observation_type: gridstate, status: WIN, level_name: Level power shield (gridstate), performance: 1.0, total_reward: -42.0, win: True, lose: False, timeout: False, error: False, runtime (sec): 3.6, effective_performance: 1.0
> Running [9/22] A8 Ghost Powerup (gridstate)...
> ```
>
> Multiple required gems still timed out. What have we tried? What's next should we try?

We have now tried:

1. Full action-path UCS (`v1-0`).
2. First-action A* plus grid-string visited keys (`v1-1`).
3. Real-environment entity caching (`v1-2`).
4. MST gem heuristic (`v1-3`).
5. All gem-order enumeration with optimistic Manhattan/Speed distances (`v1-4`).
6. Reduced static map cache (`v1-5`).
7. Cached wall-aware BFS distances plus all gem-order enumeration (`v1-6`).

A3 still finds the optimal solution (`performance: 1.0`, reward `-63`) but exceeds the runtime budget. So the remaining problem is computational overhead, not route quality.

The next thing to try is the compact per-search-node metadata we had deferred:

```python
(agent_position, remaining_gem_mask)
```

For the static A3-style level, that is enough to represent the meaningful search state. It eliminates two expensive operations done for every generated successor:

- scanning the entire `GridState` in `h(...)` to rediscover the agent and remaining gems;
- constructing `str(next_state.grid)` as the visited-state key.

The heuristic can then receive metadata directly:

```python
h(agent_position, remaining_gem_mask)
```

and use the already cached BFS maps plus a precomputed gem-position-to-bit mapping. Since at most five gems exist, there are only `2^5 = 32` gem subsets.

For A3 specifically, the key can safely be:

```python
(agent_position, remaining_gem_mask)
```

because it only has static walls, gems, and an exit. For mechanics-heavy levels, that key would be insufficient—boxes, doors, keys, active power-ups, and health can change the reachable world—so make this an A3/static-map specialization or conditionally enable it only when no dynamic mechanics are present.

That is the most promising next version. The cached BFS improved heuristic quality, but the search is still paying `GridState` cloning, grid scans, string serialization, and 120-order enumeration across many nodes. Compact metadata directly targets the latter three costs.

> Hmm. Can we possibly add cheap observability for that? (If you're adding one, copy it into a new v1.6.1.)

<details><summary>4 previous messages</summary>

> Yes. I’ll add lightweight per-planning-call counters and timers—without printing during evaluation—and expose the latest measurements through `info()`. I’ll put it in a separate `v1-6-1.py` copy so v1-6 stays unchanged.
>
> <details><summary>Edited a file, ran 5 commands</summary>
>
> - Ran `rg --files | rg "^v1"`
> - Ran `Copy-Item -LiteralPath v1-6.py -Destination v1-6-1.py`
> - Ran `Get-Content -LiteralPath v1-6-1.py -Tail 35; Get-Content -LiteralPath v1-6-1.py | Select-Object -Index (135..340)`
> - Wrote `./v1-6-1.py` (+39 -0)
> - Wrote `./v1-6-1.py` (+16 -2)
> - Ran `python -m py_compile v1-6-1.py; rg -n "perf_counter|_last_search_stats|_last_cache_stats|_record_search_stats|\"search\"|\"cache\"" v1-6-1.py`
> - Ran `python -m py_compile v1-6-1.py; rg -n -e perf_counter -e _last_search_stats -e _last_cache_stats -e _record_search_stats v1-6-1.py`
>
> </details>
>
> I’ve added aggregate counters; I’m also splitting the planner time into successor simulation, grid-key serialization, and heuristic evaluation so the diagnostic can distinguish the likely bottleneck rather than merely confirm that the search is large.
>
> <details><summary>Edited a file, ran a command</summary>
>
> - Wrote `./v1-6-1.py` (+14 -0)
> - Ran `python -m py_compile v1-6-1.py; Get-Item -LiteralPath v1-6.py, v1-6-1.py | Select-Object Name,Length`
>
> </details>
</details>

Added [v1-6-1.py](./v1-6-1.py) as a diagnostics-only copy of v1-6. It does not change search decisions.

It now exposes, through `info()`:

- total planning time per real action;
- states popped, successors simulated, states visited/enqueued, heuristic calls, and peak frontier size;
- cumulative time in `grid_step`, `str(next_state.grid)`, and `h(...)`;
- one-time BFS cache construction time, target count, and cached reachable-tile count.

This directly tests the “computational overhead” explanation rather than assuming it: `grid_step` dominating points to simulated-state creation; `grid_key` to `str(grid)` serialization; and `heuristic` to state scanning/permutation work. :codex-annotation{index="1"}

`v1-6.py` remains unchanged, and `v1-6-1.py` passes syntax compilation.

> ```python
> RUN_TASK_1_PUBLIC_CHECKS = True
>
> if RUN_TASK_1_PUBLIC_CHECKS:
>     task_1_public_results = run_task_1_public_tests(Agent)
>     display(task_1_public_results)
>     display(summarize_public_results(task_1_public_results))
> else:
>     print("Task 1 public checks skipped. Set RUN_TASK_1_PUBLIC_CHECKS = True to run them.")
> ```
>
> How do I get the telemetry? (Then from there we have information for improvement.) This is a cell from the notebook, so we'll just add print statements here (can we dump the output somewhere in the notebook?).

<details><summary>4 previous messages</summary>

> I’ll check what `run_task_1_public_tests` returns and whether it retains the agent instance; that determines whether a print in this cell is enough or whether we need a tiny evaluation-wrapper change.
>
> <details><summary>Ran 2 commands</summary>
>
> - Ran `rg -n -C 8 "def run_task_1_public_tests|def evaluate\(|class.*Result|history|agent\.info|info\(\)" utils.py capstone-project.ipynb`
> - Ran `rg -n "Multiple Required|build_level.*required|A3" capstone-project.ipynb utils.py`
>
> </details>
>
> The public-test helper creates and discards each `Agent`, so printing after `run_task_1_public_tests(...)` cannot access its telemetry. I’m adding a tiny per-episode telemetry history to v1-6-1 so a focused A3 notebook cell can display every planning call after the run.
>
> <details><summary>Edited a file, ran a command</summary>
>
> - Wrote `./v1-6-1.py` (+8 -1)
> - Ran `python -m py_compile v1-6-1.py; rg -n -C 2 "search_stats_history|def telemetry" v1-6-1.py`
>
> </details>
</details>

The public-test helper discards its `Agent` instance, so code after `run_task_1_public_tests(Agent)` cannot retrieve its telemetry. Run A3 separately in a diagnostic notebook cell instead; its displayed table will remain as cell output.

First, run the v1-6-1 `Agent` definition cell. Then add:

```python
import pandas as pd

env = create_env(
    build_level_required_multiple,
    observation_type="gridstate",
    seed=42,
)

agent = Agent()
state, _ = env.reset()
win = lose = False
total_reward = 0

while not (win or lose):
    action = agent.step(state)
    state, reward, win, lose, _ = env.step(action)
    total_reward += reward

telemetry = pd.DataFrame(agent.telemetry())

print(f"win={win}, lose={lose}, total_reward={total_reward}")
display(agent.info())
display(telemetry)
display(telemetry.describe())
```

The table has one row per real environment turn. The most useful columns are:

- `search_ms`: total A* time for that turn
- `popped`, `visited`, `max_frontier`: search size
- `grid_step_ms`: time spent constructing successor `GridState`s
- `key_ms`: time spent serializing `str(next_state.grid)`
- `heuristic_ms`: heuristic cost

I added `Agent.telemetry()` to [v1-6-1.py](./v1-6-1.py:377), which retains those completed per-turn records for this exact purpose.

> Can you modify the cell you gave so it dumps to a text file instead?

Use this version; it writes the run summary, latest info, full telemetry table, and descriptive statistics to `a3-telemetry.txt` beside the notebook.

```python
from pathlib import Path
import pandas as pd

env = create_env(
    build_level_required_multiple,
    observation_type="gridstate",
    seed=42,
)

agent = Agent()
state, _ = env.reset()
win = lose = False
total_reward = 0

while not (win or lose):
    action = agent.step(state)
    state, reward, win, lose, _ = env.step(action)
    total_reward += reward

telemetry = pd.DataFrame(agent.telemetry())

output_path = Path("a3-telemetry.txt")
output_path.write_text(
    "\n".join(
        [
            f"win={win}, lose={lose}, total_reward={total_reward}",
            "",
            "LATEST AGENT INFO",
            str(agent.info()),
            "",
            "PER-TURN TELEMETRY",
            telemetry.to_string(index=False),
            "",
            "SUMMARY STATISTICS",
            telemetry.describe().to_string(),
        ]
    ),
    encoding="utf-8",
)

print(f"Telemetry written to: {output_path.resolve()}")
```

> `a3-telemetry.txt` out fresh.
> Anything we can infer from that? Should we run another level to calibrate what does it mean by "taking too long"?

<details><summary>2 previous messages</summary>

> I’ll read the A3 telemetry and compare its per-turn search profile before deciding whether a second level would meaningfully calibrate it.
>
> <details><summary>Explored a file, ran 2 commands</summary>
>
> <details><summary>Explored a file</summary>
>
> - Read `./a3-telemetry.txt`
>
> </details>
>
> - Ran `Get-Content -LiteralPath capstone-project.ipynb | Select-Object -Index (690..720); Get-Content -LiteralPath capstone-project.ipynb | Select-Object -Index (730..790)`
>
> - Ran `rg -n "PUBLIC_GAMEPLAY_TIME_LIMIT" capstone-project.ipynb utils.py`
>
> </details>
</details>

Yes—A3 is very clear already:

- Total planning time: ~21.64 s across 22 real turns, matching the timeout.
- `grid_step`: ~17.92 s, or **83%** of planning time.
- `str(next_state.grid)`: ~3.56 s, or **16%**.
- Heuristic: ~45 ms total, about **0.2%**.

The search itself is small: at worst only 41 visited states and frontier size 8. So the wall-aware permutation heuristic is not the cause. Nor will compact heuristic metadata alone solve the timeout.

The actual issue is repeatedly cloning/specializing full `GridState`s in `grid_step`: 2,160 simulated successor actions in total, averaging ~8.3 ms each. Replacing grid-string visited keys would recover roughly 16%, but the essential next experiment is a static-A3 fast path that simulates movement on a compact `(agent_position, gem_mask)` model instead of calling `grid_step` for every candidate.

A calibration run is optional, but useful. Run A1 Maze Turns—not A0—because it is a comparable wall maze without the multi-gem goal. Adapt the telemetry cell like this:

```python
level_label = "A1 Maze Turns"
builder = PUBLIC_GAMEPLAY_LEVEL_BUILDERS[level_label]

env = create_env(builder, observation_type="gridstate", seed=42)
agent = Agent()
state, _ = env.reset()
win = lose = False
total_reward = 0

while not (win or lose):
    action = agent.step(state)
    state, reward, win, lose, _ = env.step(action)
    total_reward += reward

telemetry = pd.DataFrame(agent.telemetry())

Path("a1-telemetry.txt").write_text(
    "\n".join(
        [
            f"{level_label}: win={win}, lose={lose}, total_reward={total_reward}",
            "",
            "LATEST AGENT INFO",
            str(agent.info()),
            "",
            "PER-TURN TELEMETRY",
            telemetry.to_string(index=False),
            "",
            "SUMMARY STATISTICS",
            telemetry.describe().to_string(),
        ]
    ),
    encoding="utf-8",
)
```

If A1’s per-successor `grid_step` time is similarly high, that confirms full-state simulation cost. If it is much lower, A3’s multi-gem re-planning multiplies that baseline cost—but either result still points away from the heuristic.

> Done. How's it?

<details><summary>2 previous messages</summary>

> I’ll compare the A1 and A3 telemetry, focusing on successor count and the per-successor cost of state simulation and grid-key creation.
>
> <details><summary>Explored a file</summary>
>
> - Read `./a1-telemetry.txt`
>
> </details>
</details>

This confirms the diagnosis.

| Metric | A1 Maze Turns | A3 Multiple Gems |
|---|---:|---:|
| Total successor simulations | 551 | 2,160 |
| Total planner time | ~4.00 s | ~21.64 s |
| `grid_step` time | ~3.30 s | ~17.92 s |
| `str(grid)` key time | ~0.65 s | ~3.56 s |
| Heuristic time | ~11 ms | ~45 ms |

A3’s search performs about 4× as many simulated successors, and each simulation is also slower: roughly 8.3 ms per `grid_step` in A3 versus 6.0 ms in A1. Its map is larger (45 versus 26 reachable tiles), so copying/specializing the full grid costs more per successor.

The heuristic is decisively not the bottleneck: it costs about 0.02 ms per invocation in both levels.

So no more calibration is necessary. The evidence supports this next change:

- Add a static-level compact search mode for levels containing only walls, gems, exit, and agent.
- Search directly over `(position, remaining_gem_mask)`.
- Generate cardinal moves and valid `PICK_UP` transitions directly, without `grid_step`.
- Use that compact tuple directly as the visited key—no `str(next_state.grid)`.

That targets roughly 99% of the A3 planning time represented in the telemetry.

> Proceed in `v1-7.py`.

<details><summary>2 previous messages</summary>

> I’ll add a guarded static-level fast path in v1-7: it will use compact `(position, gem-mask)` A* only when the level contains no mechanics beyond walls, gems, exits, and the agent. All other levels will retain the existing full `GridState` search.
>
> <details><summary>Edited a file, ran 7 commands</summary>
>
> - Ran `Get-ChildItem -Name v1-7.py; Get-Content -LiteralPath v1-6.py -TotalCount 390`
> - Ran `rg -n "Action\.(UP|DOWN|LEFT|RIGHT|MOVE|PICK_UP|WAIT)|list\(Action\)|class Action" capstone-project.ipynb v1-*.py`
> - Ran `rg -n -i -C 4 "move up|move down|pick up|actions" capstone-project.ipynb`
> - Wrote `./v1-7.py` (+130 -0)
> - Ran `rg -n -C 5 "_cache_level\(state\)|_sync_dynamic_cache|def info|return \{\"name\"" v1-7.py`
> - Ran `rg -n -C 5 -e "_cache_level(state)" -e "_sync_dynamic_cache" -e "def info" -e "return {\"name\"" v1-7.py`
> - Ran `Get-Content -LiteralPath v1-7.py | Select-Object -Index (385..485); Get-Content -LiteralPath v1-7.py -Tail 25`
> - Wrote `./v1-7.py` (+10 -1)
> - Ran `python -m py_compile v1-7.py; Select-String -LiteralPath v1-7.py -Pattern "_static_fast_path","_static_fast_action","_static_heuristic","_gem_bits"`
>
> </details>
</details>

Implemented the compact static-level search path in [v1-7.py](./v1-7.py:313).

For wall/gem/exit-only levels such as A3, it now:

- represents search nodes as `(position, remaining_gem_mask)`;
- generates cardinal movement and `PICK_UP` transitions directly;
- uses the compact tuple as its visited key;
- retains cached wall-distance permutation estimates;
- avoids simulated `GridState` creation and `str(grid)` entirely.

Levels containing coins, doors, boxes, lava, keys, or power-ups automatically fall back to the prior full-`GridState` A* behavior.

`v1-7.py` passes syntax compilation.

> Still times out. Telemetry written to `a3-telemetry.txt`. See what's different - did it improve on that aspect?

<details><summary>6 previous messages</summary>

> I’ll compare the new A3 telemetry with the prior run to verify whether v1-7 actually entered the compact mode and whether the expensive full-state simulation disappeared.
>
> <details><summary>Explored a file, ran a command</summary>
>
> <details><summary>Explored a file</summary>
>
> - Read `./a3-telemetry.txt`
>
> </details>
>
> - Ran `Get-Content -LiteralPath capstone-project.ipynb | Select-Object -Index (925..965)`
>
> </details>
>
> The new telemetry shows v1-7 did not enter its compact path at all: the agent name and every full-state counter are unchanged. I’m checking which guard failed—most likely the movement-action naming assumption—before changing the fast-path eligibility logic.
>
> <details><summary>Ran 3 commands</summary>
>
> - Ran `& 'C:\Users\User\anaconda3\envs\CapstoneProject\python.exe' -c "from grid_adventure.step import Action; print([(a.name, a.value) for a in Action])"`
> - Ran `& 'C:\Users\User\anaconda3\envs\CapstoneProject\python.exe' -c "from public_levels.intro import build_level_required_multiple; from utils import create_env; from collections import Counter; env=create_env(build_level_required_multiple, observation_type='gridstate', seed=42); state,_=env.reset(); print(Counter(type(entity).__name__ for column in state.grid for cell in column for entity in cell))"`
> - Ran `& 'C:\Users\User\anaconda3\envs\CapstoneProject\python.exe' -c "import importlib.util; from public_levels.intro import build_level_required_multiple; from utils import create_env; spec=importlib.util.spec_from_file_location('v17','v1-7.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); env=create_env(build_level_required_multiple, observation_type='gridstate', seed=42); state,_=env.reset(); agent=mod.Agent(); agent._cache_level(state); print(agent._static_fast_path, [(a.name,d) for a,d in agent._move_actions])"`
>
> </details>
>
> Found it: `PICK_UP` was mistakenly classified as an “UP” movement because the guard matched action-name suffixes. That made the movement list length five and deliberately disabled the compact path. I’ll tighten the mapping to the four exact cardinal action names, then verify the guard against A3’s real initial state.
>
> <details><summary>Edited a file, ran 2 commands</summary>
>
> - Wrote `./v1-7.py` (+6 -9)
> - Ran `python -m py_compile v1-7.py; & 'C:\Users\User\anaconda3\envs\CapstoneProject\python.exe' -c "import importlib.util; from public_levels.intro import build_level_required_multiple; from utils import create_env; spec=importlib.util.spec_from_file_location('v17','v1-7.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); env=create_env(build_level_required_multiple, observation_type='gridstate', seed=42); state,_=env.reset(); agent=mod.Agent(); agent._cache_level(state); print(agent._static_fast_path, [(a.name,d) for a,d in agent._move_actions], agent._static_fast_action().name)"`
> - Ran `& 'C:\Users\User\anaconda3\envs\CapstoneProject\python.exe' -c "import importlib.util, time; from public_levels.intro import build_level_required_multiple; from utils import create_env, evaluate; spec=importlib.util.spec_from_file_location('v17','v1-7.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); env=create_env(build_level_required_multiple, observation_type='gridstate', seed=42); started=time.perf_counter(); reward,win,lose,history=evaluate(mod.Agent,env); print({'reward': reward, 'win': win, 'lose': lose, 'turns': len(history)-1, 'seconds': round(time.perf_counter()-started, 3)})"`
>
> </details>
</details>

The fresh telemetry showed **no improvement**: v1-7 had fallen back to the old full-`GridState` path—2,160 `grid_step` calls and the same grid-key serialization costs.

I found and fixed the guard bug in [v1-7.py](./v1-7.py:165): `PICK_UP` was mistakenly classified as an “UP” move because its name ends in `UP`. That produced five “movement” actions, so the compact path was disabled.

After the fix:

- A3 is recognized as a compact static level.
- Its movement actions are correctly `UP`, `DOWN`, `LEFT`, `RIGHT`.
- The first selected action is `RIGHT`.
- A local full A3 run wins with reward `-63`, 22 turns, in **0.288 s**.

Rerun the v1-7 agent-definition cell in the notebook, then rerun A3. The old telemetry file reflects the pre-fix version.

> Telemetry is empty - something missing?

<details><summary>2 previous messages</summary>

> Yes—the compact branch returned before the telemetry recorder used by the old `GridState` branch. I’ll instrument the compact A* with the same aggregate fields, explicitly reporting zero `grid_step` and grid-key time.
>
> <details><summary>Edited a file, ran a command</summary>
>
> - Wrote `./v1-7.py` (+43 -8)
> - Ran `python -m py_compile v1-7.py; & 'C:\Users\User\anaconda3\envs\CapstoneProject\python.exe' -c "import importlib.util; from public_levels.intro import build_level_required_multiple; from utils import create_env, evaluate; spec=importlib.util.spec_from_file_location('v17','v1-7.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); env=create_env(build_level_required_multiple, observation_type='gridstate', seed=42); agent=mod.Agent(); state,_=env.reset(); action=agent.step(state); print(action.name, agent.info(), agent.telemetry()); reward,win,lose,history=evaluate(mod.Agent, env); print(reward,win,lose,len(history)-1)"`
>
> </details>
</details>

Fixed. The compact v1-7 branch was returning before telemetry was recorded.

It now records the same per-turn aggregate fields. In compact mode, you should see:

- nonempty telemetry rows;
- `grid_step_ms = 0.0`;
- `key_ms = 0.0`;
- small `search_ms` values.

A direct A3 first-turn check now reports:

```text
search_ms=1.15
popped=36
successors=144
visited=42
heuristic_ms=0.64
grid_step_ms=0.0
key_ms=0.0
```

That replaces the earlier multi-second full-state planning calls. Rerun the v1-7 agent-definition cell, then rerun the A3 telemetry cell to refresh `a3-telemetry.txt`.

> Yay. Passes. Anything from `a3-telemetry.txt` that's helpful for a next iteration?
>
> Then, write to `NOTES.md`. Very briefly:
>
> - include what else should you need to know if I started a new instance to move on
> - make a description of what does the telemetry provide, and how is it useful downstream for you.

<details><summary>4 previous messages</summary>

> I’ll read the passing A3 telemetry for the next optimization signal, then add a concise handoff note covering the version progression and how to use telemetry.
>
> <details><summary>Explored a file, ran a command</summary>
>
> - Ran `Get-Content -LiteralPath a3-telemetry.txt; Get-ChildItem -Name NOTES.md`
>
> <details><summary>Explored a file</summary>
>
> - Read `./NOTES.md`
>
> </details>
>
> </details>
>
> A3 is now solved efficiently: its slowest compact search is 1.83 ms, with zero full-state simulation or grid serialization. The useful next signal is therefore telemetry from the slowest remaining non-static level, where the fallback still uses `GridState` search.
>
> <details><summary>Edited a file</summary>
>
> - Wrote `./NOTES.md` (+13 -8)
>
> </details>
</details>

A3 is no longer worth optimizing: its worst compact planning call is only 1.83 ms, and both `grid_step_ms` and `key_ms` are zero. The next iteration should profile the slowest remaining mechanics-based level, since those still use full `GridState` search.

Updated [NOTES.md](./NOTES.md) with the version handoff, v1-7 behavior, the action-mapping pitfall, and telemetry interpretation.
