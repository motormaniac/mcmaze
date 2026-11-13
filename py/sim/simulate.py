"""Simulates the maze2 algorithm (commands/maze2.txt) so tests can be checked before running in game.

  cd py
  uv run sim/simulate.py check tiles.csv
      expand rotations, check reciprocity, flag likely typos
  uv run sim/simulate.py run tiles.csv --size 4 1 4 [--constraint 1,0,2 ...]
      exact verdict (solvable or not), then many simulated runs: how long they take, how high edit
      counts climb, and the false-error rate for each LIMIT
  uv run sim/simulate.py fuzz --instances 300
      random small reciprocal inputs; reports any run that ends with a wrong answer or that looks
      stuck on a solvable input

--size is X (width, east) Y (height, up) Z (length, south). Coordinates start at the start cell
(0,0,0). One step of the algorithm is 1 gt; 20 gt = 1 s.
"""

import argparse
import random
import statistics
import sys
from pathlib import Path

from algo import Algorithm, Event, Run
from solver import Verdict, check_filling, solve
from tiles import DIRS, OPP, WALL, Pos, Problem, Tile, TileError, add, lint, read_csv, \
  reciprocity_errors, rotations, write_csv

LIMITS = (1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512)


# ------------------------------------------------------------------------------------------- output

def pct(values: list[int], p: float) -> int:
  s = sorted(values)
  return s[min(len(s) - 1, int(p * len(s)))]


def spread(values: list[int]) -> str:
  if not values:
    return "-"
  return (f"median {statistics.median(values):g}, p95 {pct(values, 0.95)}, max {max(values)}")


def gt(ticks: float) -> str:
  return f"{ticks:g} gt ({ticks / 20:.1f} s)"


def show_grid(problem: Problem, grid: dict[Pos, int | None]) -> str:
  X, Y, Z = problem.size
  labels = {p: problem.tiles[t].label for p, t in grid.items() if t is not None}
  width = max([len(v) for v in labels.values()] + [1])
  lines = []
  for y in range(Y):
    lines.append(f"  y={y}  (rows z=0.., columns x=0..; # constraint, . unfilled)")
    for z in range(Z):
      row = []
      for x in range(X):
        p = (x, y, z)
        row.append(("#" if p in problem.constraints else labels.get(p, ".")).ljust(width))
      lines.append("    " + "  ".join(row))
  return "\n".join(lines)


def show_event(e: Event) -> str:
  what = {2: "fits all", 1: "fits strong only", 0: "fits nothing"}[e.level]
  out = f"  {e.tick:>6}  {e.pos} edit {e.edit_before}: {what}, {e.candidates} candidates"
  if e.placed:
    out += f" -> {e.placed}"
  if e.pushed:
    out += f"; pushed {', '.join(map(str, e.pushed))}"
  return out


# ------------------------------------------------------------------------------------------- checks

def load(path: Path, wall: str, allow_nonreciprocal: bool) -> list[Tile]:
  tiles = read_csv(path)
  errors = reciprocity_errors(tiles, wall)
  for note in lint(tiles, wall):
    print(f"note: {note}")
  if errors:
    print(f"{len(errors)} non-reciprocal pairs (the algorithm only checks one half of each):")
    for e in errors[:20]:
      print(f"  {e}")
    if len(errors) > 20:
      print(f"  ... and {len(errors) - 20} more")
    if not allow_nonreciprocal:
      raise SystemExit(2)
  return tiles


def cmd_check(args: argparse.Namespace) -> int:
  tiles = load(args.csv, args.wall, True)
  print(f"{len(tiles) // 4} cell types, {len(tiles)} lookups")
  for t in tiles:
    faces = "  ".join(f"{DIRS[d][0].upper()}:{t.phys[d]}>{'|'.join(sorted(t.targets[d]))}"
                      for d in range(6))
    print(f"  {t.label:<24} {faces}")
  return 0


# ---------------------------------------------------------------------------------------------- run

