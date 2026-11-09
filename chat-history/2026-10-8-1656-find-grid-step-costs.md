# Find grid step costs

> https://grid-universe.github.io/grid-adventure-v1/
>
> ```csharp
> ## Tutorial 2: Boxes, coins, and lava
>
> Find an action sequence that completes the level with the highest possible score. A box can be pushed onto a coin, but it cannot be pushed onto lava.
> ```
> ```csharp
> gridstate_2_2 = GridState(
>     width=6,
>     height=4,
>     movement=MOVEMENTS["cardinal"],
>     objective=OBJECTIVES["collect_gems_and_exit"],
>     seed=1,
>     step_cost=STEP_COST,
> )
>
> wall_positions = [
>     (0, 0), (0, 3), (1, 0), (1, 3), (2, 3),
>     (3, 2), (3, 3), (4, 2), (4, 3), (5, 2), (5, 3),
> ]
> for position in wall_positions:
>     gridstate_2_2.add(position, WallEntity())
>
> gridstate_2_2.add((0, 1), AgentEntity())
> gridstate_2_2.add((2, 1), BoxEntity())
> gridstate_2_2.add((3, 1), CoinEntity())
> gridstate_2_2.add((4, 1), LavaEntity())
> gridstate_2_2.add((5, 1), ExitEntity())
>
> display(renderer.render(to_state(gridstate_2_2)))
> ```
> ```python
> # TODO: Complete the action list using Action.UP, Action.DOWN,
> # Action.LEFT, Action.RIGHT, and Action.PICK_UP.
> actions = [
>     Action.DOWN, Action.RIGHT, Action.RIGHT, Action.UP, Action.RIGHT, Action.PICK_UP, Action.RIGHT, Action.RIGHT
> ]
>
> result_2_2 = gridstate_2_2
> for action in actions:
>     result_2_2 = step(result_2_2, action)
>
> display(renderer.render(to_state(result_2_2)))
>
> if result_2_2.win:
>     print("Congratulations! You solved the grid. Total score:", result_2_2.score)
>     if result_2_2.score == -16:
>         print("You achieved the highest possible score!")
>     else:
>         print("Try another route to reach the optimal score of -16.")
> elif result_2_2.lose:
>     print("The agent lost. Try another action sequence.")
> else:
>     print("The grid is not yet solved. Keep trying!")
> ```
>
> This sequence of steps requires the agent to walk pass a block of lava. In this case, how do I know the scores for walking past it? In general, given a `gridstate` how (check the docs for me) do I know the cost of each step, and the effects of stepping on, say, a block of lava?

<details><summary>2 previous messages</summary>

> I’ll check the Grid Universe docs/source around movement, rewards, and entity interactions so the answer is anchored in how this environment actually computes score, not just inferred from the tutorial text.
>
> <details><summary>Searched the web</summary>
>
> Searched the web for `grid-universe grid-adventure-v1 GridState STEP_COST LavaEntity CoinEntity docs`
>
> Searched the web for `https://github.com/grid-universe/grid-universe`
>
> Searched the web for `https://grid-universe.github.io/grid-adventure-v1/`
>
> Searched the web for `https://grid-universe.github.io/grid-adventure-v1/game/entities/`
>
> </details>
</details>

In this level, “walking past lava” really means:

1. Step onto the lava tile at `(4, 1)`.
2. Survive the damage.
3. Move from lava to the exit at `(5, 1)`.

Lava does **not** directly reduce score. It reduces HP by `2` whenever the agent is processed on the same tile as lava; you lose only if HP reaches `0` [Entities docs](https://grid-universe.github.io/grid-adventure-v1/game/entities/). Score comes mainly from turn cost and collectibles: most non-final actions cost `-3`, the winning final action costs `0`, and each coin gives `+5` [Objectives & Rewards](https://grid-universe.github.io/grid-adventure-v1/game/objectives-and-rewards/).

For your action list:

```python
actions = [
    Action.DOWN,      # -3
    Action.RIGHT,     # -3
    Action.RIGHT,     # -3
    Action.UP,        # -3, pushes box up
    Action.RIGHT,     # -3, stand on coin
    Action.PICK_UP,   # -3 + 5 = +2
    Action.RIGHT,     # -3, step onto lava and take 2 damage
    Action.RIGHT,     # final winning action, 0 cost
]
```

Total: `-3 * 6 + 5 + -3 + 0 = -16`.

In general, given a `GridState`:

```python
print(gridstate.step_cost)
```

That tells you the per-action cost. The docs say `GridState.step_cost` is the reward cost applied to each non-terminal turn; Grid Adventure levels configure it as `3` [GridState docs](https://grid-universe.github.io/grid-adventure-v1/agent/gridstate/).

To know tile effects, inspect entities in the cell:

```python
from grid_adventure.entities import LavaEntity, CoinEntity, WallEntity, BoxEntity

for entity in gridstate.objects_at((x, y)):
    if isinstance(entity, LavaEntity):
        print("Lava: damages agent by 2 when occupied during an action")
    elif isinstance(entity, CoinEntity):
        print("Coin: +5 when PICK_UP is used on this tile")
```

And the most reliable way to discover exact effects is to simulate and compare before/after:

```python
before = gridstate
after = step(before, Action.RIGHT)

print("score delta:", after.score - before.score)
print("turn delta:", after.turn - before.turn)
print("win/lose:", after.win, after.lose)
```

So for planning: treat lava as a **health constraint**, not a score tile. Treat `step_cost` as the usual action penalty, coins as reward-bearing pickups, and terminal winning moves as special because they do not apply the turn cost.

> Are lava damages fixed for the whole game, or is it state-dependent?

For **Grid Adventure v1**, lava damage is fixed: **lava deals 2 HP damage** whenever the agent is on the lava tile during an action. The docs state this both in the object summary and the Lava section [Grid Adventure docs](https://grid-universe.github.io/grid-adventure-v1/) / [Entities](https://grid-universe.github.io/grid-adventure-v1/game/entities/).

But the *effect* can feel state-dependent because:

- If the agent has enough HP, it survives.
- If HP reaches `0`, the game ends.
- If the agent has a relevant powerup/effect, such as shield/immunity, lava may be ignored or reduced depending on the effect rules.
- If the action is terminal by loss, the normal turn cost may not be applied; the docs say an HP-to-0 action ends before the turn cost is applied [Objectives & Rewards](https://grid-universe.github.io/grid-adventure-v1/game/objectives-and-rewards/).

So: **the lava damage amount is fixed at 2 in this game variant**, but whether it matters depends on the current state: HP, statuses/powerups, and whether the action ends the game.
