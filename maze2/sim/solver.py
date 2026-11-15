"""Exact solver: decides whether a Problem has any valid filling. This is the ground truth the
simulated algorithm is judged against.

Backtracking search over bitset domains with arc consistency and smallest-domain-first. A valid
filling puts a tile on every free cell so that every adjacent pair matches (both halves), and every
face against a constraint is `wall` and targets `wall`.
"""

from dataclasses import dataclass

from tiles import Pos, Problem, add, matches, wall_matches


@dataclass
class Verdict:
  status: str                            # "solvable", "unsolvable", or "unknown" (budget ran out)
  solution: dict[Pos, int] | None        # cell -> tile index, when solvable
  nodes: int                             # search nodes used


def bits(mask: int):
  while mask:
    low = mask & -mask
    yield low.bit_length() - 1
    mask ^= low


def compat_table(problem: Problem) -> list[list[int]]:
  """compat[d][a] = mask of tiles b that may sit on side d of tile a."""
  tiles = problem.tiles
  return [[sum(1 << b for b, tb in enumerate(tiles) if matches(ta, d, tb)) for ta in tiles]
          for d in range(6)]


def solve(problem: Problem, budget: int = 2_000_000) -> Verdict:
  tiles = problem.tiles
  cells = problem.free_cells()
  index = {p: i for i, p in enumerate(cells)}
  compat = compat_table(problem)
  full = (1 << len(tiles)) - 1
  wall_ok = [sum(1 << a for a, t in enumerate(tiles) if wall_matches(t, d, problem.wall))
             for d in range(6)]

  neighbors: list[list[tuple[int, int]]] = []
  dom = [full] * len(cells)
  for i, p in enumerate(cells):
    adj = []
    for d in range(6):
      q = add(p, d)
      if problem.blocked(q):
        dom[i] &= wall_ok[d]
      else:
        adj.append((d, index[q]))
    neighbors.append(adj)

  cache: dict[tuple[int, int], int] = {}

  def support(d: int, mask: int) -> int:
    key = (d, mask)
    s = cache.get(key)
    if s is None:
      s = 0
      for a in bits(mask):
        s |= compat[d][a]
      cache[key] = s
    return s

  def propagate(dom: list[int], queue: list[int]) -> bool:
    while queue:
      i = queue.pop()
      for d, j in neighbors[i]:
        new = dom[j] & support(d, dom[i])
        if new != dom[j]:
          if not new:
            return False
          dom[j] = new
          queue.append(j)
    return True

  if any(m == 0 for m in dom) or not propagate(dom, list(range(len(cells)))):
    return Verdict("unsolvable", None, 0)

  nodes = 0

  def search(dom: list[int]) -> list[int] | None:
    nonlocal nodes
    nodes += 1
    if nodes > budget:
      raise TimeoutError
    best, best_count = -1, 0
    for i, m in enumerate(dom):
      c = m.bit_count()
      if c > 1 and (best < 0 or c < best_count):
        best, best_count = i, c
    if best < 0:
      return dom
    for a in bits(dom[best]):
      child = dom.copy()
      child[best] = 1 << a
      if propagate(child, [best]):
        found = search(child)
        if found is not None:
          return found
    return None

  try:
    found = search(dom)
  except TimeoutError:
    return Verdict("unknown", None, nodes)
  if found is None:
    return Verdict("unsolvable", None, nodes)
  return Verdict("solvable", {p: found[i].bit_length() - 1 for i, p in enumerate(cells)}, nodes)


def check_filling(problem: Problem, grid: dict[Pos, int | None]) -> tuple[list[Pos], list[str]]:
  """Returns (unfilled cells, mismatched pairs) for a finished grid of tile indices."""
  tiles = problem.tiles
  unfilled = [p for p in problem.free_cells() if grid.get(p) is None]
  bad = []
  for p in problem.free_cells():
    a = grid.get(p)
    if a is None:
      continue
    for d in range(6):
      q = add(p, d)
      if problem.blocked(q):
        if not wall_matches(tiles[a], d, problem.wall):
          bad.append(f"{p} {tiles[a].label} against the constraint on side {d}")
      elif d in (1, 2, 4):                 # east, south, up: each pair once
        b = grid.get(q)
        if b is not None and not matches(tiles[a], d, tiles[b]):
          bad.append(f"{p} {tiles[a].label} / {q} {tiles[b].label}")
  return unfilled, bad
