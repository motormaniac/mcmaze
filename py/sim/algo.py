"""A step-by-step model of the algorithm in commands/maze2.txt. One step = one BFS iteration = 1 gt.

Modelled as the commands are written, with the fixes agreed on:
  * an unfilled neighbor (no node yet, or a node that has no tile yet) is skipped: any encoding fits
  * all 6 directions are checked, pushed and expanded (the commands only have N/E/S/W so far)
  * a newly summoned node starts at edit 0
  * constraint nodes count as having infinite edit, expose `wall` and target only `wall`
  * pushing a node that is already queued does nothing (the `if score @s i matches -1` guard)

Step, for the popped node s:
  filter    every lookup starts at level 2. A lookup that fails a filled neighbor's targets drops to
            1; if that neighbor is strong (higher edit than s, or a constraint), it drops to 0.
  level 2   if any lookup is at 2: pick among those.
  level 1   else if any at 1: s.edit += 1, push every unqueued neighbor node whose edit is now below
            s.edit, pick among level 1.
  level 0   else: s.edit += 1, push s again, place nothing, and skip the rest of the step.
  expand    summon and push a node on every empty neighbor position (constraints are nodes too,
            so nothing is summoned past the bounds).
  paste     place the picked lookup on s.
  end       queue empty -> done. Any edit above LIMIT -> error.
"""

import random
from collections import deque
from dataclasses import dataclass, field

from tiles import Pos, Problem, accepts, add, wall_accepts


@dataclass(eq=False)
class Node:
  pos: Pos
  edit: int = 0
  tile: int | None = None
  queued: bool = False                   # i >= 0 in game; False is i = -1


class Queue:
  """First in, first out. Pushing a node that is already queued does nothing."""

  def __init__(self) -> None:
    self.nodes: deque[Node] = deque()

  def __len__(self) -> int:
    return len(self.nodes)

  def push(self, node: Node) -> bool:
    if node.queued:
      return False
    node.queued = True
    self.nodes.append(node)
    return True

  def pop(self) -> Node:
    node = self.nodes.popleft()
    node.queued = False
    return node


@dataclass
class Event:
  """What one step did, for --trace."""
  tick: int
  pos: Pos
  edit_before: int
  level: int = -1                        # 2, 1 or 0
  candidates: int = 0
  placed: str = ""
  pushed: list[Pos] = field(default_factory=list)


@dataclass
class Run:
  outcome: str                           # "done", "error" (edit above LIMIT), "timeout" (tick cap)
  ticks: int
  peak_edit: int
  first_tick_at_edit: list[int]          # [k] = tick at which some edit first reached k
  grid: dict[Pos, int | None]


class Algorithm:
  def __init__(self, problem: Problem) -> None:
    self.problem = problem
    tiles = problem.tiles
    # acc[d][b] = lookups a that pass the check against filled neighbor b on side d of the cell
    self.acc = [[sum(1 << a for a, ta in enumerate(tiles) if accepts(ta, d, tb)) for tb in tiles]
                for d in range(6)]
    self.wall_acc = [sum(1 << a for a, ta in enumerate(tiles) if wall_accepts(ta, d, problem.wall))
                     for d in range(6)]
    self.full = (1 << len(tiles)) - 1

  def run(self, rng: random.Random, limit: int | None, tick_cap: int,
          trace: list[Event] | None = None) -> Run:
    problem, tiles = self.problem, self.problem.tiles
    nodes: dict[Pos, Node] = {}
    queue = Queue()
    start = Node((0, 0, 0))
    nodes[start.pos] = start
    queue.push(start)
    peak, first_tick, tick = 0, [0], 0

    def bump(node: Node) -> None:
      nonlocal peak
      node.edit += 1
      if node.edit > peak:
        peak = node.edit
        first_tick.append(tick)

    while True:
      tick += 1
      s = queue.pop()
      event = Event(tick, s.pos, s.edit) if trace is not None else None
      pushed: list[Pos] = []

      weak, strong = self.full, self.full
      for d in range(6):
        q = add(s.pos, d)
        if problem.blocked(q):
          mask = self.wall_acc[d]
          weak &= mask
          strong &= mask
          continue
        n = nodes.get(q)
        if n is None or n.tile is None:
          continue                       # unfilled: wildcard
        mask = self.acc[d][n.tile]
        weak &= mask
        if n.edit > s.edit:
          strong &= mask
      if weak:
        level, pool = 2, weak
      elif strong:
        level, pool = 1, strong
        bump(s)
        for d in range(6):
          n = nodes.get(add(s.pos, d))
          if n is not None and n.edit < s.edit and queue.push(n):
            pushed.append(n.pos)
      else:
        level, pool = 0, 0
        bump(s)
        queue.push(s)
        pushed.append(s.pos)
      if level > 0:
        for d in range(6):
          q = add(s.pos, d)
          if not problem.blocked(q) and q not in nodes:
            n = Node(q)
            nodes[q] = n
            queue.push(n)
            pushed.append(q)
        s.tile = pick(pool, rng)
      if event is not None and trace is not None:
        event.level, event.candidates, event.pushed = level, pool.bit_count(), pushed
        event.placed = tiles[s.tile].label if level > 0 and s.tile is not None else ""
        trace.append(event)

      if len(queue) == 0:
        outcome = "done"
      elif limit is not None and peak > limit:
        outcome = "error"
      elif tick >= tick_cap:
        outcome = "timeout"
      else:
        continue
      grid = {p: n.tile for p, n in nodes.items()}
      return Run(outcome, tick, peak, first_tick, grid)


def pick(mask: int, rng: random.Random) -> int:
  """A uniformly random set bit of mask."""
  k = rng.randrange(mask.bit_count())
  while True:
    low = mask & -mask
    if k == 0:
      return low.bit_length() - 1
    mask ^= low
    k -= 1
