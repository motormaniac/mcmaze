"""Tests for the maze2 simulator: tile handling, the exact solver, and the algorithm model."""

import random
from pathlib import Path

import pytest

from algo import Algorithm, Node, Queue
from simulate import main, random_problem, reachable
from solver import check_filling, solve
from tiles import (D, E, N, S, U, W, WALL, Problem, Tile, TileError, lint, read_csv,
                   reciprocity_errors, rotate, rotations, write_csv)


def tile(name: str, phys: list[str], targets: list[set[str]]) -> Tile:
  return Tile(name, 0, tuple(phys), tuple(frozenset(t) for t in targets))

def walled(name: str, **open_faces: str) -> Tile:
  """A tile that is `wall` (targeting `wall`) everywhere except the named faces, which use the
  given encoding and target themselves."""
  dirs = ["north", "east", "south", "west", "up", "down"]
  phys = [open_faces.get(d, WALL) for d in dirs]
  return tile(name, phys, [{e} for e in phys])

OPEN_4WAY = tile("maze:open_4way", ["open"] * 4 + ["ceiling", "floor"],
                 [{"open"}] * 4 + [{"floor"}, {"ceiling"}])
HALF = walled("half", north="join")                      # a horizontal domino half
HALF_UP = walled("half_up", up="join")
HALF_DOWN = walled("half_down", down="join")
SOLID = walled("solid")

def problem(base: list[Tile], size: tuple[int, int, int], *constraints) -> Problem:
  return Problem([r for t in base for r in rotations(t)], size, frozenset(constraints))


# -------------------------------------------------------------------------------------------- tiles

def test_rotate_moves_north_to_east_and_keeps_vertical():
  t = tile("t", ["n", "e", "s", "w", "u", "d"], [{"tn"}, {"te"}, {"ts"}, {"tw"}, {"tu"}, {"td"}])
  r = rotate(t)
  assert r.rotation == 90
  assert r.phys == ("w", "n", "e", "s", "u", "d")
  assert r.targets[E] == {"tn"} and r.targets[U] == {"tu"}
  assert rotate(rotate(rotate(r))).phys == t.phys

def test_reads_the_spreadsheet_layout(tmp_path: Path):
  path = tmp_path / "t.csv"
  path.write_text(
    ',"Instructions: ...",This Cell\'s Encoding,,,,,,Target Encoding1,,,,,,Target Encoding 2,,,,,,'
    'Target Encoding 3,,,,,,\n'
    'Error?,Structure Name,North,East,South,West,Up,Down,North,East,South,West,Up,Down,North,East,'
    'South,West,Up,Down,North,East,South,West,Up,Down,\n'
    ',maze:open_4way,open,open,open,open,ceiling,floor,open,open,open,open,floor,ceiling,'
    ',,,,,,,,,,,,FALSE\n'
    ',,,,,,,,,,,,,,,,,,,,,,,,,,FALSE\n', encoding="utf-8")
  tiles = read_csv(path)
  assert len(tiles) == 4
  assert tiles[0] == OPEN_4WAY

def test_csv_round_trip_keeps_optional_targets(tmp_path: Path):
  t = tile("t", ["a", "b", "c", "d", "e", "f"], [{"a", "b", "c"}, {"b"}, {"c", "a"}, {"d"}, {"e"}, {"f"}])
  write_csv([t, SOLID], tmp_path / "t.csv")
  assert read_csv(tmp_path / "t.csv")[::4] == [t, SOLID]

def test_blank_target_1_is_rejected(tmp_path: Path):
  path = tmp_path / "t.csv"
  write_csv([SOLID], path)
  text = path.read_text().replace(",solid," + "wall," * 6 + "wall,", ",solid," + "wall," * 6 + ",")
  path.write_text(text)
  with pytest.raises(TileError, match="blank Target 1 on north"):
    read_csv(path)

def test_reciprocity():
  assert reciprocity_errors(problem([OPEN_4WAY, HALF, SOLID], (1, 1, 1)).tiles) == []
  # 'x' accepts 'y' on the north, but the 'y' face doesn't accept 'x' back
  bad = tile("bad", ["x", WALL, "y", WALL, WALL, WALL], [{"y"}, {WALL}, {"y"}, {WALL}, {WALL}, {WALL}])
  assert reciprocity_errors(rotations(bad))
  # a wall face that doesn't target wall can't be reciprocal with a constraint
  leaky = tile("leaky", [WALL] * 6, [{"open"}] + [{WALL}] * 5)
  assert any("vs wall" in e for e in reciprocity_errors(rotations(leaky)))

def test_lint_catches_near_identical_encodings():
  t = tile("t", ["Wall", WALL, WALL, WALL, WALL, WALL], [{"Wall"}] + [{WALL}] * 5)
  assert any("case/whitespace" in n for n in lint(rotations(t)))