def parse_pos(text: str) -> Pos:
  try:
    x, y, z = (int(v) for v in text.split(","))
  except ValueError:
    raise argparse.ArgumentTypeError(f"expected x,y,z, got {text!r}")
  return (x, y, z)


def trials(problem: Problem, count: int, seed: int, limit: int | None, tick_cap: int) -> list[Run]:
  algo = Algorithm(problem)
  return [algo.run(random.Random(seed * 1_000_003 + i), limit, tick_cap) for i in range(count)]


def describe(problem: Problem, verdict: Verdict, runs: list[Run], limit_max: int) -> list[str]:
  """The report for one problem. Lines starting with 'BUG' or 'WARNING' are anomalies."""
  out = []
  done = [r for r in runs if r.outcome == "done"]
  for r in done:
    unfilled, bad = check_filling(problem, r.grid)
    if bad:
      out.append(f"BUG: a run finished with {len(bad)} mismatched pairs, e.g. {bad[0]}")
      break
    if unfilled:
      out.append(f"BUG: a run finished with {len(unfilled)} cells never reached, e.g. "
                 f"{unfilled[0]} (separate region the BFS can't reach)")
      break
  counts = {k: sum(r.outcome == k for r in runs) for k in ("done", "error", "timeout")}
  out.append(f"{len(runs)} runs: {counts['done']} finished, {counts['error']} passed "
             f"LIMIT={limit_max}, {counts['timeout']} hit the tick cap")

  if verdict.status == "unsolvable":
    if done:
      out.append(f"BUG: {len(done)} runs finished on an input with no solution")
    if counts["timeout"]:
      out.append("WARNING: runs reached the tick cap without edits passing LIMIT")
    out.append("Expected: error. Time until an edit first passes LIMIT:")
    for L in LIMITS:
      if L > limit_max:
        break
      ticks = [r.first_tick_at_edit[L + 1] for r in runs if len(r.first_tick_at_edit) > L + 1]
      if ticks:
        out.append(f"  LIMIT {L:>4}: {spread(ticks)} gt  (median {statistics.median(ticks) / 20:.1f} s)")
    return out

  if verdict.status == "unknown":
    out.append("Exact solver ran out of budget; solvability unknown.")
  else:
    out.append("Expected: finish.")
  if done:
    out.append(f"  steps to finish: {spread([r.ticks for r in done])} "
               f"(median {gt(statistics.median([r.ticks for r in done]))})")
    out.append(f"  peak edit:       {spread([r.peak_edit for r in done])}")
  out.append("  false-error rate by LIMIT (fraction of runs whose peak edit passes it):")
  safe = None
  for L in LIMITS:
    if L > limit_max:
      break
    failed = sum(r.outcome != "done" or r.peak_edit > L for r in runs)
    out.append(f"    LIMIT {L:>4}: {failed}/{len(runs)}")
    if failed == 0 and safe is None:
      safe = L
  if safe is not None:
    out.append(f"  smallest LIMIT with no false errors in {len(runs)} runs: {safe} "
               f"(true rate likely under {3 / len(runs):.1%})")
  elif verdict.status == "solvable":
    out.append(f"WARNING: no LIMIT up to {limit_max} finished every run")
  return out


def cmd_run(args: argparse.Namespace) -> int:
  tiles = load(args.csv, args.wall, args.allow_nonreciprocal)
  problem = Problem(tiles, tuple(args.size), frozenset(args.constraint), args.wall)
  print(f"{len(tiles) // 4} cell types ({len(tiles)} lookups), grid {problem.size}, "
        f"{len(problem.constraints)} interior constraints, {len(problem.free_cells())} cells")
  verdict = solve(problem, args.budget)
  print(f"exact solver: {verdict.status} ({verdict.nodes} search nodes)")
  if args.witness and verdict.solution:
    print("one valid filling:")
    print(show_grid(problem, verdict.solution))

  if args.trace is not None:
    trace: list[Event] = []
    run = Algorithm(problem).run(random.Random(args.seed * 1_000_003), args.limit_max,
                                 args.tick_cap, trace)
    print(f"trace of run 0 ({run.outcome} after {run.ticks} steps):")
    for e in trace[:args.trace]:
      print(show_event(e))
    if len(trace) > args.trace:
      print(f"  ... {len(trace) - args.trace} more steps")
    print(show_grid(problem, run.grid))

  runs = trials(problem, args.trials, args.seed, args.limit_max, args.tick_cap)
  report = describe(problem, verdict, runs, args.limit_max)
  print("\n".join(report))
  return 1 if any(line.startswith(("BUG", "WARNING")) for line in report) else 0


