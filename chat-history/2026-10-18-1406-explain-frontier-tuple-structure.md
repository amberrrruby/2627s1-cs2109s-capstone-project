# Explain frontier tuple structure

> I'm starting with the first task of the capstone project. (Refer to the notebook for context.)
>
> To get the hang of the whole mess, I decided to first change the deque in the algorithm to a priority queue.
>
> ```
> py
>
>         frontier = deque([(state, [])])
> ```
>
> What does this mean? What does the second `[]` do? If I'm swapping it out with a deque, I need something that's comparable - perhaps I could make a small wrapper struct that defines an order.

<details><summary>2 previous messages</summary>

> I’ll look at the first-task notebook so I can map that `frontier` entry to the surrounding search algorithm rather than explain it in isolation.
>
> <details><summary>Ran 3 commands</summary>
>
> - Ran `rg --files -g "*.ipynb" -g "*.py" -g "README*"`
> - Ran `rg -n -C 5 "frontier\s*=|deque\(" work.py tutorial.ipynb capstone-project.ipynb`
> - Ran `Get-Content -LiteralPath work.py | Select-Object -Skip 75 -First 100; rg -n -C 4 "class GridState|def successors|def actions|append\(" work.py`
>
> </details>
</details>

`(state, [])` is one frontier entry: a 2-tuple containing

1. `state` — the board position to explore
2. `[]` — the sequence of actions that led from the starting position to that state

So later:

```python
current_state, path = frontier.popleft()
```

unpacks that tuple. For each possible next move, this line extends the recorded route:

```python
next_path = path + [action]
```

The initial state has an empty route because no moves have been made yet. When a win is found, `next_path[0]` returns the first move of the winning route—the only action `step()` needs to return.

A priority queue is a reasonable next experiment. Python’s `heapq` requires its entries to be orderable, but you don’t need to make `GridState` itself comparable. Store priority first, followed by a monotonically increasing tie-breaker:

```python
import heapq
from itertools import count

tie_breaker = count()
frontier = [(0, next(tie_breaker), state, [])]

while frontier:
    _, _, current_state, path = heapq.heappop(frontier)

    for action in Action:
        next_state = grid_step(current_state, action)
        # ... skip losing / visited states ...

        next_path = path + [action]
        priority = len(next_path)  # equivalent to breadth-first search here
        heapq.heappush(
            frontier,
            (priority, next(tie_breaker), next_state, next_path),
        )
```

The counter matters: if two priorities tie, Python otherwise tries to compare `GridState` objects, which likely raises a `TypeError`.

With `priority = len(next_path)`, this is effectively BFS with extra machinery: shorter paths are still explored first. The priority queue becomes valuable once the priority expresses something smarter, e.g. `len(next_path) + estimated_distance_to_goal` for A*.

> Right. A good next improvement is to change it so that `path + [action]` is avoided, and instead I track with `previous_node`s and `action`s. Do I even need the whole path though? I just need an action for the next step.

You don’t need the full path if `step()` only returns the next action.

The simplest approach is to carry just the **first action** taken from the original state:

```python
frontier = deque([(state, None)])

while frontier:
    current_state, first_action = frontier.popleft()

    for action in Action:
        next_state = grid_step(current_state, action)
        if next_state.lose:
            continue

        next_first_action = action if first_action is None else first_action

        if next_state.win:
            return next_first_action

        key = str(next_state.grid)
        if key in visited:
            continue

        visited.add(key)
        frontier.append((next_state, next_first_action))
```

For a priority queue, you may also want to retain `cost_so_far` / `depth` for the priority calculation:

```python
# (priority, tie_breaker, state, first_action, cost_so_far)
```

Use `previous_node` plus `action` only if you need to reconstruct the entire winning plan—for debugging, visualisation, or executing a multi-step plan later. To choose one immediate action, propagating `first_action` is both simpler and more memory-efficient.

:codex-annotation{index="1"} `cost_so_far` is not a tie-breaker. The counter/tie-breaker is only there to prevent Python from trying to compare two `GridState`s when priorities are equal.

`cost_so_far` means “how many moves have we made to reach this node?” It is useful only when your priority depends on route cost:

```python
priority = cost_so_far + heuristic(next_state)  # A*
```

or:

```python
priority = cost_so_far  # uniform-cost search
```

For your current BFS—or for a priority queue ordered solely by a heuristic—you do not need it. You can keep frontier items as:

```python
(priority, tie_breaker, state, first_action)
```

Add `cost_so_far` only once you want the queue to prefer both cheap-so-far paths and states that appear closer to the goal.