# ------------------------------------------------------------------------------------------- solver

@pytest.mark.parametrize("size, blocked, expected", [
  ((1, 1, 1), [], "unsolvable"),               # a lone half has nothing to join
  ((2, 1, 1), [], "solvable"),
  ((2, 1, 3), [], "solvable"),
  ((3, 1, 3), [], "unsolvable"),               # odd cell count
  ((4, 1, 4), [], "solvable"),
  ((4, 1, 4), [(0, 0, 3), (3, 0, 0)], "unsolvable"),   # opposite corners: same colour
  ((4, 1, 4), [(0, 0, 3), (3, 0, 3)], "solvable"),     # adjacent corners
])
def test_solver_on_dominoes(size, blocked, expected):
  assert solve(problem([HALF], size, *blocked)).status == expected

def test_solver_uses_vertical_faces():
  assert solve(problem([HALF], (1, 2, 1))).status == "unsolvable"
  assert solve(problem([HALF_UP, HALF_DOWN], (1, 2, 1))).status == "solvable"
  assert solve(problem([HALF_UP], (1, 2, 1))).status == "unsolvable"

def test_solver_solution_is_valid():
  p = problem([HALF, HALF_UP, HALF_DOWN], (3, 2, 3))
  v = solve(p)
  assert v.status == "solvable"
  assert check_filling(p, v.solution) == ([], [])


# ---------------------------------------------------------------------------------------- algorithm

def test_queue_ignores_repush_of_a_queued_node():
  q = Queue()
  a, b = Node((0, 0, 0)), Node((1, 0, 0))
  q.push(a), q.push(b), q.push(a)
  assert len(q) == 2
  assert q.pop() is a
  q.push(a)                                    # no longer queued, so this one counts
  assert [q.pop(), q.pop()] == [b, a]
  assert len(q) == 0

def test_finishes_with_a_valid_grid_when_solvable():
  p = problem([HALF, HALF_UP, HALF_DOWN], (2, 2, 3))
  algo = Algorithm(p)
  for seed in range(50):
    run = algo.run(random.Random(seed), None, 100_000)
    assert run.outcome == "done"
    assert check_filling(p, run.grid) == ([], [])

def test_errors_when_unsolvable():
  for p in (problem([OPEN_4WAY], (2, 1, 2)), problem([HALF], (3, 1, 3)),
            problem([HALF], (4, 1, 4), (0, 0, 3), (3, 0, 0))):
    for seed in range(10):
      run = Algorithm(p).run(random.Random(seed), 8, 100_000)
      assert run.outcome == "error" and run.peak_edit == 9

def test_first_cell_sees_unfilled_neighbors_as_wildcards():
  p = problem([HALF], (2, 1, 1))
  trace = []
  Algorithm(p).run(random.Random(0), None, 1000, trace)
  first = trace[0]
  assert first.level == 2
  assert first.candidates == 1                 # only the rotation facing east fits the walls
  assert first.pushed == [(1, 0, 0)]

def test_split_grid_finishes_with_unreached_cells():
  """Known issue: the BFS can't cross a wall of constraints, so the far side is never filled."""
  p = problem([SOLID], (3, 1, 1), (1, 0, 0))
  assert reachable(p) == {(0, 0, 0)}
  run = Algorithm(p).run(random.Random(0), None, 1000)
  assert run.outcome == "done"
  assert check_filling(p, run.grid)[0] == [(2, 0, 0)]

def test_random_inputs_never_give_a_wrong_answer():
  for seed in range(150):
    _, p = random_problem(random.Random(seed))
    if len(reachable(p)) != len(p.free_cells()):
      continue
    verdict = solve(p, 50_000)
    if verdict.status == "unknown":
      continue
    for k in range(3):
      run = Algorithm(p).run(random.Random(k), 12, 5_000)
      if run.outcome == "done":
        assert verdict.status == "solvable", seed
        assert check_filling(p, run.grid) == ([], []), seed


# -------------------------------------------------------------------------------------------- CLI

def test_run_command_reports_unsolvable(tmp_path: Path, capsys):
  write_csv([HALF], tmp_path / "half.csv")
  assert main(["run", str(tmp_path / "half.csv"), "--size", "3", "1", "3", "--trials", "5",
               "--limit-max", "4"]) == 0
  out = capsys.readouterr().out
  assert "exact solver: unsolvable" in out
  assert "5 passed LIMIT=4" in out

def test_run_command_rejects_nonreciprocal(tmp_path: Path):
  leaky = tile("leaky", [WALL] * 6, [{"open"}] + [{WALL}] * 5)
  write_csv([leaky], tmp_path / "leaky.csv")
  with pytest.raises(SystemExit):
    main(["run", str(tmp_path / "leaky.csv"), "--size", "1", "1", "1"])
