"""A tick-by-tick model of $bfs_iterate in maze2/src/maze2.mct. One tick = one run of the chain = 1 gt.

`select` (the node being filled), its priority list and its ignored sides carry over between ticks.
A tick:

  pop       if there is no select: pop the queue into select, then look at each of its 6 sides
              constraint      (bounds or a blocker) only lookups that target WALL on that side pass
              node with tile  only lookups whose targets on that side include the node's facing
                              encoding pass (not_$dir). The node joins the priority list with
                              rng(1..10) + facing encoding id + edit * 1,000,000
              node, no tile   (encodings -1) every lookup passes; not in the priority list
              no node         summon one there (edit 0, no tile) and push it
  filter    the lookups that pass every side that isn't ignored
  pick      if select and the filter isn't empty: each candidate rolls random(0..100) + rngWeight and
            the highest goes on select. select.edit += 1 and select is cleared
  relax     clear the priority of every node at 0, then shift the list so its lowest is 0. If select
            is still set and the list isn't empty: push every node at 0 and ignore its side, in
            direction order (ties go together). Otherwise clear select: it gives up and keeps
            whatever tile it had
  end       no select and an empty queue -> done. Any edit above LIMIT -> error

Modelling choices:
  * edit counts are in units of one pick (1,000,000 in game)
  * candidates that tie on the highest roll are broken at random (in game: whichever lookup entity
    randChoose finds first)
"""

import random
from collections import deque
from dataclasses import dataclass, field

from tiles import OPP, Pos, Problem, add, default_ids, fits, wall_fits

EDIT = 1_000_000                         # one pick's worth of edit in game


@dataclass(eq=False)
class Node:
  pos: Pos
  edit: int = 0
  tile: int | None = None
  queued: bool = False                   # i >= 0 in game; False is i = -1


class Queue:
  """First in, first out. Pushing a node that is already queued does nothing (the `unless score @s i
  matches 0..` guard)."""

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
  """What one tick did, for --trace."""
  tick: int
  pos: Pos                               # select
  edit_before: int
  popped: bool                           # select was popped this tick
  ignored: list[int]                     # sides ignored when this tick's filter ran
  candidates: int = 0
  placed: str = ""
  relaxed: list[int] = field(default_factory=list)   # sides ignored at the end of this tick
  gave_up: bool = False
  pushed: list[Pos] = field(default_factory=list)


@dataclass
class Run:
  outcome: str                           # "done" (queue empty), "error" (edit above LIMIT), "timeout" (tick cap)
  ticks: int
  peak_edit: int
  first_tick_at_edit: list[int]          # [k] = tick at which some edit first reached k
  grid: dict[Pos, int | None]


class Algorithm:
  def __init__(self, problem: Problem) -> None:
    self.problem = problem
    tiles = problem.tiles
    # passes[d][b] = lookups that pass filled neighbor b on their side d
    self.passes = [[sum(1 << a for a, ta in enumerate(tiles) if fits(ta, d, tb)) for tb in tiles]
                   for d in range(6)]
    self.wall_passes = [sum(1 << a for a, ta in enumerate(tiles) if wall_fits(ta, d, problem.wall))
                        for d in range(6)]
    ids = problem.ids if problem.ids is not None else default_ids(tiles, problem.wall)
    # facing[d][b] = id of b's encoding that faces a select on b's side OPP[d]
    self.facing = [[ids[tb.phys[OPP[d]]] for tb in tiles] for d in range(6)]
    self.full = (1 << len(tiles)) - 1

  def run(self, rng: random.Random, limit: int | None, tick_cap: int,
          trace: list[Event] | None = None) -> Run:
    problem, tiles, full = self.problem, self.problem.tiles, self.full
    nodes: dict[Pos, Node] = {}
    queue = Queue()
    start = Node((0, 0, 0))
    nodes[start.pos] = start
    queue.push(start)

    select: Node | None = None
    passing = [full] * 6                 # per side of select: the lookups without not_$dir
    ignored: list[int] = []
    priority: dict[Node, int] = {}
    side: dict[Node, int] = {}           # the neighbor score: which side of select a node is on
    peak, first_tick, tick = 0, [0], 0

    while True:
      tick += 1
      pushed: list[Pos] = []
      popped = select is None

      # pop
      if select is None:
        select = queue.pop()
        passing, ignored = [full] * 6, []
        priority.clear()
        side.clear()
        for d in range(6):
          q = add(select.pos, d)
          if problem.blocked(q):
            passing[d] = self.wall_passes[d]
            continue
          n = nodes.get(q)
          if n is None:
            n = nodes[q] = Node(q)
            queue.push(n)
            pushed.append(q)
            continue
          side[n] = d
          if n.tile is not None:
            passing[d] = self.passes[d][n.tile]
            priority[n] = rng.randint(1, 10) + self.facing[d][n.tile] + n.edit * EDIT

      event = Event(tick, select.pos, select.edit, popped, list(ignored)) if trace is not None else None

      # filter and pick
      pool = full
      for mask in passing:
        pool &= mask
      if pool:
        select.tile = pick(pool, tiles, rng)
        select.edit += 1
        if select.edit > peak:
          peak = select.edit
          first_tick.append(tick)
        if event is not None:
          event.placed = tiles[select.tile].label
        select = None

      # relax
      for n in [n for n, p in priority.items() if p == 0]:
        del priority[n]
      if priority:
        low = min(priority.values())
        for n in priority:
          priority[n] -= low
      if select is not None and priority:
        at_zero = {side[n]: n for n, p in priority.items() if p == 0 and n in side}
        for d in sorted(at_zero):
          n = at_zero[d]
          if queue.push(n):
            pushed.append(n.pos)
          del side[n]
          passing[d] = full
          ignored.append(d)
          if event is not None:
            event.relaxed.append(d)
      elif select is not None:
        select = None
        if event is not None:
          event.gave_up = True

      if event is not None and trace is not None:
        event.candidates, event.pushed = pool.bit_count(), pushed
        trace.append(event)

      # end
      if select is None and len(queue) == 0:
        outcome = "done"
      elif limit is not None and peak > limit:
        outcome = "error"
      elif tick >= tick_cap:
        outcome = "timeout"
      else:
        continue
      grid = {p: n.tile for p, n in nodes.items()}
      return Run(outcome, tick, peak, first_tick, grid)


def pick(mask: int, tiles: list, rng: random.Random) -> int:
  """The lookup in mask with the highest random(0..100) + weight, ties broken at random."""
  best, top = [], None
  while mask:
    low = mask & -mask
    mask ^= low
    a = low.bit_length() - 1
    roll = rng.randint(0, 100) + tiles[a].weight
    if top is None or roll > top:
      best, top = [a], roll
    elif roll == top:
      best.append(a)
  return best[0] if len(best) == 1 else rng.choice(best)