# --------------------------------------------------------------------------------------------- fuzz

def random_problem(rng: random.Random) -> tuple[list[Tile], Problem]:
  """A small random input that is reciprocal by construction: each side's targets are exactly the
  encodings related to that side's own encoding, under a symmetric relation."""
  letters = "abcd"[:rng.randint(1, 4)]
  pairs = [(a, b) for i, a in enumerate(letters) for b in letters[i:]]
  related = {e: set() for e in letters}
  for a, b in pairs:
    if rng.random() < 0.45:
      related[a].add(b)
      related[b].add(a)
  for e in letters:
    while len(related[e]) > 3:
      other = rng.choice(sorted(related[e] - {e}) or [e])
      related[e].discard(other)
      related[other].discard(e)
  for e in letters:
    if not related[e]:
      related[e].add(e)
  related[WALL] = {WALL}

  size = (rng.randint(1, 4), rng.choice((1, 1, 1, 2, 2, 3)), rng.randint(1, 4))
  cells = [(x, y, z) for x in range(size[0]) for y in range(size[1]) for z in range(size[2])][1:]
  blockers = frozenset(rng.sample(cells, min(len(cells), rng.choice((0, 0, 0, 1, 2)))))
  shell = Problem([], size, blockers)

  def tile(name: str, phys: tuple[str, ...]) -> Tile:
    return Tile(name, 0, phys, tuple(frozenset(related[e]) for e in phys))

  mode = rng.random()
  if mode < 0.3:
    # random cell types: mostly unsolvable
    base = [tile(f"t{n}", tuple(WALL if rng.random() < 0.4 else rng.choice(letters) for _ in range(6)))
            for n in range(rng.randint(1, 4))]
  else:
    # planted: build a valid filling first, then take its cells as the cell types
    faces: dict[tuple[Pos, int], str] = {}
    for p in shell.free_cells():
      for d in range(6):
        q = add(p, d)
        if shell.blocked(q):
          faces[p, d] = WALL
        elif (p, d) not in faces:
          e = rng.choice([*letters, WALL]) if rng.random() < 0.8 else WALL
          faces[p, d] = e
          faces[q, OPP[d]] = rng.choice(sorted(related[e]))
    seen: dict[tuple[str, ...], Tile] = {}
    for p in shell.free_cells():
      phys = tuple(faces[p, d] for d in range(6))
      seen.setdefault(phys, tile(f"t{len(seen)}", phys))
    base = list(seen.values())
    if mode > 0.8 and len(base) > 1:
      base.pop(rng.randrange(len(base)))           # often unsolvable, but not obviously
    for n in range(rng.choice((0, 0, 1, 2))):      # decoys
      base.append(tile(f"x{n}", tuple(rng.choice([*letters, WALL]) for _ in range(6))))
  tiles = [r for t in base for r in rotations(t)]
  return base, Problem(tiles, size, blockers)


def reachable(problem: Problem) -> set[Pos]:
  """Free cells the BFS can reach from the start cell without crossing a constraint."""
  seen, todo = {(0, 0, 0)}, [(0, 0, 0)]
  while todo:
    p = todo.pop()
    for d in range(6):
      q = add(p, d)
      if not problem.blocked(q) and q not in seen:
        seen.add(q)
        todo.append(q)
  return seen