> ```python
> py
>
>         tie_breaker = count()
>         frontier = [ (0, next(tie_breaker), state, None) ]
>         visited = { str(state.grid) }
>
>         while frontier:
>             _, _, current_state, first_action = heapq.heappop(frontier)
>
>             for action in Action:
>                 next_state = grid_step(current_state, action)
>                 if next_state.lose:
>                     continue
>
>                 next_path = path + [action] # TODO:
>                 if next_state.win:
>                     return next_path[0]
>
>                 key = str(next_state.grid)
>                 if key in visited:
>                     continue
>
>                 visited.add(key)
>
>                 priority = len(next_path) # heuristic here
>
>                 heapq.heappush(frontier, (priority, next(tie_breaker), next_state, next_path))
>
>         return Action.WAIT
> ```
>
> Can you help me modify so `first_action` is tracked (and appropriately updated, check if it is `None`)?

Replace `path` / `next_path` with `first_action` propagation:

```python
tie_breaker = count()
frontier = [(0, next(tie_breaker), state, None)]
visited = {str(state.grid)}

while frontier:
    _, _, current_state, first_action = heapq.heappop(frontier)

    for action in Action:
        next_state = grid_step(current_state, action)
        if next_state.lose:
            continue

        # The first move stays unchanged after the first expansion.
        next_first_action = action if first_action is None else first_action

        if next_state.win:
            return next_first_action

        key = str(next_state.grid)
        if key in visited:
            continue

        visited.add(key)

        heapq.heappush(
            frontier,
            (0, next(tie_breaker), next_state, next_first_action),
        )

return Action.WAIT
```

I used `0` as the priority because, after removing `path`, `len(next_path)` no longer exists. Replace that `0` with your actual heuristic when you add one:

```python
priority = heuristic(next_state)
```

If you want priority to preserve breadth-first behavior for now, track a separate integer `depth` too:

```python
# (priority, tie_breaker, state, first_action, depth)
```

> (Don't think "for now, XYZ can do"s from now on. Think as if I'm writing the final solution now. Step by step fine, but a step too simple is not, simplifying too much now affects later work.)
>
> What should we incorporate in the final heuristic?
>
> - We need to get to all the gems, collect them then get to the exit.
> - Coins - if it doesn't cost too much, collect coins. No idea yet.
> - Power-ups - no idea yet.
>
> To add the gem part, do I find Manhattan (or Euclidean?) distance to each gem? To the closest gem? Furthest gem?

<details><summary>2 previous messages</summary>

> I’ll check the project’s entity and scoring rules before recommending a heuristic, since whether gems disappear, movement is cardinal, and whether hazards matter changes what is admissible and useful.
>
> <details><summary>Ran a command</summary>
>
> - Ran `rg -n -C 4 "Gem|gem|Coin|coin|Power|power|exit|Exit|STEP_COST|collect_gems" public_levels work.py utils.py capstone-project.ipynb`
>
> </details>
</details>

Use **Manhattan distance**, not Euclidean distance: movement is cardinal—one horizontal or vertical tile at a time—so Manhattan distance matches the movement geometry. Euclidean distance is not meaningful for this grid.

But do not use only “distance to the closest gem.” It ignores the other required gems and the exit, so it becomes a very weak guide. “Distance to the furthest gem” has the same problem.

For the finished planner, use an A* priority:

```python
priority = g(next_state) + h(next_state)
```

- `g`: the exact cost accumulated so far—ideally derived from the score change caused by each transition.
- `h`: an optimistic lower bound on the remaining cost to collect every remaining gem and then reach the exit.

A good gem heuristic is:

```text
if no gems remain:
    h = distance(agent, exit)
else:
    h =
        min(distance(agent, gem) for gem in remaining_gems)
        + MST_cost(remaining_gems ∪ {exit})
```

Here, `MST_cost` is the weight of a minimum spanning tree whose nodes are all remaining gems plus the exit, with Manhattan distances as edge weights.

Why this shape?

```text
agent → first gem → …all other gems… → exit
```

Any valid solution must:

1. reach some first gem;
2. connect every remaining gem and the exit somehow.

The MST is a lower bound for that required connection, so it is safe for A*: it can underestimate but should not overestimate.

For a single gem this naturally becomes:

```text
Manhattan(agent, gem) + Manhattan(gem, exit)
```

For no gems:

```text
Manhattan(agent, exit)
```

Walls, doors, boxes, lava, coins, and power-ups make the real route more expensive or more complicated. Initially, keep them out of `h` and let `g` capture their actual costs and rewards as `grid_step` simulates them. That preserves an optimistic heuristic.

Coins are optional, so they should not be added to the required-gem heuristic. Their reward belongs in `g`: a path that collects a coin has lower actual accumulated cost. Likewise, a power-up’s value should emerge from its actual downstream effect—fewer moves via Boots, passage through walls via Ghost, or avoided lava damage via Shield—rather than from a guessed bonus in `h`.

One important final-design detail: once coins and alternative routes can produce different costs, replace `visited` with a `best_g` mapping. Reaching the same state again can be worth keeping if its new accumulated cost is lower.
