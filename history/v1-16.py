"""
Passes A2 and B2 with expected effective performance.
"""

# Input states for Agent step function
from grid_adventure.grid import GridState
from grid_adventure.env import ImageObservation
from grid_adventure.constants import STEP_COST
from grid_adventure.entities import (
    AgentEntity,
    BoxEntity,
    CoinEntity,
    ExitEntity,
    GemEntity,
    KeyEntity,
    LavaEntity,
    LockedDoorEntity,
    PhasingPowerUpEntity,
    ShieldPowerUpEntity,
    SpeedPowerUpEntity,
    UnlockedDoorEntity,
    WallEntity,
)
from grid_adventure.movements import MOVEMENTS
from grid_adventure.objectives import OBJECTIVES
from grid_adventure.rendering import DEFAULT_ASSET_ROOT
from grid_universe.grid.entity import BaseEntity

# State steppers
from grid_adventure.step import Action
from grid_adventure.grid import step as grid_step

# Utility helpers
from collections import deque
import heapq
from itertools import count, permutations
from pathlib import Path
from time import perf_counter
import numpy as np
from PIL import Image

try:
    import psutil
except ImportError:  # Optional diagnostic dependency; never required to play.
    psutil = None

def optimistic_steps(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Lower bound on actions between two tiles with Speed always available."""
    return (abs(a[0] - b[0]) + abs(a[1] - b[1]) + 1) // 2


def h(agent: "Agent", state: GridState) -> int:
    """Best remaining gem order using cached wall-only path distances.

    The level cache runs one BFS from every original gem and exit.  Thus this
    function only scans the simulated state for dynamic positions and combines
    already-computed distances for at most 5! gem orders.
    """
    agent_position = None
    gem_positions: list[tuple[int, int]] = []

    for x in range(state.width):
        for y in range(state.height):
            position = (x, y)
            for entity in state.grid[x][y]:
                if isinstance(entity, AgentEntity):
                    agent_position = position
                elif isinstance(entity, GemEntity):
                    gem_positions.append(position)

    if agent_position is None or not agent._exit_positions:
        return 0

    def distance(source: tuple[int, int], target: tuple[int, int]) -> int | None:
        # BFS maps are keyed by their target, so the symmetric cardinal-grid
        # distance from source to target is a single lookup.
        return agent._wall_distances[target].get(source)

    if not gem_positions:
        exit_distances = [
            distance(agent_position, exit_position)
            for exit_position in agent._exit_positions
        ]
        reachable = [value for value in exit_distances if value is not None]
        return min(reachable, default=0)

    best_tour = float("inf")
    for order in permutations(gem_positions):
        first_leg = distance(agent_position, order[0])
        if first_leg is None:
            continue

        tour_cost = first_leg
        for index in range(len(order) - 1):
            leg = distance(order[index], order[index + 1])
            if leg is None:
                break
            tour_cost += leg
        else:
            exit_distances = [
                distance(order[-1], exit_position)
                for exit_position in agent._exit_positions
            ]
            reachable = [value for value in exit_distances if value is not None]
            if reachable:
                best_tour = min(best_tour, tour_cost + min(reachable))

    # An unreachable wall-only tour must not make A*'s estimate infinite.
    return 0 if best_tour == float("inf") else int(best_tour) + len(gem_positions)

class Agent:
    """
    Grid Adventure: PQueue agent variant.

    This class is the single public interface that Coursemology will import and
    interact with when evaluating your submission. You should extend the
    internals (add helper classes / functions in other files if you wish) but
    MUST preserve:

    1. The class name: Agent
    2. The public method: step(self, state: GridState | ImageObservation) -> Action

    High-level lifecycle per environment tick:
        state  --->  step(...)  --->  Action

    The "state" object type depends on the task:
    - Task 1: A fully structured GridState instance.
    - Task 2: An ImageObservation dictionary whose primary observation is an RGBA image
      plus limited structured metadata in the 'info' sub-dict. In this case you
      typically perform perception to build (or approximate) an internal
      structured representation before planning.
    - Task 3: Input state could be either a GridState instance 
      or an ImageObservation dictionary

    Constraints:
    - Keep per-step latency small (single CPU, 1.5 GB RAM). Avoid O(W*H) scans of
      the full grid every step.
    - Determinism helps reproducibility; seed your own RNG if you add any
      random components.

    You may add __init__ parameters (with defaults) if needed for your own
    development, but the grader will instantiate Agent() with no arguments.
    """

    def __init__(self):
        """Initialize your agent.

        Put all one-time setup here (e.g., hardcoded ML model weights, 
        precomputing heuristic tables). Keep it fast and memory-light 
        to respect platform limits.
        """
        # Level data is stable across an episode while GridState itself is a
        # fresh snapshot on every call to step().  Build this index once so
        # planner helpers can look up map objects without repeatedly walking
        # every cell in state.grid.
        self._level_key: tuple[int, int, int | None, int | None] | None = None
        # Reduced static level map.  These positions do not move during an
        # episode and will later be the input for wall-aware BFS distances.
        self._walls: set[tuple[int, int]] = set()
        self._initial_gems: set[tuple[int, int]] = set()
        # Coins are deliberately excluded from the A* state.  On otherwise
        # static levels, a small post-processing pass can still splice in
        # reward-positive detours without multiplying the search state space.
        self._coin_rewards: dict[tuple[int, int], int] = {}
        self._exit_positions: set[tuple[int, int]] = set()
        self._wall_distances: dict[
            tuple[int, int], dict[tuple[int, int], int]
        ] = {}
        self._gem_bits: dict[tuple[int, int], int] = {}
        self._static_fast_path = False
        # Static maps are deterministic, so retain the whole compact route
        # after the initial search instead of recomputing its suffix each turn.
        self._static_plan: deque[Action] = deque()
        # The power-up route handles static terrain, lava, and any number of
        # collectible power-ups. Moving boxes, doors, keys and coins still
        # use the reference simulator below.
        self._powerup_fast_path = False
        self._powerup_bits: dict[tuple[int, int], tuple[str, int]] = {}
        self._lava_positions: set[tuple[int, int]] = set()
        self._initial_health = 0
        self._powerup_plan: deque[Action] = deque()
        self._keydoor_fast_path = False
        self._key_bits: dict[tuple[int, int], int] = {}
        self._door_bits: dict[tuple[int, int], int] = {}
        self._keydoor_plan: deque[Action] = deque()
        # Mixed static maps combine keys/doors with hazards and power-ups.
        self._mixed_fast_path = False
        self._mixed_plan: deque[Action] = deque()
        # Box-only levels use a compact Sokoban state instead of cloning full
        # GridStates. The box tuple is canonicalized after every push.
        self._box_fast_path = False
        self._initial_boxes: tuple[tuple[int, int], ...] = ()
        self._box_plan: deque[Action] = deque()
        # A Grid Adventure episode is deterministic.  The generic simulator
        # can therefore retain a complete winning route instead of rediscovering
        # its suffix from every real successor state.
        self._fallback_plan: deque[Action] = deque()
        self._fallback_plan_next_turn: int | None = None
        # RSS is a coarse process-wide measurement, but it is cheap to sample
        # after a completed real action and catches unbounded cache growth.
        self._memory_process = psutil.Process() if psutil is not None else None
        self._rss_peak_bytes = 0
        self._width = 0
        self._height = 0

        direction_by_name = {
            "UP": (0, -1),
            "DOWN": (0, 1),
            "LEFT": (-1, 0),
            "RIGHT": (1, 0),
        }
        self._move_actions = [
            (action, direction_by_name[action.name])
            for action in Action
            if action.name in direction_by_name
        ]

        # Dynamic facts are tracked separately from the level blueprint.
        self._remaining_gems: set[tuple[int, int]] = set()
        self._agent_position: tuple[int, int] | None = None
        self._last_action: Action | None = None
        self._last_turn: int | None = None
        # These are updated once per real planning call and displayed by
        # info(); they never print during automated evaluation.
        self._last_search_stats: dict[str, int | float] = {}
        self._last_cache_stats: dict[str, int | float] = {}
        self._search_stats_history: list[dict[str, int | float]] = []

    def _cache_level(self, state: GridState) -> None:
        """Create or refresh the per-episode map index.

        A new episode normally begins at turn 0.  Dimensions, seed, and turn
        limit are also included as safeguards when an Agent is reused across
        levels.  This is deliberately the only full-grid scan for a level.
        """
        level_key = (state.width, state.height, state.seed, state.turn_limit)
        is_new_episode = (
            self._level_key != level_key
            or state.turn == 0
            or (self._last_turn is not None and state.turn < self._last_turn)
        )
        if not is_new_episode:
            self._last_turn = state.turn
            return

        cache_started = perf_counter()
        walls: set[tuple[int, int]] = set()
        gems: set[tuple[int, int]] = set()
        coin_rewards: dict[tuple[int, int], int] = {}
        exits: set[tuple[int, int]] = set()
        agent_position: tuple[int, int] | None = None
        static_only = True
        powerup_only = True
        keydoor_only = True
        box_only = True
        mixed_only = True
        lava: set[tuple[int, int]] = set()
        powerups: list[tuple[tuple[int, int], str]] = []
        keys: list[tuple[int, int]] = []
        doors: list[tuple[int, int]] = []
        boxes: list[tuple[int, int]] = []
        initial_health = 0
        for x in range(state.width):
            for y in range(state.height):
                for entity in state.grid[x][y]:
                    position = (x, y)
                    if isinstance(entity, WallEntity):
                        walls.add(position)
                    elif isinstance(entity, GemEntity):
                        gems.add(position)
                    elif isinstance(entity, ExitEntity):
                        exits.add(position)
                    elif isinstance(entity, AgentEntity):
                        agent_position = position
                        initial_health = entity.health.current_health
                    elif isinstance(entity, CoinEntity):
                        # Coins neither block movement nor are required for a
                        # win.  Leave them out of the compact state so a large
                        # optional-coin vault does not force full GridState
                        # simulation and serialization on every successor.
                        coin_rewards[position] = entity.rewardable.amount
                    elif isinstance(entity, KeyEntity):
                        static_only = False
                        powerup_only = False
                        box_only = False
                        keys.append(position)
                    elif isinstance(entity, LockedDoorEntity):
                        static_only = False
                        powerup_only = False
                        box_only = False
                        doors.append(position)
                    elif isinstance(entity, LavaEntity):
                        static_only = False
                        keydoor_only = False
                        box_only = False
                        lava.add(position)
                    elif isinstance(entity, PhasingPowerUpEntity):
                        static_only = False
                        keydoor_only = False
                        box_only = False
                        powerups.append((position, "ghost"))
                    elif isinstance(entity, SpeedPowerUpEntity):
                        static_only = False
                        keydoor_only = False
                        box_only = False
                        powerups.append((position, "boots"))
                    elif isinstance(entity, ShieldPowerUpEntity):
                        static_only = False
                        keydoor_only = False
                        box_only = False
                        powerups.append((position, "shield"))
                    elif isinstance(entity, BoxEntity):
                        static_only = False
                        powerup_only = False
                        keydoor_only = False
                        mixed_only = False
                        boxes.append(position)
                    else:
                        static_only = False
                        powerup_only = False
                        keydoor_only = False
                        box_only = False
                        mixed_only = False

        self._level_key = level_key
        self._walls = walls
        self._initial_gems = gems
        self._coin_rewards = coin_rewards
        self._exit_positions = exits
        self._remaining_gems = set(gems)
        self._agent_position = agent_position
        self._gem_bits = {
            position: 1 << index for index, position in enumerate(sorted(gems))
        }
        self._static_fast_path = static_only and len(self._move_actions) == 4
        self._powerup_fast_path = (
            powerup_only
            and len(self._move_actions) == 4
        )
        self._powerup_bits = {
            position: (kind, 1 << index)
            for index, (position, kind) in enumerate(powerups)
        }
        self._key_bits = {
            position: 1 << index for index, position in enumerate(sorted(keys))
        }
        self._door_bits = {
            position: 1 << index for index, position in enumerate(sorted(doors))
        }
        self._keydoor_fast_path = (
            keydoor_only
            and bool(keys or doors)
            and len(self._move_actions) == 4
        )
        self._mixed_fast_path = (
            mixed_only
            and bool(keys or doors)
            and bool(powerups or lava)
            and len(self._move_actions) == 4
        )
        self._box_fast_path = (
            box_only and bool(boxes) and len(self._move_actions) == 4
        )
        self._initial_boxes = tuple(sorted(boxes))
        self._lava_positions = lava
        self._initial_health = initial_health
        self._width = state.width
        self._height = state.height
        targets = gems | exits
        self._wall_distances = {
            target: self._bfs_wall_distances(target, state.width, state.height)
            for target in targets
        }
        self._last_cache_stats = {
            "targets": len(targets),
            "reachable_tiles": sum(len(distances) for distances in self._wall_distances.values()),
            "distance_entries": sum(
                len(distances) for distances in self._wall_distances.values()
            ),
            "build_ms": round((perf_counter() - cache_started) * 1000, 2),
        }
        self._last_action = None
        self._static_plan.clear()
        self._powerup_plan.clear()
        self._keydoor_plan.clear()
        self._mixed_plan.clear()
        self._box_plan.clear()
        self._fallback_plan.clear()
        self._fallback_plan_next_turn = None
        self._last_turn = state.turn
        self._search_stats_history = []

    def _bfs_wall_distances(
        self, source: tuple[int, int], width: int, height: int
    ) -> dict[tuple[int, int], int]:
        """Return shortest cardinal walking distances on the static wall map."""
        distances = {source: 0}
        frontier = deque([source])

        while frontier:
            x, y = frontier.popleft()
            next_distance = distances[(x, y)] + 1
            for position in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                nx, ny = position
                if (
                    0 <= nx < width
                    and 0 <= ny < height
                    and position not in self._walls
                    and position not in distances
                ):
                    distances[position] = next_distance
                    frontier.append(position)

        return distances

    def _static_heuristic(self, position: tuple[int, int], remaining_mask: int) -> int:
        """Cached wall-distance gem-order bound for a compact static state."""
        remaining_gems = [
            gem for gem, bit in self._gem_bits.items() if remaining_mask & bit
        ]

        def distance(source: tuple[int, int], target: tuple[int, int]) -> int | None:
            return self._wall_distances[target].get(source)

        if not remaining_gems:
            reachable = [
                distance(position, exit_position)
                for exit_position in self._exit_positions
            ]
            return min((value for value in reachable if value is not None), default=0)

        best_tour = float("inf")
        for order in permutations(remaining_gems):
            first_leg = distance(position, order[0])
            if first_leg is None:
                continue

            tour_cost = first_leg
            for index in range(len(order) - 1):
                leg = distance(order[index], order[index + 1])
                if leg is None:
                    break
                tour_cost += leg
            else:
                exit_distances = [
                    distance(order[-1], exit_position)
                    for exit_position in self._exit_positions
                ]
                reachable = [value for value in exit_distances if value is not None]
                if reachable:
                    best_tour = min(best_tour, tour_cost + min(reachable))

        return 0 if best_tour == float("inf") else int(best_tour) + len(remaining_gems)

    def _static_fast_plan(
        self,
    ) -> tuple[deque[Action], dict[str, int | float], int, int]:
        """Plan a walls/gems/exits-only level without constructing GridStates."""
        stats: dict[str, int | float] = {
            "popped": 0,
            "successors": 0,
            "enqueued": 0,
            "heuristic_calls": 0,
            "max_frontier": 1,
            "grid_step_ms": 0.0,
            "key_ms": 0.0,
            "heuristic_ms": 0.0,
        }
        if self._agent_position is None:
            return deque(), stats, 0, 0

        def estimate(position: tuple[int, int], mask: int) -> int:
            started = perf_counter()
            stats["heuristic_calls"] += 1
            value = self._static_heuristic(position, mask)
            stats["heuristic_ms"] += (perf_counter() - started) * 1000
            return value

        remaining_mask = sum(
            self._gem_bits[position]
            for position in self._remaining_gems
            if position in self._gem_bits
        )
        tie_breaker = count()
        initial_state = (self._agent_position, remaining_mask)
        frontier = [
            (estimate(*initial_state), next(tie_breaker), *initial_state, 0)
        ]
        visited = {initial_state}
        parents: dict[
            tuple[tuple[int, int], int], tuple[tuple[tuple[int, int], int], Action]
        ] = {}

        def reconstruct_plan(
            goal: tuple[tuple[int, int], int],
        ) -> deque[Action]:
            plan: deque[Action] = deque()
            while goal != initial_state:
                parent, action = parents[goal]
                plan.appendleft(action)
                goal = parent
            return plan

        while frontier:
            stats["popped"] += 1
            _, _, position, mask, depth = heapq.heappop(frontier)
            if mask == 0 and position in self._exit_positions:
                return (
                    reconstruct_plan((position, mask)),
                    stats,
                    len(visited),
                    len(frontier),
                )

            if mask & self._gem_bits.get(position, 0):
                stats["successors"] += 1
                next_mask = mask & ~self._gem_bits[position]
                key = (position, next_mask)
                if key not in visited:
                    visited.add(key)
                    parents[key] = ((position, mask), Action.PICK_UP)
                    priority = depth + 1 + estimate(position, next_mask)
                    heapq.heappush(
                        frontier,
                        (priority, next(tie_breaker), position, next_mask, depth + 1),
                    )
                    stats["enqueued"] += 1
                    stats["max_frontier"] = max(stats["max_frontier"], len(frontier))

            x, y = position
            for action, (dx, dy) in self._move_actions:
                stats["successors"] += 1
                next_position = (x + dx, y + dy)
                nx, ny = next_position
                if (
                    not (0 <= nx < self._width and 0 <= ny < self._height)
                    or next_position in self._walls
                ):
                    continue

                key = (next_position, mask)
                if key in visited:
                    continue
                visited.add(key)
                parents[key] = ((position, mask), action)
                priority = depth + 1 + estimate(next_position, mask)
                heapq.heappush(
                    frontier,
                    (priority, next(tie_breaker), next_position, mask, depth + 1),
                )
                stats["enqueued"] += 1
                stats["max_frontier"] = max(stats["max_frontier"], len(frontier))

        return deque(), stats, len(visited), len(frontier)

    def _shortest_move_actions(
        self, source: tuple[int, int], target: tuple[int, int]
    ) -> list[Action] | None:
        """Reconstruct one wall-only shortest path for a coin detour."""
        if source == target:
            return []

        frontier = deque([source])
        parents: dict[tuple[int, int], tuple[tuple[int, int], Action]] = {}
        seen = {source}
        while frontier:
            x, y = frontier.popleft()
            for action, (dx, dy) in self._move_actions:
                position = (x + dx, y + dy)
                nx, ny = position
                if (
                    not (0 <= nx < self._width and 0 <= ny < self._height)
                    or position in self._walls
                    or position in seen
                ):
                    continue
                seen.add(position)
                parents[position] = ((x, y), action)
                if position == target:
                    path: list[Action] = []
                    while position != source:
                        position, action = parents[position]
                        path.append(action)
                    path.reverse()
                    return path
                frontier.append(position)
        return None

    def _coin_detour_plan(self, plan: deque[Action]) -> deque[Action]:
        """Replace a static route with a bounded, reward-positive coin tour.

        Coins stay out of the main A* state.  Instead, consider only the
        twelve coins with the smallest start-to-coin-to-exit detour, then use
        subset dynamic programming to find their best order.  The limit keeps
        this post-pass at most ``2**12 * 12**2`` inexpensive distance lookups.
        """
        move_actions = {action for action, _ in self._move_actions}
        if (
            not self._coin_rewards
            or self._agent_position is None
            or self._initial_gems
            or any(action not in move_actions for action in plan)
        ):
            return plan

        baseline = list(plan)
        position = self._agent_position
        assert position is not None
        for action in baseline:
            dx, dy = dict(self._move_actions)[action]
            position = (position[0] + dx, position[1] + dy)
        exit_position = position
        if exit_position not in self._exit_positions:
            return plan

        distance_maps = {
            point: self._bfs_wall_distances(point, self._width, self._height)
            for point in set(self._coin_rewards) | {self._agent_position, exit_position}
        }
        baseline_moves = len(baseline)
        ranked_coins = sorted(
            (
                distance_maps[self._agent_position].get(coin, float("inf"))
                + distance_maps[coin].get(exit_position, float("inf"))
                - baseline_moves,
                coin,
            )
            for coin in self._coin_rewards
        )
        coins = [coin for detour, coin in ranked_coins[:12] if detour != float("inf")]
        if not coins:
            return plan

        # ``cost`` counts actions, including one explicit PICK_UP for each
        # selected coin.  The score comparison below uses the actual reward
        # rather than assuming every coin has the same value.
        cost: dict[tuple[int, int], int] = {(0, -1): 0}
        parents: dict[tuple[int, int], tuple[int, int]] = {}
        for mask in range(1 << len(coins)):
            for last_index in range(-1, len(coins)):
                state = (mask, last_index)
                if state not in cost:
                    continue
                source = self._agent_position if last_index == -1 else coins[last_index]
                for next_index, coin in enumerate(coins):
                    bit = 1 << next_index
                    if mask & bit:
                        continue
                    distance = distance_maps[source].get(coin)
                    if distance is None:
                        continue
                    next_state = (mask | bit, next_index)
                    next_cost = cost[state] + distance + 1  # movement + PICK_UP
                    if next_cost < cost.get(next_state, float("inf")):
                        cost[next_state] = next_cost
                        parents[next_state] = state

        best_state: tuple[int, int] | None = None
        best_score = -STEP_COST * baseline_moves
        for (mask, last_index), action_cost in cost.items():
            source = self._agent_position if last_index == -1 else coins[last_index]
            final_distance = distance_maps[source].get(exit_position)
            if final_distance is None:
                continue
            reward = sum(
                self._coin_rewards[coins[index]]
                for index in range(len(coins))
                if mask & (1 << index)
            )
            score = reward - STEP_COST * (action_cost + final_distance)
            if score > best_score:
                best_score = score
                best_state = (mask, last_index)

        if best_state is None:
            return plan
        order: list[tuple[int, int]] = []
        state = best_state
        while state != (0, -1):
            order.append(coins[state[1]])
            state = parents[state]
        order.reverse()

        result: deque[Action] = deque()
        picked: set[tuple[int, int]] = set()
        position = self._agent_position
        for target in [*order, exit_position]:
            segment = self._shortest_move_actions(position, target)
            if segment is None:
                return plan
            for action in segment:
                result.append(action)
                dx, dy = dict(self._move_actions)[action]
                position = (position[0] + dx, position[1] + dy)
                if position in self._exit_positions and target != exit_position:
                    # Reaching an exit ends a no-gem level immediately, so it
                    # cannot be used as an intermediate corridor tile.
                    return plan
                if position in self._coin_rewards and position not in picked:
                    result.append(Action.PICK_UP)
                    picked.add(position)

        # Incidental coins can only improve a valid route: each adds reward
        # greater than its one-action pickup cost.
        if position != exit_position:
            return plan
        return result

    def _powerup_fast_plan(
        self,
    ) -> tuple[deque[Action], dict[str, int | float], int, int]:
        """Plan static terrain with lava and arbitrary collectible power-ups.

        This is intentionally a compact model rather than an approximation of
        ``GridState``.  It preserves the public power-up mechanics needed by
        the introductory levels: explicit PICK_UP, five-turn ghost/boots
        effects, two boots substeps, and shield-protected lava.  The fast path
        is disabled at cache time for mechanics this model does not represent.
        """
        stats: dict[str, int | float] = {
            "popped": 0,
            "successors": 0,
            "enqueued": 0,
            "heuristic_calls": 0,
            "max_frontier": 1,
            "grid_step_ms": 0.0,
            "key_ms": 0.0,
            "heuristic_ms": 0.0,
        }
        if self._agent_position is None:
            return deque(), stats, 0, 0

        initial_gems = sum(self._gem_bits.values())
        initial_powerups = sum(bit for _, bit in self._powerup_bits.values())
        # position, gems, uncollected powerups, ghost turns, boots turns,
        # shield charges, health
        initial = (
            self._agent_position,
            initial_gems,
            initial_powerups,
            0,
            0,
            0,
            self._initial_health,
        )

        def estimate(node: tuple[object, ...]) -> int:
            """Admissible action bound even if boots are acquired later."""
            started = perf_counter()
            stats["heuristic_calls"] += 1
            position = node[0]
            assert isinstance(position, tuple)
            value = min(
                (optimistic_steps(position, exit_position)
                 for exit_position in self._exit_positions),
                default=0,
            )
            stats["heuristic_ms"] += (perf_counter() - started) * 1000
            return value

        # Store predecessors rather than an action list per successor.
        parents: dict[tuple[object, ...], tuple[tuple[object, ...], Action]] = {}
        best_cost = {initial: 0}
        tie_breaker = count()
        frontier = [(estimate(initial), next(tie_breaker), 0, initial)]

        def finish(node: tuple[object, ...]) -> deque[Action]:
            actions: deque[Action] = deque()
            while node in parents:
                node, action = parents[node]
                actions.appendleft(action)
            return actions

        while frontier:
            _, _, depth, current = heapq.heappop(frontier)
            if depth != best_cost.get(current):
                continue
            stats["popped"] += 1
            position, gems, powerups, ghost, boots, shield, health = current
            assert isinstance(position, tuple)
            assert all(isinstance(value, int) for value in current[1:])

            if gems == 0 and position in self._exit_positions:
                return finish(current), stats, len(best_cost), len(frontier)

            successors: list[tuple[Action, tuple[object, ...]]] = []

            # Pick-up is a separate action.  A just-collected timed effect is
            # not decremented until a later turn, matching status_tick_system.
            item = self._powerup_bits.get(position)
            gem_bit = self._gem_bits.get(position, 0)
            if (item is not None and powerups & item[1]) or gems & gem_bit:
                next_gems = gems & ~gem_bit
                next_powerups = powerups
                next_ghost, next_boots, next_shield = ghost, boots, shield
                if item is not None and powerups & item[1]:
                    kind, bit = item
                    next_powerups &= ~bit
                    if kind == "ghost":
                        next_ghost = 5
                    elif kind == "boots":
                        next_boots = 5
                    else:
                        # Unlike timed effects, every shield remains active
                        # until all of its uses are spent. Multiple pickups
                        # therefore stack their five absorbed hits.
                        next_shield += 5
                successors.append((
                    Action.PICK_UP,
                    (position, next_gems, next_powerups, next_ghost,
                     next_boots, next_shield, health),
                ))

            for action, (dx, dy) in self._move_actions:
                stats["successors"] += 1
                next_position = position
                crossed_lava = False
                # Effects apply for the entire action using their value at its
                # start.  Boots make two ordinary movement substeps.
                for _ in range(2 if boots > 0 else 1):
                    candidate = (next_position[0] + dx, next_position[1] + dy)
                    cx, cy = candidate
                    if not (0 <= cx < self._width and 0 <= cy < self._height):
                        break
                    if candidate in self._walls and ghost == 0:
                        break
                    next_position = candidate
                    crossed_lava = crossed_lava or candidate in self._lava_positions

                next_health = health
                next_shield = shield
                # A stationary failed move cannot newly contact lava.  Lava
                # deals damage once per action, even during a boots move.
                if crossed_lava:
                    if next_shield > 0:
                        next_shield -= 1
                    elif ghost == 0:
                        next_health -= 2
                if next_health <= 0:
                    continue
                successors.append((
                    action,
                    (next_position, gems, powerups, max(0, ghost - 1),
                     max(0, boots - 1), next_shield, next_health),
                ))

            for action, successor in successors:
                stats["successors"] += action is Action.PICK_UP
                new_depth = depth + 1
                if new_depth >= best_cost.get(successor, float("inf")):
                    continue
                best_cost[successor] = new_depth
                parents[successor] = (current, action)
                priority = new_depth + estimate(successor)
                heapq.heappush(
                    frontier, (priority, next(tie_breaker), new_depth, successor)
                )
                stats["enqueued"] += 1
                stats["max_frontier"] = max(stats["max_frontier"], len(frontier))

        return deque(), stats, len(best_cost), len(frontier)

    def _mixed_fast_plan(
        self,
    ) -> tuple[deque[Action], dict[str, int | float], int, int]:
        """Plan static keys, doors, lava, and power-ups in one compact state."""
        stats: dict[str, int | float] = {
            "popped": 0, "successors": 0, "enqueued": 0,
            "heuristic_calls": 0, "max_frontier": 1,
            "grid_step_ms": 0.0, "key_ms": 0.0, "heuristic_ms": 0.0,
        }
        if self._agent_position is None:
            return deque(), stats, 0, 0

        # position, gems, uncollected power-ups, ghost turns, boots turns,
        # shield uses, health, uncollected keys, opened doors, held keys
        initial = (
            self._agent_position,
            sum(self._gem_bits.values()),
            sum(bit for _, bit in self._powerup_bits.values()),
            0, 0, 0, self._initial_health,
            sum(self._key_bits.values()), 0, 0,
        )

        def estimate(node: tuple[object, ...]) -> int:
            # Doors, hazards, and boxes are ignored in this lower bound.
            started = perf_counter()
            stats["heuristic_calls"] += 1
            position, gems = node[0], node[1]
            assert isinstance(position, tuple) and isinstance(gems, int)
            value = self._static_heuristic(position, gems)
            stats["heuristic_ms"] += (perf_counter() - started) * 1000
            return value

        parents: dict[tuple[object, ...], tuple[tuple[object, ...], Action]] = {}
        best_cost = {initial: 0}
        tie_breaker = count()
        frontier = [(estimate(initial), next(tie_breaker), 0, initial)]

        def finish(node: tuple[object, ...]) -> deque[Action]:
            actions: deque[Action] = deque()
            while node in parents:
                node, action = parents[node]
                actions.appendleft(action)
            return actions

        while frontier:
            _, _, depth, current = heapq.heappop(frontier)
            if depth != best_cost.get(current):
                continue
            stats["popped"] += 1
            (
                position, gems, powerups, ghost, boots, shield, health,
                keys, opened_doors, held_keys,
            ) = current
            assert isinstance(position, tuple)
            assert all(isinstance(value, int) for value in current[1:])

            if gems == 0 and position in self._exit_positions:
                return finish(current), stats, len(best_cost), len(frontier)

            successors: list[tuple[Action, tuple[object, ...]]] = []
            item = self._powerup_bits.get(position)
            gem_bit = self._gem_bits.get(position, 0)
            key_bit = self._key_bits.get(position, 0)
            if (
                (item is not None and powerups & item[1])
                or gems & gem_bit
                or keys & key_bit
            ):
                # Existing timed effects tick on every action, while a newly
                # collected effect begins with its full duration.
                next_ghost = max(0, ghost - 1)
                next_boots = max(0, boots - 1)
                next_shield = shield
                next_powerups = powerups
                if item is not None and powerups & item[1]:
                    kind, bit = item
                    next_powerups &= ~bit
                    if kind == "ghost":
                        next_ghost = 5
                    elif kind == "boots":
                        next_boots = 5
                    else:
                        next_shield += 5
                successors.append((
                    Action.PICK_UP,
                    (
                        position, gems & ~gem_bit, next_powerups,
                        next_ghost, next_boots, next_shield, health,
                        keys & ~key_bit, opened_doors,
                        held_keys + bool(keys & key_bit),
                    ),
                ))

            if held_keys:
                next_opened = opened_doors
                next_held = held_keys
                x, y = position
                for door_position in (
                    position, (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)
                ):
                    door_bit = self._door_bits.get(door_position, 0)
                    if door_bit and not (next_opened & door_bit) and next_held:
                        next_opened |= door_bit
                        next_held -= 1
                if next_opened != opened_doors:
                    successors.append((
                        Action.USE_KEY,
                        (
                            position, gems, powerups, max(0, ghost - 1),
                            max(0, boots - 1), shield, health, keys,
                            next_opened, next_held,
                        ),
                    ))

            for action, (dx, dy) in self._move_actions:
                stats["successors"] += 1
                next_position = position
                crossed_lava = False
                for _ in range(2 if boots > 0 else 1):
                    candidate = (next_position[0] + dx, next_position[1] + dy)
                    cx, cy = candidate
                    if not (0 <= cx < self._width and 0 <= cy < self._height):
                        break
                    door_bit = self._door_bits.get(candidate, 0)
                    if ghost == 0 and (
                        candidate in self._walls
                        or (door_bit and not (opened_doors & door_bit))
                    ):
                        break
                    next_position = candidate
                    crossed_lava = crossed_lava or candidate in self._lava_positions

                next_health = health
                next_shield = shield
                if crossed_lava:
                    if next_shield > 0:
                        next_shield -= 1
                    elif ghost == 0:
                        next_health -= 2
                if next_health <= 0:
                    continue
                successors.append((
                    action,
                    (
                        next_position, gems, powerups, max(0, ghost - 1),
                        max(0, boots - 1), next_shield, next_health,
                        keys, opened_doors, held_keys,
                    ),
                ))

            for action, successor in successors:
                stats["successors"] += action in (Action.PICK_UP, Action.USE_KEY)
                new_depth = depth + 1
                if new_depth >= best_cost.get(successor, float("inf")):
                    continue
                best_cost[successor] = new_depth
                parents[successor] = (current, action)
                heapq.heappush(
                    frontier,
                    (new_depth + estimate(successor), next(tie_breaker), new_depth, successor),
                )
                stats["enqueued"] += 1
                stats["max_frontier"] = max(stats["max_frontier"], len(frontier))

        return deque(), stats, len(best_cost), len(frontier)

    def _keydoor_fast_plan(
        self,
    ) -> tuple[deque[Action], dict[str, int | float], int, int]:
        """Plan static key-and-door maps without constructing GridStates."""
        stats: dict[str, int | float] = {
            "popped": 0,
            "successors": 0,
            "enqueued": 0,
            "heuristic_calls": 0,
            "max_frontier": 1,
            "grid_step_ms": 0.0,
            "key_ms": 0.0,
            "heuristic_ms": 0.0,
        }
        if self._agent_position is None:
            return deque(), stats, 0, 0

        # position, remaining gems, remaining keys, opened doors, held keys
        initial = (
            self._agent_position,
            sum(self._gem_bits.values()),
            sum(self._key_bits.values()),
            0,
            0,
        )

        def estimate(node: tuple[object, ...]) -> int:
            # Treat still-locked doors as open in the lower bound.  This is
            # admissible and reuses the existing cached wall-only distances.
            started = perf_counter()
            stats["heuristic_calls"] += 1
            position, gems, _, _, _ = node
            assert isinstance(position, tuple) and isinstance(gems, int)
            value = self._static_heuristic(position, gems)
            stats["heuristic_ms"] += (perf_counter() - started) * 1000
            return value

        parents: dict[tuple[object, ...], tuple[tuple[object, ...], Action]] = {}
        best_cost = {initial: 0}
        tie_breaker = count()
        frontier = [(estimate(initial), next(tie_breaker), 0, initial)]

        def finish(node: tuple[object, ...]) -> deque[Action]:
            actions: deque[Action] = deque()
            while node in parents:
                node, action = parents[node]
                actions.appendleft(action)
            return actions

        while frontier:
            _, _, depth, current = heapq.heappop(frontier)
            if depth != best_cost.get(current):
                continue
            stats["popped"] += 1
            position, gems, keys, opened_doors, held_keys = current
            assert isinstance(position, tuple)
            assert all(isinstance(value, int) for value in current[1:])

            if gems == 0 and position in self._exit_positions:
                return finish(current), stats, len(best_cost), len(frontier)

            successors: list[tuple[Action, tuple[object, ...]]] = []
            gem_bit = self._gem_bits.get(position, 0)
            key_bit = self._key_bits.get(position, 0)
            if gems & gem_bit or keys & key_bit:
                successors.append((
                    Action.PICK_UP,
                    (
                        position,
                        gems & ~gem_bit,
                        keys & ~key_bit,
                        opened_doors,
                        held_keys + bool(keys & key_bit),
                    ),
                ))

            # USE_KEY opens each locked entity at the current tile and its
            # four neighbours, in the simulator's documented order.
            if held_keys:
                next_opened = opened_doors
                next_held = held_keys
                x, y = position
                for door_position in (
                    position, (x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)
                ):
                    door_bit = self._door_bits.get(door_position, 0)
                    if door_bit and not (next_opened & door_bit) and next_held:
                        next_opened |= door_bit
                        next_held -= 1
                if next_opened != opened_doors:
                    successors.append((
                        Action.USE_KEY,
                        (position, gems, keys, next_opened, next_held),
                    ))

            x, y = position
            for action, (dx, dy) in self._move_actions:
                stats["successors"] += 1
                next_position = (x + dx, y + dy)
                nx, ny = next_position
                door_bit = self._door_bits.get(next_position, 0)
                if (
                    not (0 <= nx < self._width and 0 <= ny < self._height)
                    or next_position in self._walls
                    or (door_bit and not (opened_doors & door_bit))
                ):
                    continue
                successors.append((
                    action,
                    (next_position, gems, keys, opened_doors, held_keys),
                ))

            for action, successor in successors:
                stats["successors"] += action in (Action.PICK_UP, Action.USE_KEY)
                new_depth = depth + 1
                if new_depth >= best_cost.get(successor, float("inf")):
                    continue
                best_cost[successor] = new_depth
                parents[successor] = (current, action)
                heapq.heappush(
                    frontier,
                    (new_depth + estimate(successor), next(tie_breaker), new_depth, successor),
                )
                stats["enqueued"] += 1
                stats["max_frontier"] = max(stats["max_frontier"], len(frontier))

        return deque(), stats, len(best_cost), len(frontier)

    def _box_fast_plan(
        self,
    ) -> tuple[deque[Action], dict[str, int | float], int, int]:
        """Plan static box-pushing levels without cloning ``GridState``.

        Boxes are indistinguishable, so their sorted positions form the
        Sokoban portion of the state.  Ordinary movement and successful pushes
        each cost one action, exactly as the engine's push and move systems do.
        """
        stats: dict[str, int | float] = {
            "popped": 0,
            "successors": 0,
            "enqueued": 0,
            "heuristic_calls": 0,
            "max_frontier": 1,
            "grid_step_ms": 0.0,
            "key_ms": 0.0,
            "heuristic_ms": 0.0,
        }
        if self._agent_position is None:
            return deque(), stats, 0, 0

        # position, sorted box positions, remaining gems
        initial = (
            self._agent_position,
            self._initial_boxes,
            sum(self._gem_bits.values()),
        )

        def estimate(node: tuple[object, ...]) -> int:
            # Ignore boxes in the lower bound; static wall distances remain
            # admissible while still guiding the agent toward required goals.
            started = perf_counter()
            stats["heuristic_calls"] += 1
            position, _, gems = node
            assert isinstance(position, tuple) and isinstance(gems, int)
            value = self._static_heuristic(position, gems)
            stats["heuristic_ms"] += (perf_counter() - started) * 1000
            return value

        parents: dict[tuple[object, ...], tuple[tuple[object, ...], Action]] = {}
        best_cost = {initial: 0}
        tie_breaker = count()
        frontier = [(estimate(initial), next(tie_breaker), 0, initial)]

        def finish(node: tuple[object, ...]) -> deque[Action]:
            actions: deque[Action] = deque()
            while node in parents:
                node, action = parents[node]
                actions.appendleft(action)
            return actions

        while frontier:
            _, _, depth, current = heapq.heappop(frontier)
            if depth != best_cost.get(current):
                continue
            stats["popped"] += 1
            position, boxes, gems = current
            assert isinstance(position, tuple) and isinstance(boxes, tuple)
            assert isinstance(gems, int)

            if gems == 0 and position in self._exit_positions:
                return finish(current), stats, len(best_cost), len(frontier)

            successors: list[tuple[Action, tuple[object, ...]]] = []
            gem_bit = self._gem_bits.get(position, 0)
            if gems & gem_bit:
                successors.append((
                    Action.PICK_UP, (position, boxes, gems & ~gem_bit)
                ))

            box_set = set(boxes)
            x, y = position
            for action, (dx, dy) in self._move_actions:
                stats["successors"] += 1
                next_position = (x + dx, y + dy)
                nx, ny = next_position
                if (
                    not (0 <= nx < self._width and 0 <= ny < self._height)
                    or next_position in self._walls
                ):
                    continue

                next_boxes = boxes
                if next_position in box_set:
                    pushed_to = (nx + dx, ny + dy)
                    px, py = pushed_to
                    if (
                        not (0 <= px < self._width and 0 <= py < self._height)
                        or pushed_to in self._walls
                        or pushed_to in box_set
                    ):
                        continue
                    next_boxes = tuple(sorted(
                        pushed_to if box == next_position else box
                        for box in boxes
                    ))
                successors.append((action, (next_position, next_boxes, gems)))

            for action, successor in successors:
                stats["successors"] += action is Action.PICK_UP
                new_depth = depth + 1
                if new_depth >= best_cost.get(successor, float("inf")):
                    continue
                best_cost[successor] = new_depth
                parents[successor] = (current, action)
                heapq.heappush(
                    frontier,
                    (new_depth + estimate(successor), next(tie_breaker), new_depth, successor),
                )
                stats["enqueued"] += 1
                stats["max_frontier"] = max(stats["max_frontier"], len(frontier))

        return deque(), stats, len(best_cost), len(frontier)

    def locations(self, entity_type: type[BaseEntity]) -> frozenset[tuple[int, int]]:
        """Return positions from the reduced cached map without scanning the grid."""
        if entity_type is GemEntity:
            return frozenset(self._remaining_gems)
        if entity_type is WallEntity:
            return frozenset(self._walls)
        if entity_type is ExitEntity:
            return frozenset(self._exit_positions)
        return frozenset()

    def _sync_dynamic_cache(self, state: GridState) -> None:
        """Update the moving agent and picked-up gems using only nearby cells."""
        if self._agent_position is None:
            return

        old_agent_position = self._agent_position
        # The largest single-turn displacement is two cells (Speed power-up),
        # so this examines at most 25 cells rather than the whole level.
        x0, y0 = old_agent_position
        for x in range(max(0, x0 - 2), min(state.width, x0 + 3)):
            for y in range(max(0, y0 - 2), min(state.height, y0 + 3)):
                if any(isinstance(entity, AgentEntity) for entity in state.objects_at((x, y))):
                    self._agent_position = (x, y)
                    break
            else:
                continue
            break

        # Pick-up is the only action that can remove a gem and it happens at
        # the agent's pre-action cell.  Verify just that one cell.
        if self._last_action is Action.PICK_UP and old_agent_position in self._remaining_gems:
            if not any(isinstance(entity, GemEntity) for entity in state.objects_at(old_agent_position)):
                self._remaining_gems.remove(old_agent_position)

    def step(self, state: GridState | ImageObservation) -> Action:
        """Return the next action given the current environment state.

        Parameters
        ----------
        state : GridState | ImageObservation
            - If a GridState instance (Tasks 1 and 3): you have direct, structured
              access to grid, entities, objective message, score, etc.
            - If an ImageObservation dictionary (Tasks 2 and 3): contains 'image' (HxWx4 RGBA uint8)
              plus 'info' sub-dictionary (agent stats, partial config, message).
              You likely need to parse the image into an internal representation.

        Returns
        -------
        Action
            A valid action from the Action enum. Must always return a member;
            never return None.
        """

        if not isinstance(state, GridState):
            state = self.parse(state)

        self._cache_level(state)
        self._sync_dynamic_cache(state)

        if self._static_fast_path:
            search_started = perf_counter()
            if not self._static_plan:
                (
                    self._static_plan,
                    search_stats,
                    visited_count,
                    frontier_count,
                ) = self._static_fast_plan()
                self._static_plan = self._coin_detour_plan(self._static_plan)
            else:
                search_stats = {
                    "popped": 0,
                    "successors": 0,
                    "enqueued": 0,
                    "heuristic_calls": 0,
                    "max_frontier": 0,
                    "grid_step_ms": 0.0,
                    "key_ms": 0.0,
                    "heuristic_ms": 0.0,
                    "reused_plan": 1,
                }
                visited_count = 0
                frontier_count = len(self._static_plan)
            action = self._static_plan.popleft() if self._static_plan else Action.WAIT
            self._record_search_stats(
                search_started, search_stats, visited_count, frontier_count
            )
            self._last_action = action
            return action

        if self._mixed_fast_path:
            search_started = perf_counter()
            if not self._mixed_plan:
                (
                    self._mixed_plan,
                    search_stats,
                    visited_count,
                    frontier_count,
                ) = self._mixed_fast_plan()
            else:
                search_stats = {
                    "popped": 0, "successors": 0, "enqueued": 0,
                    "heuristic_calls": 0, "max_frontier": 0,
                    "grid_step_ms": 0.0, "key_ms": 0.0,
                    "heuristic_ms": 0.0, "reused_plan": 1,
                }
                visited_count = 0
                frontier_count = len(self._mixed_plan)
            action = self._mixed_plan.popleft() if self._mixed_plan else Action.WAIT
            self._record_search_stats(
                search_started, search_stats, visited_count, frontier_count
            )
            self._last_action = action
            return action

        if self._keydoor_fast_path:
            search_started = perf_counter()
            if not self._keydoor_plan:
                (
                    self._keydoor_plan,
                    search_stats,
                    visited_count,
                    frontier_count,
                ) = self._keydoor_fast_plan()
            else:
                search_stats = {
                    "popped": 0,
                    "successors": 0,
                    "enqueued": 0,
                    "heuristic_calls": 0,
                    "max_frontier": 0,
                    "grid_step_ms": 0.0,
                    "key_ms": 0.0,
                    "heuristic_ms": 0.0,
                    "reused_plan": 1,
                }
                visited_count = 0
                frontier_count = len(self._keydoor_plan)
            action = self._keydoor_plan.popleft() if self._keydoor_plan else Action.WAIT
            self._record_search_stats(
                search_started, search_stats, visited_count, frontier_count
            )
            self._last_action = action
            return action

        if self._powerup_fast_path:
            search_started = perf_counter()
            if not self._powerup_plan:
                (
                    self._powerup_plan,
                    search_stats,
                    visited_count,
                    frontier_count,
                ) = self._powerup_fast_plan()
            else:
                search_stats = {
                    "popped": 0,
                    "successors": 0,
                    "enqueued": 0,
                    "heuristic_calls": 0,
                    "max_frontier": 0,
                    "grid_step_ms": 0.0,
                    "key_ms": 0.0,
                    "heuristic_ms": 0.0,
                    "reused_plan": 1,
                }
                visited_count = 0
                frontier_count = len(self._powerup_plan)
            action = self._powerup_plan.popleft() if self._powerup_plan else Action.WAIT
            self._record_search_stats(
                search_started, search_stats, visited_count, frontier_count
            )
            self._last_action = action
            return action

        if self._box_fast_path:
            search_started = perf_counter()
            if not self._box_plan:
                (
                    self._box_plan,
                    search_stats,
                    visited_count,
                    frontier_count,
                ) = self._box_fast_plan()
            else:
                search_stats = {
                    "popped": 0,
                    "successors": 0,
                    "enqueued": 0,
                    "heuristic_calls": 0,
                    "max_frontier": 0,
                    "grid_step_ms": 0.0,
                    "key_ms": 0.0,
                    "heuristic_ms": 0.0,
                    "reused_plan": 1,
                }
                visited_count = 0
                frontier_count = len(self._box_plan)
            action = self._box_plan.popleft() if self._box_plan else Action.WAIT
            self._record_search_stats(
                search_started, search_stats, visited_count, frontier_count
            )
            self._last_action = action
            return action

        # A cached route is valid only for the immediately following turn.
        # This retains the normal search behavior if Grid Play supplies a
        # reset, skipped, or otherwise unrelated state.
        if self._fallback_plan and state.turn == self._fallback_plan_next_turn:
            search_started = perf_counter()
            action = self._fallback_plan.popleft()
            self._fallback_plan_next_turn = state.turn + 1
            self._record_search_stats(
                search_started,
                {
                    "popped": 0,
                    "successors": 0,
                    "enqueued": 0,
                    "heuristic_calls": 0,
                    "max_frontier": 0,
                    "grid_step_ms": 0.0,
                    "key_ms": 0.0,
                    "heuristic_ms": 0.0,
                    "reused_plan": 1,
                },
                0,
                len(self._fallback_plan),
            )
            self._last_action = action
            return action
        if self._fallback_plan:
            self._fallback_plan.clear()
            self._fallback_plan_next_turn = None

        search_started = perf_counter()
        search_stats: dict[str, int | float] = {
            "popped": 0,
            "successors": 0,
            "enqueued": 0,
            "heuristic_calls": 0,
            "max_frontier": 1,
            "grid_step_ms": 0.0,
            "key_ms": 0.0,
            "heuristic_ms": 0.0,
        }
        tie_breaker = count()
        initial_key = str(state.grid)
        frontier = [(0, next(tie_breaker), state, initial_key, 0)]
        # Turn and score change even when an action leaves the board
        # unchanged, so they must not make duplicate positions look new.
        visited = {initial_key}
        parents: dict[str, tuple[str, Action]] = {}

        def reconstruct_plan(goal_key: str) -> deque[Action]:
            plan: deque[Action] = deque()
            while goal_key != initial_key:
                parent_key, action = parents[goal_key]
                plan.appendleft(action)
                goal_key = parent_key
            return plan

        while frontier:
            search_stats["popped"] += 1
            _, _, current_state, current_key, depth = heapq.heappop(frontier)

            for action in Action:
                search_stats["successors"] += 1
                operation_started = perf_counter()
                next_state = grid_step(current_state, action)
                search_stats["grid_step_ms"] += (perf_counter() - operation_started) * 1000
                if next_state.lose:
                    continue

                if next_state.win:
                    goal_key = str(next_state.grid)
                    parents[goal_key] = (current_key, action)
                    self._fallback_plan = reconstruct_plan(goal_key)
                    returned_action = self._fallback_plan.popleft()
                    self._fallback_plan_next_turn = state.turn + 1
                    self._record_search_stats(search_started, search_stats, len(visited), len(frontier))
                    self._last_action = returned_action
                    return returned_action

                operation_started = perf_counter()
                key = str(next_state.grid)
                search_stats["key_ms"] += (perf_counter() - operation_started) * 1000

                if key in visited:
                    continue

                visited.add(key)
                parents[key] = (current_key, action)

                new_depth = depth + 1
                search_stats["heuristic_calls"] += 1
                operation_started = perf_counter()
                priority = new_depth + h(self, next_state)
                search_stats["heuristic_ms"] += (perf_counter() - operation_started) * 1000

                heapq.heappush(
                    frontier,
                    (priority, next(tie_breaker), next_state, key, new_depth),
                )
                search_stats["enqueued"] += 1
                search_stats["max_frontier"] = max(search_stats["max_frontier"], len(frontier))

        self._record_search_stats(search_started, search_stats, len(visited), len(frontier))
        self._last_action = Action.WAIT
        return Action.WAIT

    def _memory_telemetry(self) -> dict[str, int | float]:
        """Return cheap cache counters and, when available, process RSS.

        The counters are exact for the persistent caches.  RSS includes the
        interpreter and environment as well, so it is best used to detect
        growth across an episode rather than to attribute individual bytes.
        """
        memory: dict[str, int | float] = {
            "cache_distance_entries": self._last_cache_stats.get(
                "distance_entries", 0
            ),
            "cache_static_plan_actions": len(self._static_plan),
            "cache_powerup_plan_actions": len(self._powerup_plan),
            "cache_keydoor_plan_actions": len(self._keydoor_plan),
            "cache_mixed_plan_actions": len(self._mixed_plan),
            "cache_box_plan_actions": len(self._box_plan),
            "cache_fallback_plan_actions": len(self._fallback_plan),
        }
        if self._memory_process is not None:
            try:
                rss_bytes = self._memory_process.memory_info().rss
            except (OSError, RuntimeError):
                # Telemetry must never prevent the agent from taking an action.
                return memory
            self._rss_peak_bytes = max(self._rss_peak_bytes, rss_bytes)
            memory["rss_mb"] = round(rss_bytes / (1024 * 1024), 2)
            memory["rss_peak_mb"] = round(
                self._rss_peak_bytes / (1024 * 1024), 2
            )
        return memory

    def _record_search_stats(
        self,
        search_started: float,
        stats: dict[str, int | float],
        visited_count: int,
        frontier_count: int,
    ) -> None:
        """Save compact diagnostics for the just-completed planning call."""
        stats["visited"] = visited_count
        stats["frontier_remaining"] = frontier_count
        stats["search_ms"] = round((perf_counter() - search_started) * 1000, 2)
        stats.update(self._memory_telemetry())
        self._last_search_stats = dict(stats)
        self._search_stats_history.append(dict(stats))

    def telemetry(self) -> list[dict[str, int | float]]:
        """Return one aggregate record for every completed real planning call."""
        return [dict(stats) for stats in self._search_stats_history]

    def parse(self, observation: ImageObservation) -> GridState:
        """
        Convert an image observation into a GridState.

        Grid Play also calls this method to display the agent's reconstructed view.
        """
        info = observation["info"]
        config = info["config"]
        status = info["status"]
        width = config["width"]
        height = config["height"]

        gridstate = GridState(
            width=width,
            height=height,
            movement=MOVEMENTS["cardinal"],
            objective=OBJECTIVES["collect_gems_and_exit"],
            step_cost=STEP_COST,
            seed=None if config["seed"] == -1 else config["seed"],
            turn=status["turn"],
            score=status["score"],
            win=status["phase"] == "win",
            lose=status["phase"] == "lose",
            message=info["message"] or None,
            turn_limit=None if config["turn_limit"] == -1 else config["turn_limit"],
        )

        agent_count = 0
        for y, row in enumerate(self.split_cells(observation)):
            for x, cell_image in enumerate(row):
                entity = self.predict(cell_image)
                if entity is not None:
                    if isinstance(entity, AgentEntity):
                        agent_count += 1
                        entity.set_health(info["agent"]["health"]["current_health"])
                    gridstate.add((x, y), entity)

        if agent_count != 1:
            raise ValueError(
                f"predict() must identify exactly one AgentEntity, but found {agent_count}."
            )

        return gridstate

    def split_cells(self, observation: ImageObservation) -> list[list[np.ndarray]]:
        """Split an RGBA observation into rows of cell images."""
        image = observation["image"]
        config = observation["info"]["config"]
        width = config["width"]
        height = config["height"]
        image_height, image_width = image.shape[:2]
        cells = []

        for y in range(height):
            y_start = y * image_height // height
            y_end = (y + 1) * image_height // height
            row = []
            for x in range(width):
                x_start = x * image_width // width
                x_end = (x + 1) * image_width // width
                row.append(image[y_start:y_end, x_start:x_end, :])
            cells.append(row)

        return cells

    def predict(self, cell_image: np.ndarray) -> BaseEntity | None:
        """Return the entity most similar to one RGBA cell image, or None for floor."""
        entity_types = {
            "boots": SpeedPowerUpEntity,
            "box": BoxEntity,
            "coin": CoinEntity,
            "exit": ExitEntity,
            "gem": GemEntity,
            "ghost": PhasingPowerUpEntity,
            "human": AgentEntity,
            "key": KeyEntity,
            "lava": LavaEntity,
            "locked": LockedDoorEntity,
            "opened": UnlockedDoorEntity,
            "shield": ShieldPowerUpEntity,
            "wall": WallEntity,
        }
        image_size = (cell_image.shape[1], cell_image.shape[0])
        asset_root = Path(DEFAULT_ASSET_ROOT)

        with Image.open(asset_root / "floor" / "floor_1.png") as image:
            floor = image.convert("RGBA").resize(image_size)

        observed = cell_image.astype(np.int16)
        best_entity = None
        best_error = np.abs(observed - np.asarray(floor)).mean()

        for asset_name, entity_type in entity_types.items():
            asset_path = asset_root / asset_name / f"{asset_name}_1.png"
            with Image.open(asset_path) as image:
                asset = image.convert("RGBA").resize(image_size)

            candidate = np.asarray(Image.alpha_composite(floor, asset))
            error = np.abs(observed - candidate).mean()
            if error < best_error:
                best_error = error
                best_entity = entity_type

        return None if best_entity is None else best_entity()

    def info(self) -> dict[str, str]:
        """
        Return info about the agent.

        NOTE: This method is optional and intended for debugging in Grid Play only. 
        You do not need to implement it for Coursemology submission, but it can be 
        helpful for visualizing your agent's internal state during development. 
        Implementing this method will not affect grading.
        """
        search = self._last_search_stats
        cache = self._last_cache_stats
        return {
            "name": (
                "A* Agent with replayed compact static-state A* and bounded coin detours"
                if self._static_fast_path
                else "A* Agent with compact key-door-state A*"
                if self._keydoor_fast_path
                else "A* Agent with compact power-up-state A*"
                if self._powerup_fast_path
                else "A* Agent with compact mixed-mechanics A*"
                if self._mixed_fast_path
                else "A* Agent with compact Sokoban-state A*"
                if self._box_fast_path
                else "A* Agent with cached wall-aware heuristic and replayed full-state plan"
            ),
            "search": (
                f"{search.get('search_ms', 0)} ms; popped={search.get('popped', 0)}; "
                f"successors={search.get('successors', 0)}; "
                f"visited={search.get('visited', 0)}; "
                f"h={search.get('heuristic_calls', 0)}; "
                f"max_frontier={search.get('max_frontier', 0)}"
            ),
            "cache": (
                f"{cache.get('build_ms', 0)} ms; targets={cache.get('targets', 0)}; "
                f"reachable_tiles={cache.get('reachable_tiles', 0)}"
            ),
            "timing": (
                f"grid_step={round(search.get('grid_step_ms', 0), 2)} ms; "
                f"grid_key={round(search.get('key_ms', 0), 2)} ms; "
                f"heuristic={round(search.get('heuristic_ms', 0), 2)} ms"
            ),
        }
