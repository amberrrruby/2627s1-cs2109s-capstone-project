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
import numpy as np
from PIL import Image

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
        self._exit_positions: set[tuple[int, int]] = set()
        self._wall_distances: dict[
            tuple[int, int], dict[tuple[int, int], int]
        ] = {}

        # Dynamic facts are tracked separately from the level blueprint.
        self._remaining_gems: set[tuple[int, int]] = set()
        self._agent_position: tuple[int, int] | None = None
        self._last_action: Action | None = None
        self._last_turn: int | None = None

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

        walls: set[tuple[int, int]] = set()
        gems: set[tuple[int, int]] = set()
        exits: set[tuple[int, int]] = set()
        agent_position: tuple[int, int] | None = None
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

        self._level_key = level_key
        self._walls = walls
        self._initial_gems = gems
        self._exit_positions = exits
        self._remaining_gems = set(gems)
        self._agent_position = agent_position
        targets = gems | exits
        self._wall_distances = {
            target: self._bfs_wall_distances(target, state.width, state.height)
            for target in targets
        }
        self._last_action = None
        self._last_turn = state.turn

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

        tie_breaker = count()
        frontier = [ (0, next(tie_breaker), state, None, 0) ]
        # Turn and score change even when an action leaves the board
        # unchanged, so they must not make duplicate positions look new.
        visited = {str(state.grid)}

        while frontier:
            _, _, current_state, first_action, depth = heapq.heappop(frontier)

            for action in Action:
                next_state = grid_step(current_state, action)
                if next_state.lose:
                    continue

                next_first_action = action if first_action is None else first_action
                if next_state.win:
                    self._last_action = next_first_action
                    return next_first_action

                key = str(next_state.grid)

                if key in visited:
                    continue

                visited.add(key)

                new_depth = depth + 1
                priority = new_depth + h(self, next_state)

                heapq.heappush(frontier, (priority, next(tie_breaker), next_state, next_first_action, new_depth))

        self._last_action = Action.WAIT
        return Action.WAIT

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
        # Optional: return info about the agent
        return {"name": "A* Agent, with cached BFS gem distance knowledge"}
