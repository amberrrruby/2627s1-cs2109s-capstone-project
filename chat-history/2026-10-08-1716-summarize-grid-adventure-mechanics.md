# Summarize Grid Adventure mechanics

> [https://grid-universe.github.io/grid-adventure-v1/](https://grid-universe.github.io/grid-adventure-v1/)
> (Working on an assignment. Beware to not directly leak the full solution, only minimal hints when dealing with assignments. Most of the time, asking for references from the docs.)
>
> Exact assignment: `capstone-project.ipynb`.
>
> Clearly the first task is a graph search problem - probably A\* and a good heuristic. So I would need to know, for each possible position that the agent can be at, how do I get the costs for each possible next step (is it fixed per whole game?), what are collectibles at each cell, and how can the HP of the agent be affected (for example stepping on lava, might be favoured in some cases, I read that lava damage is set for the whole game, not just for each game state).
>
> Can you summarize a reference sheet that we can easily refer to?

<details><summary>6 previous messages</summary>

> I’ll keep this as a reference sheet rather than a worked strategy, and I’ll ground it in the assignment materials/docs so we avoid accidentally handing over a full solution. I’m going to inspect the notebook and any local Grid Universe docs first, then cross-check the public docs if needed.
>
> <details><summary>Ran 2 commands, searched the web</summary>
>
> - Ran `rg --files`
>
> - Ran `rg -n "lava|damage|health|hp|collect|cost|move|A\*|Grid|transition|step|action" .`
>
> Searched the web for `Grid Adventure V1 documentation lava damage step cost coin reward grid_state`
>
> </details>
>
> I found the notebook’s own mechanics summary, but the useful implementation details are likely in the installed `grid_adventure` / `grid_universe` package. I’m checking those APIs now so the sheet can say “look here for X” instead of guessing from behavior.
>
> <details><summary>Ran 2 commands</summary>
>
> - Ran `python -c "import json; nb=json.load(open('capstone-project.ipynb', encoding='utf-8')); import re; pats=('Grid Adventure V1','Each entity type','There can be','step_cost','Task 1');
> for i,c in enumerate(nb['cells']):
>     src=''.join(c.get('source',[]));
>     if any(p in src for p in pats):
>         print('CELL',i); print(src[:2500].replace('\\n','\n'))"`
> - Ran `python -c "import inspect, grid_adventure, grid_universe; import grid_adventure.grid as g; import grid_adventure.step as s; import grid_adventure.entities as e; print(grid_adventure.__file__); print(grid_universe.__file__); print(g.__file__); print(s.__file__); print(e.__file__)"`
>
> </details>
>
> The default shell Python doesn’t have the assignment package installed, so I’m leaning on the notebook plus the package docs/site rather than pretending the imports work here. The notebook already confirms the key constants: step cost 3, coin reward 5, lava damage 2, power-up durations, and Task 1’s `GridState` input.
>
> <details><summary>Searched the web</summary>
>
> Searched the web for `https://grid-universe.github.io/grid-adventure-v1/`
>
> Searched the web for `https://grid-universe.github.io/grid-adventure-v1/`
>
> Searched the web for `https://grid-universe.github.io/grid-adventure-v1/game/powerups/`
>
> Searched the web for `https://grid-universe.github.io/grid-adventure-v1/game/entities/`
>
> </details>
</details>

Here’s a compact reference sheet for Task 1 without turning it into a full agent solution.

**Grid Adventure V1 Reference Sheet**

**Core objective**
- Win by collecting all gems, if any, then reaching the exit.
- Coins are optional; collect them only if the reward beats the extra action/detour cost.
- Losing occurs if HP reaches `0`.

Docs: [Objective and rewards](https://grid-universe.github.io/grid-adventure-v1/game/objectives-and-rewards/)

**State shape**
- Task 1 gives you a structured `GridState`.
- Main fields:
  - `state.width`, `state.height`
  - `state.grid[x][y]`: list of entities at cell `(x, y)`
  - `state.score`, `state.turn`, `state.win`, `state.lose`
  - `state.step_cost`, usually `3`
- Use `isinstance(entity, SomeEntityClass)` to identify objects.

Docs: [GridState](https://grid-universe.github.io/grid-adventure-v1/agent/gridstate/), [Entities](https://grid-universe.github.io/grid-adventure-v1/game/entities/)

```python
for x in range(state.width):
    for y in range(state.height):
        for ent in state.grid[x][y]:
            if isinstance(ent, AgentEntity):
                agent_pos = (x, y)
            elif isinstance(ent, CoinEntity):
                coins.add((x, y))
            elif isinstance(ent, GemEntity):
                gems.add((x, y))
            elif isinstance(ent, LavaEntity):
                lava.add((x, y))
```

**Actions**
Available actions are:

```python
Action.UP
Action.DOWN
Action.LEFT
Action.RIGHT
Action.USE_KEY
Action.PICK_UP
Action.WAIT
```

Each action consumes one turn unless it ends the game. Wasted actions still cost a turn, e.g. walking into a wall, picking up nothing, or using a key with no door nearby.

Docs: [Actions and movement](https://grid-universe.github.io/grid-adventure-v1/game/actions-and-movement/)

**Transition / next-state reference**
For Task 1, the cleanest way to answer “what happens if I do action A?” is to use the provided simulator:

```python
next_state = grid_step(current_state, action)
```

Then inspect:

```python
score_delta = next_state.score - current_state.score
hp_after = ...
win = next_state.win
lose = next_state.lose
```

For planning, this is useful because you do not need to manually reproduce every rule immediately. Treat `grid_step` as the authoritative transition function.

**Costs / rewards**
Fixed constants in this assignment:
- Normal non-final action: reward `-3`
- Final winning action: no `-3` turn penalty
- Coin pickup: `+5`
- Lava damage: `2` HP damage, not direct score damage
- A non-terminal `PICK_UP` that collects one coin has net score change `+2`: `+5 - 3`.

Docs: [Objective and rewards](https://grid-universe.github.io/grid-adventure-v1/game/objectives-and-rewards/)

If you frame search as reward maximization, use score deltas directly. If you frame it as cost minimization, be careful: coin pickups can create negative “cost” edges, which ordinary UCS/A* assumptions may not like.

**HP / lava**
- Lava deals `2` damage whenever the agent is processed on the same tile.
- This includes moving onto lava, moving through lava with speed, or taking another action while still standing on lava.
- If HP reaches `0`, the game is lost.
- Shield prevents damage and consumes one shield use.
- Phasing also prevents lava damage while active.

Docs: [Lava entity](https://grid-universe.github.io/grid-adventure-v1/game/entities/), [Powerups](https://grid-universe.github.io/grid-adventure-v1/game/powerups/)

**Collectibles**
Collectibles require a separate `PICK_UP` action after standing on their tile:
- `CoinEntity`: optional, `+5`
- `GemEntity`: required
- `KeyEntity`: used for locked doors
- `SpeedPowerUpEntity`: boots
- `ShieldPowerUpEntity`
- `PhasingPowerUpEntity`

Docs: [Entities](https://grid-universe.github.io/grid-adventure-v1/game/entities/)

**Power-ups**
- Boots / speed: move up to 2 tiles per movement action for 5 turns. Intermediate tile is still processed.
- Shield: prevents lava damage for 5 uses.
- Phasing: pass through blocking objects for 5 turns and avoid lava damage.
- Turn-limited powerups do not count down on the pickup action itself.

Docs: [Powerups and effects](https://grid-universe.github.io/grid-adventure-v1/game/powerups/)

**Important planning state variables**
For graph search, position alone is usually not enough. State identity may need to account for:
- Agent position
- Remaining gems
- Remaining useful coins, if optimizing score
- Keys held / doors unlocked
- HP
- Power-up timers / shield uses
- Box positions, if boxes appear
- Whether the game has already won/lost

Good next reference to read: the docs pages above, then `tutorial.ipynb` sections on finding entities and applying `step`.

> What's the ultimate objective / deliverable for stage 1? What's *the* function I'll be working with, and what are the inputs and the expected outputs?

For **Stage / Task 1**, the deliverable is:

Implement an `Agent` class whose `step(...)` method can play Grid Adventure from a fully structured `GridState`.

The one function you’ll mainly work with is:

```python
class Agent:
    def step(self, state: GridState) -> Action:
        ...
```

**Input**
`state` is a `GridState` object. It gives you the full structured game state: grid size, entities in each cell, agent position/health/status, score, win/lose flags, etc. No image parsing is needed for Task 1.

**Output**
Return exactly one valid `Action` enum value, for example:

```python
return Action.UP
return Action.PICK_UP
return Action.USE_KEY
```

The environment calls your `step` once per turn, applies the returned action, then calls you again with the next state.

**Ultimate objective**
Make the agent complete the level while maximizing score / minimizing total cost:

1. Collect all required gems.
2. Reach the exit.
3. Avoid losing, e.g. HP reaching zero.
4. Prefer lower-cost / higher-reward paths, including deciding whether optional coins or risky routes are worth it.

So mentally, Task 1 is: given a complete symbolic game state, choose the next action in a plan. You can think of `step(state) -> Action` as the public wrapper around whatever planner/search code you build internally.

> Basically graph search for task 1? Is there a provided "simulator" machine where we can use for generating successor states instead of writing the transition solution myself?

Yes: Task 1 is basically a graph search / planning problem over structured game states.

And yes, there is a provided transition simulator:

```python
from grid_adventure.grid import step as grid_step
from grid_adventure.step import Action
```

You can use it like:

```python
next_state = grid_step(current_state, action)
```

So for successor generation, you can usually do:

```python
for action in Action:
    next_state = grid_step(state, action)
    if not next_state.lose:
        ...
```

That lets you avoid hand-writing most of the transition logic: movement, lava damage, pickups, keys, doors, boxes, power-ups, win/lose checks, score changes, etc.

The usual search framing is:

```python
node = current GridState
edge = one Action
successor = grid_step(node, action)
edge reward/cost = successor.score - node.score
goal = successor.win
```

One caution: for graph search you’ll still need your own compact “state key” for visited/pruning, because `GridState` objects themselves probably aren’t a nice hashable search key. At minimum, that key likely needs position, remaining gems, keys/doors, HP, power-up status, and box positions when boxes matter.

> Briefly check: is there such an attribute implemented?

<details><summary>4 previous messages</summary>

> I’ll do a quick local inspection rather than relying on memory. First I’m checking whether the assignment environment/package is visible from this shell and, if not, I’ll look through the notebook/source references for how `GridState` is accessed.
>
> <details><summary>Ran 2 commands</summary>
>
> - Ran `rg -n "\.grid|\.width|\.height|\.score|\.win|\.lose|\.turn|\.status|health|inventory|GridState\(" capstone-project.ipynb tutorial.ipynb public_levels utils.py`
> - Ran `python -c "import grid_adventure, grid_universe; from grid_adventure.grid import GridState; import inspect; print('grid_adventure', grid_adventure.__file__); print('GridState', GridState); print([a for a in dir(GridState) if not a.startswith('__')][:200])"`
>
> </details>
>
> The parallel shell call hit a local exec setup hiccup, so I’m retrying with a narrower command.
>
> <details><summary>Ran a command</summary>
>
> - Ran `python -c "import grid_adventure, grid_universe; from grid_adventure.grid import GridState; import inspect; print('grid_adventure', grid_adventure.__file__); print('GridState', GridState); print([a for a in dir(GridState) if not a.startswith('__')][:200])"`
>
> </details>
</details>

Briefly: I don’t think there is a ready-made “search key” / hash attribute on `GridState`.

The provided thing is the **transition simulator**:

```python
next_state = grid_step(current_state, action)
```

But for visited-state pruning, you should probably make your own key, e.g.:

```python
key = (
    agent_pos,
    agent_hp,
    frozenset(remaining_gems),
    keys_held,
    frozenset(locked_doors),
    frozenset(box_positions),
    active_powerups,
)
```

There may be helper conversion functions like `to_state` / `from_state`, but I would not assume `GridState` itself is safely hashable or has a canonical `.id` / `.key` unless the docs explicitly say so.

> So basically: I get a `GridState`, and that contains the whole game grid, and tells me what entities are on which cell. (Task 2 gives me a picture of that instead, and I have to parse it into a `GridState`. Task 3 is a mix and has stricter bounds. Correct?)
>
> So I try out the algorithms: BFS, DFS, UCS, A\*, IDS, DLS - if I've written a minimax alpha-beta pruning "agent", how far away is this task, or am I literally ready (which leaves us with "heuristic engineering")?

Yes, your summary is correct.

- **Task 1:** you receive a structured `GridState`: full grid, entities, agent state, score/status.
- **Task 2:** you receive an image observation plus limited metadata, so you need perception/parsing before planning.
- **Task 3:** may give either representation and uses harder/larger cases.

For Task 1, this is much closer to **single-agent graph search / shortest path planning** than minimax.

If you already wrote a minimax alpha-beta agent, you probably have several transferable pieces:

- representing states
- generating legal actions
- recursively/iteratively exploring future states
- evaluating terminal states
- pruning repeated states
- returning the first action of the chosen line

But the search objective is different. There is no opponent, so alpha-beta itself mostly disappears. You replace:

```text
max node / min node / alpha-beta bounds
```

with something like:

```text
frontier priority = cost_so_far + heuristic
visited[state_key] = best cost/reward seen so far
goal = state.win
```

How far away are you? Conceptually, not far. Mechanically, you need to adapt the engine from adversarial search to path search.

For Task 1, I’d focus on these in order:

1. **Successor generation**
   Use `grid_step(state, action)` for each `Action`.

2. **Terminal tests**
   `state.win`, `state.lose`.

3. **State key**
   Build a compact hashable key. This is probably the biggest practical piece.

4. **Cost/reward model**
   Use score delta or accumulated cost. Be careful: coins produce positive reward, so not every edge is a simple positive cost unless you transform the objective carefully.

5. **Search algorithm**
   Start with UCS or A*. BFS is only good if all actions are equal and optional rewards/hazards don’t matter.

6. **Heuristic**
   Once UCS works, add a conservative heuristic: distance to remaining gems plus exit, accounting roughly for walls if possible.

So no, you are not “literally ready” just because you have minimax, but you are much closer than starting from scratch. The remaining work is mainly converting your mental model from “choose best move against opponent” to “find best action sequence through a deterministic state graph.”

> Cost / reward: just an accumulated cost then?
> Algorithm: I guess A* it is. We can use UCS as a baseline.
>
> Anything I missed? Then let's take a look at Task 2's description - is it just a NN? If I've done MNIST before, it's just that, but I need to generate cases with some pertubances for the training data.

Yes: for Task 1, the clean framing is:

```text
accumulated path value = sum of per-action score deltas
```

or equivalently:

```text
accumulated cost = -sum(score deltas)
```

For UCS/A*, you usually want to minimize cost, so you can treat:

```python
edge_cost = -(next_state.score - state.score)
```

But one subtlety: coins can make `edge_cost` negative, because picking up a coin gives net positive reward. Vanilla UCS/A* assumes non-negative edge costs, so either:

- use accumulated **reward maximization** with priority adapted carefully, or
- ignore optional coins at first and solve “win reliably” with mostly positive movement costs, then add coin logic later, or
- transform the scoring so your priority remains well-behaved.

What you might have missed for Task 1:

- State key matters a lot: position only is not enough.
- `Action.PICK_UP` and `Action.USE_KEY` are actions too, not free interactions.
- Boots can move two cells, so “neighbor” is not always adjacent.
- Lava affects feasibility through HP, not just score.
- Boxes and doors can change the map, so the map is not always static.
- The final winning move does not pay normal turn cost, so score deltas from `grid_step` are safer than manually estimating.

For Task 2: not necessarily “just a NN,” but an MNIST-style classifier is a very reasonable route.

Task 2 gives you a rendered image instead of direct entities. The job becomes:

```text
image observation -> inferred structured grid -> reuse Task 1 planner
```

The easiest mental decomposition is:

1. Detect grid geometry / cell size.
2. Crop each cell.
3. Classify the entity in that cell.
4. Reconstruct a `GridState` or your own equivalent internal state.
5. Feed that into the Task 1 planner.

A CNN classifier over cell crops is very MNIST-like. The main extra complications are:

- You need labels, likely generated from public levels / known `GridState`s.
- Graded images may use held-out visual variants, so exact template matching may be brittle.
- You’ll want augmentations: small shifts, brightness/contrast, noise, maybe asset variants.
- Some metadata may already be supplied in the `ImageObservation`, e.g. agent health/inventory/status, so do not relearn what is handed to you.
- Empty floor vs wall/lava/exit/objects must be robust; misclassifying one tile can break planning.

So the big picture is right: **Task 1 = planner**, **Task 2 = perception + planner**, **Task 3 = robustness + both input modes**.

> Briefly answer:
>
> Anything about the model that is specified?
> Are ML libraries banned, or what libraries are allowed and provided?

<details><summary>2 previous messages</summary>

> I’ll quickly check the notebook/environment file so I don’t hallucinate the rules here.
>
> <details><summary>Explored a file, ran a command</summary>
>
> - Ran `rg -n "machine learning|ML|PyTorch|torch|tensorflow|sklearn|library|libraries|banned|allowed|environment|Hardcoding|model" capstone-project.ipynb environment.yml`
>
> <details><summary>Explored a file</summary>
>
> - Read `./environment.yml`
>
> </details>
>
> </details>
</details>

Briefly:

**Model specification**
- No specific ML model architecture is required.
- The notebook appears to allow ML, including a small neural network, but you must be able to submit it in a Coursemology-friendly way.
- There is a section about **hardcoding trained ML model weights**, so the expected pattern is likely: train offline, paste weights/model code into `Agent`.

**Libraries**
- ML libraries are **not banned**.
- The notebook itself uses/imports things like `numpy`, `PIL`, `pandas`, and later `torch`, so PyTorch seems provided/allowed in the project environment.
- But you should assume Coursemology only has the libraries from `environment.yml`; avoid extra dependencies unless clearly listed there.

**Important rule**
If you use ML, the assignment says to submit supporting materials too: dataset generation scripts, training code, generated datasets if applicable. Otherwise you may get zero for the ML-based part.

So: CNN classifier is allowed in spirit, likely PyTorch-based, but keep it small, self-contained, and compatible with the provided environment.

> Right. How do I get started with Task 1, given this big broth of mess? Specifically, which function at where do I start? Say I know how to solve a LeetCode style grid search problem with A*, so that's fine. I just need to pattern match this game context to what I know.

<details><summary>3 previous messages</summary>

> Context compaction
>
> Source: automatic
> Status: completed
>
> I’ll map the notebook’s Task 1 entry point to the A* abstraction you already know, and keep the guidance at the interface level rather than giving away the assignment solution.
>
> <details><summary>Ran 4 commands</summary>
>
> - Ran `rg -n "Task 1|class Agent|def step|GridState|A\*|search" capstone-project.ipynb tutorial.ipynb utils.py`
> - Ran `python -c "import json; n=json.load(open('capstone-project.ipynb',encoding='utf-8'));\nfor i,c in enumerate(n['cells']):\n s=''.join(c.get('source',[]));\n if 300<=i<=430 or 'Task 1 - GridState' in s or 'Integrate Task 1 planner' in s: print(f'---CELL {i}---\\n{s}')"`
> - Ran `rg -n -C 18 "class Agent|def step\(|Task 1 - GridState|Integrate Task 1 planner" capstone-project.ipynb`
> - Ran `Get-Content capstone-project.ipynb | Select-Object -Skip 375 -First 70`
>
> </details>
</details>

Start at the `Agent.step` method in `capstone-project.ipynb`.

Its contract is:

```python
def step(self, state: GridState | ImageObservation) -> Action:
```

For Task 1, `state` is already a `GridState`, so your workflow is:

1. Extract the current agent/game information from `state`.
2. Treat each possible `Action` as an outgoing edge.
3. Generate successors with the provided simulator:

```python
next_state = grid_step(current_state, action)
```

4. Reject losing successors.
5. Search until a successor has `next_state.win == True`.
6. Return only the first action of the planned path.

The notebook’s starter BFS inside `step` is the template to replace. Conceptually, your A* version needs:

```text
GridState
   |
   | each Action
   v
grid_step(state, action)
   |
   v
next GridState
```

So you do not need to implement game transitions yourself. Your main work is replacing the starter `deque` frontier with a priority queue, defining a state key for `visited`, accumulating transition costs, and designing a heuristic.

One important detail: `step` is called once per environment turn. Your planner may search several hypothetical future states internally, but it must return exactly one `Action` for the real environment.

> Then I also need some observability: "ok so I do this algorithm. Let's see how good it performs - a score. Let's visually see how a specific grid is being solved". To what extent is this already provided for us?
>
> And also we need to come up with more test cases.

<details><summary>2 previous messages</summary>

> I’ll check the notebook’s evaluation and visualisation cells so I can separate what is already built in from what you still need to add for experiments and extra levels.
>
> <details><summary>Ran a command</summary>
>
> - Ran `rg -n -C 10 "evaluate\(|Grid Play|visual|render|score|history|public checks|RUN_TASK_1|create_env|play" capstone-project.ipynb utils.py`
>
> </details>
</details>

A lot of this observability is already provided.

For Task 1, the notebook gives you:

- `run_task_1_public_tests(Agent)`: runs the public Task 1 levels.
- `summarize_public_results(...)`: reports wins, losses, runtime, and performance.
- `evaluate(agent_class, env)`: runs one episode and returns:

```python
total_reward, win, lose, history
```

`history` contains `(GridState, Action)` pairs, so you can inspect exactly what the agent saw and did at every turn.

For visual debugging, use **Grid Play**:

```bash
grid-play --plugin-file public_levels/play.py
```

The notebook also provides `show_images_interactive(...)`, which can animate a recorded `history`. The included trace example uses the boss level, but you can replace its level builder with a Task 1 level.

For your own test cases, use the existing pattern:

```python
env = create_env(
    build_level_required_multiple,
    observation_type="gridstate",
    seed=42,
)

total_reward, win, lose, history = evaluate(Agent, env)
```

You should initially test one mechanic at a time, then combine them:

- simple movement and walls;
- collecting required items;
- doors and keys;
- hazards and HP;
- optional rewards versus shortest/cheapest routes;
- multiple objectives or mechanics together.

The public suite already contains 22 gameplay levels, but your custom tests are mainly for debugging specific failure modes. The grader’s hidden levels and held-out cases are not reproduced by the local suite, so passing the public checks is useful evidence, not a guarantee.

> I've modified `step()` to operate based on a priority queue. Now coming up with a heuristic.
>
> - We need to get all gems before leaving, so perhaps Manhattan / Euclidean distance to the furthest / closest gem? Then after all gems are claimed, distance to the exit?
>
> How much does the current state already provide for these? How much more do I have to work out myself?
>
> Haven't accounted for:
>
> - coins
> - shields (the state has to somehow say "do I have a shield? If so, crossing lava is free, equal to an ordinary step; or else, make it very expensive to make it unfavourable)
> - keys, speed power-up, phasing power-up (slightly bump it up?)

<details><summary>2 previous messages</summary>

> You’re at the right point: the search skeleton is mostly mechanical now; the real work is defining what a state means for goal progress and lower-bound cost. I’ll verify which fields/entities are exposed so the heuristic can read them directly rather than reconstructing game facts.
>
> <details><summary>Ran a command</summary>
>
> - Ran `rg -n -C 5 "GridState\(|state\.(agent|grid|objective|score|message|turn|win|lose)|AgentEntity|CoinEntity|GemEntity|Shield|Key|Boot|Phasing|Lava|Exit|Door" tutorial.ipynb capstone-project.ipynb utils.py`
>
> </details>
</details>

You already have most of the information needed in `GridState`. The notebook/tutorial expose the grid through:

```python
state.objects_at((x, y))
```

and you can identify entities with `isinstance`, for example:

```python
AgentEntity
GemEntity
ExitEntity
CoinEntity
LavaEntity
KeyEntity
LockedDoorEntity
ShieldPowerUpEntity
SpeedPowerUpEntity
PhasingPowerUpEntity
```

The agent itself exposes its current health and status/inventory information through its entity fields. You do not need to maintain those effects manually during search: call the provided simulator and inspect the returned state:

```python
next_state = grid_step(current_state, action)
```

That successor already reflects movement, collected items, opened doors, health changes, power-up effects, score, and win/lose status.

For a first heuristic, use only information you can justify as a lower bound:

```text
h(state) =
    distance from agent to the remaining required objectives,
    plus distance to the exit once objectives are satisfied
```

Manhattan distance is a reasonable starting point for cardinal movement. A “furthest remaining gem” bound is admissible but often weak. A better eventual heuristic can consider the cheapest ordering of remaining gems, but that is an optimization you should build incrementally.

A few corrections to your current ideas:

- Do not manually assign “very expensive” lava in `h` if you want optimal A*. Let `grid_step` determine the actual transition cost. A shield is already reflected in the successor state.
- Coins are rewards, so collecting one may make a longer route worthwhile. Treat coin value in `g` or your evaluation objective, not as an arbitrary heuristic penalty.
- Keys, boots, ghost, and shields belong in the search state because they change future transitions. You generally should not “slightly bump” the heuristic for them unless you can prove the adjustment remains admissible.
- Your visited key must include relevant inventory/status, not merely the agent’s position or raw grid layout. Two states at the same position can have very different futures if one has a key, shield, or active power-up.

A sensible progression is:

1. Implement UCS with `h = 0`.
2. Confirm it solves the structured public levels.
3. Add Manhattan-based `h`.
4. Compare runtime, expansions, wins, and reward.
5. Only then refine handling of optional coins and power-ups.

> ```lua
> py
>
>                 priority = len(next_path)
>
>                 heapq.heappush(frontier, (priority, next(tie_breaker), next_state, next_path))
> ```
>
> Just working out what to add to `priority` now. This solved, passed an extra test case (timed out on all the rest). But:
> ```scss
>     - Keep per-step latency small (single CPU, 1.5 GB RAM). Avoid O(W*H) scans of
>       the full grid every step.
> ```
>
> Which means I can't scan the grid to check for gem locations? Should I make it so that routes that got to a position where it steps on a gem, have a way higher priority?

That warning does not mean “never inspect the grid.” It means avoid repeatedly doing a full `O(W*H)` scan during every real `step()` call, especially inside every search-node expansion.

For a first implementation, scan the initial `GridState` once to locate the agent, gems, exit, etc. Then let `grid_step` simulate successors. You can later optimize state bookkeeping if profiling shows this is the bottleneck.

Do not give a state an arbitrary high priority merely because its route stepped on a gem. A* priority should remain:

```python
priority = g(next_state) + h(next_state)
```

where:

- `g`: accumulated cost so far;
- `h`: estimated remaining cost to satisfy the objective.

A useful first `h` is based on remaining gems and the exit. For example, a lower-bound idea is:

```text
distance(agent, nearest remaining gem)
+ distance(..., another remaining gem)
+ distance(last relevant point, exit)
```

But do not count a gem as “remaining” merely from the current position. Determine it from the simulated `next_state`; the simulator should already update the entities/inventory/objective state.

The timeout likely comes from search overhead as much as grid scanning. In particular:

```python
next_path = path + [action]
```

copies the entire path for every successor. A more efficient version stores a parent pointer or `(previous_node, action)` and reconstructs the path only when a win is found. Also ensure your visited key includes position plus relevant inventory/status, since position alone can incorrectly merge distinct states.

> So I do one scan initially, then keep it as an internal mutable copy of the state?

Almost. Scan the initial state once for static information, such as:

- grid dimensions;
- wall locations;
- exit location;
- initial locations of gems, coins, keys, and power-ups.

But do not mutate and reuse one `GridState` as your search state. Each hypothetical branch needs its own state, produced by:

```python
next_state = grid_step(current_state, action)
```

Use the initial scan as cached metadata, and inspect each successor only for dynamic changes such as collected gems, inventory, health, doors, and active power-ups. The simulator remains the source of truth for branch state.

> ```python
> py
>
> class Agent:
>     """
>     Grid Adventure: PQueue agent variant.
>
>     This class is the single public interface that Coursemology will import and
>     interact with when evaluating your submission. You should extend the
>     internals (add helper classes / functions in other files if you wish) but
>     MUST preserve:
>
>     1. The class name: Agent
>     2. The public method: step(self, state: GridState | ImageObservation) -> Action
>
>     High-level lifecycle per environment tick:
>         state  --->  step(...)  --->  Action
>
>     The "state" object type depends on the task:
>     - Task 1: A fully structured GridState instance.
>     - Task 2: An ImageObservation dictionary whose primary observation is an RGBA image
>       plus limited structured metadata in the 'info' sub-dict. In this case you
>       typically perform perception to build (or approximate) an internal
>       structured representation before planning.
>     - Task 3: Input state could be either a GridState instance
>       or an ImageObservation dictionary
>
>     Constraints:
>     - Keep per-step latency small (single CPU, 1.5 GB RAM). Avoid O(W*H) scans of
>       the full grid every step.
>     - Determinism helps reproducibility; seed your own RNG if you add any
>       random components.
>
>     You may add __init__ parameters (with defaults) if needed for your own
>     development, but the grader will instantiate Agent() with no arguments.
>     """
>
>     def __init__(self):
>         """Initialize your agent.
>
>         Put all one-time setup here (e.g., hardcoded ML model weights,
>         precomputing heuristic tables). Keep it fast and memory-light
>         to respect platform limits.
>         """
>         # Placeholder for any future initialization logic
>         pass
>
>     def step(self, state: GridState | ImageObservation) -> Action:
>         """Return the next action given the current environment state.
>
>         Parameters
>         ----------
>         state : GridState | ImageObservation
>             - If a GridState instance (Tasks 1 and 3): you have direct, structured
>               access to grid, entities, objective message, score, etc.
>             - If an ImageObservation dictionary (Tasks 2 and 3): contains 'image' (HxWx4 RGBA uint8)
>               plus 'info' sub-dictionary (agent stats, partial config, message).
>               You likely need to parse the image into an internal representation.
>
>         Returns
>         -------
>         Action
>             A valid action from the Action enum. Must always return a member;
>             never return None.
>         """
>
>         if not isinstance(state, GridState):
>             state = self.parse(state)
>
>         tie_breaker = count()
>         frontier = [ (0, next(tie_breaker), state, None, 0) ]
>         visited = { str(state.grid) }
>
>         while frontier:
>             _, _, current_state, first_action, depth = heapq.heappop(frontier)
>
>             for action in Action:
>                 next_state = grid_step(current_state, action)
>                 if next_state.lose:
>                     continue
>
>                 next_first_action = action if first_action is None else first_action
>                 if next_state.win:
>                     return next_first_action
>
>                 key = str(next_state.grid)
>                 if key in visited:
>                     continue
>
>                 visited.add(key)
>
>                 new_depth = depth + 1
>                 priority = new_depth + h(state)
>
>                 heapq.heappush(frontier, (priority, next(tie_breaker), next_state, next_first_action, new_depth))
>
>         return Action.WAIT
> ```
>
> But it seems like we have to scan at every `step()` call?

Yes, `step()` is called once per environment tick. However, you should not necessarily run the entire A* search from scratch on every call.

Your current code has two important issues:

1. This should use `next_state`, not `state`:

```python
priority = new_depth + h(next_state)
```

2. You are recomputing the full plan every turn. Cache the resulting action sequence in `self`.

Conceptually:

```python
def step(self, state):
    if self.plan_is_still_valid(state):
        return self.plan.pop(0)

    self.plan = self.plan_from_astar(state)
    return self.plan.pop(0)
```

The initial scan and A* search then happen when a new plan is needed, rather than on every ordinary tick. Since the game is deterministic, the next real state should match the state predicted by your plan. You can either trust that, or validate the current state against the expected state and replan if they differ.

Also fix the priority calculation before optimizing:

```python
priority = new_depth + h(next_state)
```

For performance, later replace `path + [action]` with parent pointers, but caching the plan is likely the first major improvement.

:codex-annotation{index="1"}

`plan_is_still_valid(state)` was shorthand for checking whether your cached action sequence still corresponds to the actual current state.

In this deterministic game, the simplest approach is:

```python
if self.plan:
    return self.plan.pop(0)
```

because the environment should follow the plan exactly.

A more defensive version stores the expected state after each planned action:

```python
self.plan = [(expected_next_state, action), ...]
```

Then on the next `step(state)`, compare the received state with the expected state. If they differ, discard the remaining plan and run A* again.

For now, you can omit validation and simply cache the plan. The key idea is that `step()` should return the next cached action instead of performing a new full search every turn.

> So basically: "cache (`GridState`+ necessary extra information that the state somehow didn't capture) and `Action` pairs, if state is not in cache, run A\*"?

Yes, that is the right idea, with one refinement:

- Cache a planned sequence of `(expected_state, action)` pairs, or cache the action sequence plus the expected next-state keys.
- On each `step(state)`, check whether the current state matches the next expected state.
- If it matches, return the cached action.
- If it does not match, discard the cache and run A* again.

For a deterministic environment, the extra information should be whatever affects future transitions but is not represented in your state key: agent position, health, inventory, active power-up durations, score/turn if relevant, and the remaining entities.

Do not use only the agent’s position as the cache key. Two states at the same position can require different actions if, for example, one has a key or shield and the other does not.

> Check the docs: what's in a `GridState`, what's not in a `GridState` that I have to addtionally cache?
> Currently: \`        visited = { str(state.grid) }\`.
> [https://grid-universe.github.io/grid-adventure-v1/](https://grid-universe.github.io/grid-adventure-v1/)

<details><summary>2 previous messages</summary>

> I’ll verify this against the official Grid Adventure documentation, focusing on the `GridState` fields and what `str(state.grid)` omits.
>
> <details><summary>Ran a command, searched the web</summary>
>
> Searched the web for `site:grid-universe.github.io/grid-adventure-v1 GridState grid state documentation`
>
> Searched the web for `site:grid-universe.github.io/grid-adventure-v1 GridState ...`
>
> - Ran `Get-Content capstone-project.ipynb | Select-Object -Skip 785 -First 45`
>
> </details>
</details>

`GridState` contains these top-level fields:

```text
width, height
movement, objective
seed
grid
turn, score, step_cost
win, lose
message
turn_limit
```

The `grid` contains the entities at each cell. Entity objects carry dynamic details such as the agent’s health, inventory, and active power-up status.

So:

```python
visited = {str(state.grid)}
```

is potentially incomplete. It captures the cell contents, but you should verify whether the entity string representations include all mutable agent state. For a robust search key, include at least:

```python
def state_key(state):
    return (
        str(state.grid),
        state.turn,
        state.score,
        state.win,
        state.lose,
    )
```

Whether `score` belongs depends on your search objective:

- For merely finding any winning path, score may be unnecessary.
- For maximizing reward/minimizing cost, score matters.
- `turn` matters when there is a turn limit or when final-turn scoring differs.
- Static fields such as `width`, `height`, `movement`, `objective`, and `step_cost` can usually be omitted from the key because they are constant within one level.

The official documentation describes the State view as the complete internal game state, while the notebook’s printed `GridState` confirms the fields above. [`GridState`/State documentation](https://grid-universe.github.io/grid-play/tutorial/state/)

One caution: `str(state.grid)` is not automatically guaranteed to be a canonical, complete serialization of the entire game state. For debugging, print representative states before and after collecting an item, taking damage, or activating a power-up, and check whether the string changes appropriately.

> ```php-template
> "GridState(width=7, height=7, movement=CardinalMovement(name='cardinal', description='Single-step cardinal movement.', function=<function cardinal_move_fn at 0x000002058EF57A60>), objective=CollectGemsAndExitObjective(name='collect_exit', description='Collect all gems (if any) and reach an exit tile.', functions=(<function collect_objective_fn at 0x000002058EF7A700>, <function exit_objective_fn at 0x000002058EF7A480>)), seed=0, grid=[[[], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [], [], [], [GemEntity(appearance=Appearance(name='gem', priority=4, icon=True, background=False), collectible=Collectible(), requirable=Requirable())], [ExitEntity(appearance=Appearance(name='exit', priority=9, icon=False, background=False), exit=Exit())]], [[], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [CoinEntity(appearance=Appearance(name='coin', priority=4, icon=True, background=False), collectible=Collectible(), rewardable=Rewardable(amount=5))], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [LockedDoorEntity(appearance=Appearance(name='door', priority=6, icon=False, background=False), blocking=Blocking(), locked=Locked(key_id='A'))]], [[SpeedPowerUpEntity(appearance=Appearance(name='boots', priority=4, icon=True, background=False), collectible=Collectible(), speed=Speed(multiplier=2), time_limit=TimeLimit(amount=5))], [BoxEntity(appearance=Appearance(name='box', priority=2, icon=False, background=False), blocking=Blocking(), pushable=Pushable())], [], [PhasingPowerUpEntity(appearance=Appearance(name='ghost', priority=4, icon=True, background=False), collectible=Collectible(), phasing=Phasing(), time_limit=TimeLimit(amount=5))], [], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [CoinEntity(appearance=Appearance(name='coin', priority=4, icon=True, background=False), collectible=Collectible(), rewardable=Rewardable(amount=5))]], [[WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [CoinEntity(appearance=Appearance(name='coin', priority=4, icon=True, background=False), collectible=Collectible(), rewardable=Rewardable(amount=5))], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [CoinEntity(appearance=Appearance(name='coin', priority=4, icon=True, background=False), collectible=Collectible(), rewardable=Rewardable(amount=5))]], [[ShieldPowerUpEntity(appearance=Appearance(name='shield', priority=4, icon=True, background=False), collectible=Collectible(), immunity=Immunity(), usage_limit=UsageLimit(amount=5))], [], [CoinEntity(appearance=Appearance(name='coin', priority=4, icon=True, background=False), collectible=Collectible(), rewardable=Rewardable(amount=5))], [], [KeyEntity(appearance=Appearance(name='key', priority=4, icon=True, background=False), collectible=Collectible(), key=Key(key_id='A'))], [], []], [[], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [LavaEntity(appearance=Appearance(name='lava', priority=7, icon=False, background=False), collidable=Collidable(), damage=Damage(amount=2))], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], [WallEntity(appearance=Appearance(name='wall', priority=9, icon=False, background=True), blocking=Blocking())], []], [[], [AgentEntity(agent=Agent(), appearance=Appearance(name='human', priority=0, icon=False, background=False), collidable=Collidable(), health=Health(current_health=5, max_health=5), inventory=Inventory(item_ids=set()), status=Status(effect_ids=set()))], [], [GemEntity(appearance=Appearance(name='gem', priority=4, icon=True, background=False), collectible=Collectible(), requirable=Requirable())], [], [CoinEntity(appearance=Appearance(name='coin', priority=4, icon=True, background=False), collectible=Collectible(), rewardable=Rewardable(amount=5))], []]], turn=0, score=0, step_cost=3, win=False, lose=False, message=None, turn_limit=None)"
> ```
>
> This is one state.

Exactly. This `GridState` already contains the important dynamic information inside `grid`.

For example, the `AgentEntity` includes:

```text
health.current_health
inventory.item_ids
status.effect_ids
```

and the grid also shows remaining gems, coins, keys, doors, lava, etc. Therefore, for determining future legal transitions, `str(state.grid)` likely captures the essential gameplay state.

The top-level fields not represented by `state.grid` are:

```text
turn
score
win
lose
message
turn_limit
```

Use this distinction:

```python
# Good enough for finding a winning path when no turn limit matters:
visited = {str(state.grid)}

# Safer for reward/cost-sensitive search:
visited = {
    (
        str(state.grid),
        state.turn,
        state.score,
        state.win,
        state.lose,
    )
}
```

You generally do not need to add health, inventory, or power-up status separately because they are visibly nested inside the `AgentEntity` in `grid`.

One subtlety: if your objective is only “find a win,” including `score` in `visited` can create unnecessary duplicate searches, because two otherwise identical gameplay states with different scores have the same future mechanics. If you are optimizing reward, however, score becomes relevant.

> So, say, if I want to avoid scanning the grid every `step()` call, what should the `Agent` keep, locally?

Keep the plan, not a mutable copy of the whole game state.

In `__init__`:

```python
def __init__(self):
    self.plan = []
    self.static_map = None
```

Then:

```python
def step(self, state):
    if not self.plan:
        self.static_map = self.extract_static_info(state)
        self.plan = self.plan_with_astar(state, self.static_map)

    return self.plan.pop(0)
```

`self.plan` is the remaining sequence of actions returned by A*. The first call performs the grid scan and search; later calls simply return the next cached action.

You may cache static information such as walls, exit location, and initial entity locations, but do not cache one mutable `GridState` and modify it. Each search branch must still use:

```python
next_state = grid_step(current_state, action)
```

For this deterministic assignment, trusting the cached plan is the cheapest option. A defensive implementation could compare the actual state against an expected state, but constructing that comparison may itself require scanning/serializing the grid each turn. Replan only when the cached plan is exhausted or if you have evidence that the real state diverged.

> But it could be the case that the `Agent` takes in consecutively, totally different grid state levels through `step()` calls. Are we assuming that consecutive `step()` calls are of the same level?
> Check the notebook if needed. Say, if I want to get the position of all the gems in the map.

<details><summary>2 previous messages</summary>

> Good catch. I’ll verify the evaluation lifecycle in the notebook: specifically whether one `Agent` instance is reused across episodes or created fresh, and whether consecutive `step()` calls within an episode stay on the same level.
>
> <details><summary>Ran a command</summary>
>
> - Ran `rg -n -C 12 "agent_class\(\)|env.reset\(|Agent\(\)|evaluate\(|one environment|episode|per environment|step\(" capstone-project.ipynb utils.py`
>
> </details>
</details>

Yes, consecutive `step()` calls within one episode are for the same level. The environment does:

```python
state, _ = env.reset()
agent = agent_class()

while not (win or lose):
    action = agent.step(state)
    state, ... = env.step(action)
```

The public evaluation creates a fresh `Agent` for each evaluated environment, so your cache is naturally reset per level.

Thus, for finding all gem positions:

```python
def step(self, state):
    if not self.plan:
        self.gem_positions = self.find_gems(state)
        self.plan = self.plan_with_astar(state)

    return self.plan.pop(0)
```

That initial scan happens once for the episode, not once per action.

If you want to make the class robust to an evaluator reusing the same `Agent` across levels, reset cached data when you detect a new initial state, typically:

```python
if state.turn == 0:
    self.plan = []
    self.gem_positions = None
```

Then scan and plan again. Do not assume that arbitrary consecutive calls represent unrelated levels; within an episode they represent successive states of the same level.