def cmd_fuzz(args: argparse.Namespace) -> int:
  anomalies = 0
  tally = {"solvable": 0, "unsolvable": 0, "unknown": 0, "split": 0}
  for k in range(args.instances):
    seed = args.seed + k
    base, problem = random_problem(random.Random(seed))
    assert not reciprocity_errors(problem.tiles), seed
    if len(reachable(problem)) != len(problem.free_cells()):
      tally["split"] += 1                # known issue: the BFS never reaches the other region
      continue
    verdict = solve(problem, 200_000)
    tally[verdict.status] += 1
    if verdict.status == "unknown":
      continue
    limit = None if verdict.status == "solvable" else args.limit
    runs = trials(problem, args.trials, seed, limit, args.tick_cap)
    report = describe(problem, verdict, runs, args.limit if limit else 10**9)
    flagged = [line for line in report if line.startswith(("BUG", "WARNING"))]
    if verdict.status == "solvable" and any(r.outcome != "done" for r in runs):
      stuck = sum(r.outcome != "done" for r in runs)
      flagged.append(f"POSSIBLE TRAP: {stuck}/{len(runs)} runs didn't finish in {args.tick_cap} steps")
    if not flagged:
      continue
    anomalies += 1
    cmd = (f"uv run sim/simulate.py run {args.dump}/fuzz{seed}.csv --size "
           f"{' '.join(map(str, problem.size))}"
           + "".join(f" --constraint {x},{y},{z}" for x, y, z in sorted(problem.constraints)))
    print(f"instance {seed} ({verdict.status}): {'; '.join(flagged)}")
    print(f"  {cmd}")
    if args.dump:
      Path(args.dump).mkdir(parents=True, exist_ok=True)
      write_csv(base, Path(args.dump) / f"fuzz{seed}.csv")
  print(f"{args.instances} instances: {tally['solvable']} solvable, {tally['unsolvable']} unsolvable, "
        f"{tally['unknown']} unknown, {tally['split']} skipped (constraints split the grid); "
        f"{anomalies} with anomalies")
  return 1 if anomalies else 0


# --------------------------------------------------------------------------------------------- main

def main(argv: list[str]) -> int:
  parser = argparse.ArgumentParser(prog="uv run sim/simulate.py", description=__doc__.split("\n")[0])
  sub = parser.add_subparsers(dest="command", required=True)

  check = sub.add_parser("check", help="expand rotations and validate a cell-type CSV")
  check.add_argument("csv", type=Path)
  check.add_argument("--wall", default=WALL)

  run = sub.add_parser("run", help="exact verdict plus simulated runs")
  run.add_argument("csv", type=Path)
  run.add_argument("--size", type=int, nargs=3, required=True, metavar=("X", "Y", "Z"))
  run.add_argument("--constraint", type=parse_pos, action="append", default=[], metavar="x,y,z")
  run.add_argument("--wall", default=WALL)
  run.add_argument("--trials", type=int, default=200)
  run.add_argument("--seed", type=int, default=0)
  run.add_argument("--limit-max", type=int, default=64,
                   help="runs stop once an edit passes this; also the largest LIMIT reported")
  run.add_argument("--tick-cap", type=int, default=200_000)
  run.add_argument("--budget", type=int, default=2_000_000, help="exact solver search nodes")
  run.add_argument("--witness", action="store_true", help="print one valid filling")
  run.add_argument("--trace", type=int, nargs="?", const=200, metavar="STEPS",
                   help="print the first STEPS steps of run 0")
  run.add_argument("--allow-nonreciprocal", action="store_true")

  fuzz = sub.add_parser("fuzz", help="random small inputs, looking for wrong answers or traps")
  fuzz.add_argument("--instances", type=int, default=300)
  fuzz.add_argument("--trials", type=int, default=20)
  fuzz.add_argument("--seed", type=int, default=0)
  fuzz.add_argument("--limit", type=int, default=16, help="LIMIT used on unsolvable inputs")
  fuzz.add_argument("--tick-cap", type=int, default=20_000)
  fuzz.add_argument("--dump", default="sim/fuzz", help="where to write CSVs of flagged instances")

  args = parser.parse_args(argv)
  try:
    return {"check": cmd_check, "run": cmd_run, "fuzz": cmd_fuzz}[args.command](args)
  except TileError as e:
    print(f"error: {e}", file=sys.stderr)
    return 2


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
