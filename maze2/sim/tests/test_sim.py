"""Tests for the maze2 simulator: tile handling, the exact solver, and the algorithm model."""

import csv
import io
import random
import re
from pathlib import Path

import pytest

from algo import Algorithm, Node, Queue, pick
from simulate import main, random_problem, reachable
from solver import check_filling, solve
from tiles import (D, E, N, S, U, W, WALL, Problem, Tile, TileError, encoding_ids, lint, matches, read_csv, sheet,
                   reciprocity_errors, rotate, rotations, write_csv)


def tile(name: str, phys: list[str], targets: list[list[str]], categories: tuple[str, ...] = ()) -> Tile:
  return Tile(name, 0, tuple(phys), tuple(tuple(t) for t in targets), categories)

def walled(name: str, **open_faces: str) -> Tile:
  """A tile that is `wall` (targeting `wall`) everywhere except the named faces, which use the
  given encoding and target themselves."""
  dirs = ["north", "east", "south", "west", "up", "down"]
  phys = [open_faces.get(d, WALL) for d in dirs]
  return tile(name, phys, [[e] for e in phys])

OPEN_4WAY = tile("maze:open_4way", ["open"] * 4 + ["ceiling", "floor"],
                 [["open"]] * 4 + [["floor"], ["ceiling"]])
HALF = walled("half", north="join")                      # a horizontal domino half
HALF_UP = walled("half_up", up="join")
HALF_DOWN = walled("half_down", down="join")
SOLID = walled("solid")

def problem(base: list[Tile], size: tuple[int, int, int], *constraints) -> Problem:
  return Problem([r for t in base for r in rotations(t)], size, frozenset(constraints))


# -------------------------------------------------------------------------------------------- tiles

def test_rotate_moves_north_to_east_and_keeps_vertical():
  t = tile("t", ["n", "e", "s", "w", "u", "d"], [["tn"], ["te"], ["ts"], ["tw"], ["tu"], ["td"]])
  r = rotate(t)
  assert r.rotation == 90
  assert r.phys == ("w", "n", "e", "s", "u", "d")
  assert r.targets[E] == ("tn",) and r.targets[U] == ("tu",)
  assert rotate(rotate(rotate(r))).phys == t.phys

def test_rotations_match_the_lookups_rooms_py_builds():
  room = sheet.Room(3, "t", 0, [], ["n", "e", "s", "w", "u", "d"],
                    [["tn"], ["te", "x"], ["ts"], ["tw"], ["tu"], ["td"]])
  t = tile("t", room.sides, room.targets)
  for lookup, r in zip(sheet.lookups([room]), rotations(t)):
    assert tuple(lookup.sides) == r.phys
    assert tuple(tuple(x) for x in lookup.targets) == r.targets

def csv_row(name: str, sides: list[str], targets: list[list[str]], inner: dict[int, str] = {},
            rot: dict[int, str] = {}) -> list[str]:
  """One room in the room CSV layout. `inner` and `rot` map a direction to its In or Rot cell."""
  return (["0", "", name, *sides, *(inner.get(d, "") for d in range(6)), rot.get(U, ""), rot.get(D, ""),
           *(", ".join(t) for t in targets)])

def write_rows(path: Path, rows: list[list[str]]) -> None:
  with open(path, "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([sheet.CSV_HEADER, *rows])

def test_reads_the_room_sheet(tmp_path: Path):
  path = tmp_path / "rooms.csv"
  write_rows(path, [csv_row("maze:open_4way", list(OPEN_4WAY.phys), [list(t) for t in OPEN_4WAY.targets],
                            {N: "FALSE"}),
                    [""] * len(sheet.CSV_HEADER)])
  tiles = read_csv(path)
  assert len(tiles) == 4
  assert tiles[0] == OPEN_4WAY

def test_rejects_the_old_layout(tmp_path: Path):
  path = tmp_path / "rooms.csv"
  path.write_text("Room Weight,Categories,Structure Name,North,East,South,West,Up,Down,"
                  "Target North,Target East,Target South,Target West,Target Up,Target Down\n", encoding="utf-8")
  with pytest.raises(TileError, match="the header doesn't match the room CSV layout"):
    read_csv(path)

def test_csv_round_trip_keeps_target_order_and_categories(tmp_path: Path):
  t = tile("t", ["a", "b", "c", "d", "e", "f"], [["c", "a", "b"], ["b"], ["c", "a"], ["d"], ["f"], ["e"]],
           ("one", "two"))
  solid = tile("solid", [WALL] * 6, [[WALL]] * 6, ("two",))
  write_csv([t, solid], tmp_path / "t.csv")
  back = read_csv(tmp_path / "t.csv")
  assert back[::4] == [t, solid]
  assert back[0].targets[N] == ("c", "a", "b")
  assert back[0].categories == ("one", "two")
  assert read_csv(tmp_path / "t.csv", ["one"])[::4] == [t]
  assert read_csv(tmp_path / "t.csv", ["two"])[::4] == [t, solid]
  with pytest.raises(TileError, match="no rooms in categories"):
    read_csv(tmp_path / "t.csv", ["three"])
  ids = encoding_ids(tmp_path / "t.csv")
  assert ids[WALL] == 0  # the constraint encoding is always 0, even when it appears after others
  assert ids["a"] == 1

def test_sheet_errors_are_reported(tmp_path: Path):
  path = tmp_path / "t.csv"
  write_csv([tile("solid", [WALL] * 6, [[WALL]] * 5 + [[]])], path)
  with pytest.raises(TileError, match="down target list is empty"):
    read_csv(path)

STAIR_BOTTOM = walled("stair_bottom", up="stair")
STAIR_TOP = walled("stair_top", down="stair")

def test_rotating_encodings_turn_with_the_room(tmp_path: Path):
  write_csv([STAIR_BOTTOM, STAIR_TOP], tmp_path / "t.csv", rotating={"stair"})
  tiles = read_csv(tmp_path / "t.csv")
  bottoms, tops = tiles[:4], tiles[4:]
  assert [t.phys[U] for t in bottoms] == ["stair_R0", "stair_R90", "stair_R180", "stair_R270"]
  assert [t.targets[D] for t in tops] == [("stair_R0",), ("stair_R90",), ("stair_R180",), ("stair_R270",)]
  for bottom in bottoms:
    assert [top.rotation for top in tops if matches(bottom, U, top)] == [bottom.rotation]
  assert reciprocity_errors(tiles) == []
  assert solve(Problem(tiles, (1, 2, 1))).status == "solvable"

def test_rotating_encodings_take_4_ids_in_rotation_order(tmp_path: Path):
  write_csv([STAIR_BOTTOM, STAIR_TOP], tmp_path / "t.csv", rotating={"stair"})
  ids = encoding_ids(tmp_path / "t.csv")
  assert [ids[f"stair_R{d}"] for d in (0, 90, 180, 270)] == [ids[WALL] + k for k in range(1, 5)]
  assert "stair" not in ids

def test_in_encodings_are_numbered_from_1001(tmp_path: Path):
  write_csv([walled("half", north="join"), STAIR_BOTTOM, OPEN_4WAY, STAIR_TOP], tmp_path / "t.csv",
            inner={"join", "stair"}, rotating={"stair"})
  ids = encoding_ids(tmp_path / "t.csv")
  assert ids["join"] == sheet.INNER_FIRST_ID == 1001
  assert [ids[f"stair_R{d}"] for d in (0, 90, 180, 270)] == [1002, 1003, 1004, 1005]
  assert [ids[e] for e in ("open", "ceiling", "floor")] == [1, 2, 3]  # In encodings don't use up the low ids
  assert ids[WALL] == 0

def test_in_encodings_reach_the_lookups(tmp_path: Path):
  rooms, errors = sheet.parse_rooms(list(csv.reader(io.StringIO(
    "\n".join(",".join(row) for row in [sheet.CSV_HEADER,
      csv_row("a", ["join", WALL, WALL, WALL, WALL, WALL], [["join"]] + [[WALL]] * 5, {N: "TRUE"})])))))
  assert errors == []
  text = sheet.lookups_ir(sheet.lookups(rooms), sheet.encoding_ids(rooms))
  assert "@e[type=item_display,name=lookup,tag=new] north 1001" in text
  assert "@e[type=item_display,name=lookup,tag=new] target_north1 1001" in text
  assert "@e[type=item_display,name=lookup,tag=new] east 1001" in text  # turned once: north moved to east

def test_too_many_encodings_without_in(tmp_path: Path):
  rooms = [tile(f"r{i}", [f"e{i}_{d}" for d in range(6)], [[f"e{i}_{d}"] for d in range(6)]) for i in range(167)]
  write_csv(rooms, tmp_path / "t.csv")
  with pytest.raises(TileError, match="1002 encodings without In, the most is 1000"):
    read_csv(tmp_path / "t.csv")

@pytest.mark.parametrize("rows, message", [
  ([csv_row("bottom", [WALL] * 4 + ["stair", WALL], [[WALL]] * 4 + [["stair"], [WALL]], rot={U: "TRUE"}),
    csv_row("top", [WALL] * 5 + ["stair"], [[WALL]] * 5 + [["stair"]])],
   "row 3 (top): down encoding 'stair' does not rotate, but on up in row 2 (bottom) it does."),
  ([csv_row("a", ["join"] + [WALL] * 5, [["join"]] + [[WALL]] * 5, {N: "TRUE"}),
    csv_row("b", ["join"] + [WALL] * 5, [["join"]] + [[WALL]] * 5)],
   "row 3 (b): north encoding 'join' has In unchecked, but on north in row 2 (a) it's checked"),
  ([csv_row("a", [WALL] * 6, [[WALL]] * 6, {E: "TRUE"})], "east is constraint, which can't be In or Rot"),
  ([csv_row("a", [WALL] * 6, [[WALL]] * 6, rot={D: "TRUE"})], "down is constraint, which can't be In or Rot"),
  ([csv_row("a", [WALL] * 6, [[WALL]] * 6, {W: "yes"})], "In west is 'yes', it must be TRUE, FALSE or blank"),
  ([csv_row("a", [WALL] * 6, [[WALL]] * 6) + ["maybe"]], "Disabled is 'maybe', it must be TRUE, FALSE or blank"),
  ([csv_row("bottom", [WALL] * 4 + ["stair", WALL], [[WALL]] * 4 + [["stair"], [WALL]], rot={U: "TRUE"}),
    csv_row("t", ["stair_R90"] + [WALL] * 5, [["stair_R90"]] + [[WALL]] * 5)],
   "encoding 'stair_R90' has the same name as a variant of the rotating encoding 'stair'"),
  # In still has to agree within an axis
  ([csv_row("a", [WALL] * 4 + ["lift", WALL], [[WALL]] * 4 + [["lift"], [WALL]], {U: "TRUE"}),
    csv_row("b", [WALL] * 5 + ["lift"], [[WALL]] * 5 + [["lift"]])],
   "row 3 (b): down encoding 'lift' has In unchecked, but on up in row 2 (a) it's checked"),
  # a name on both axes that doesn't rotate shares one id, so In has to agree across the axes too
  ([csv_row("a", ["join"] + [WALL] * 3 + ["join", WALL], [["join"]] + [[WALL]] * 3 + [[WALL], [WALL]], {N: "TRUE"})],
   "encoding 'join' has In checked on one axis but not the other"),
])
def test_flag_errors(tmp_path: Path, rows: list[list[str]], message: str):
  write_rows(tmp_path / "t.csv", rows)
  with pytest.raises(TileError, match=re.escape(message)):
    read_csv(tmp_path / "t.csv")

def test_axes_have_separate_encodings(tmp_path: Path):
  # `link` joins two halves horizontally without rotating, and is also a rotating, In stair link on up/down
  write_rows(tmp_path / "t.csv", [
    csv_row("half", ["link"] + [WALL] * 3 + ["link", WALL], [["link"]] + [[WALL]] * 3 + [["link"], [WALL]],
            {U: "TRUE"}, {U: "TRUE"}),
    csv_row("top", [WALL] * 5 + ["link"], [[WALL]] * 5 + [["link"]], {D: "TRUE"}, {D: "TRUE"})])
  tiles = read_csv(tmp_path / "t.csv")
  halves, tops = tiles[:4], tiles[4:]
  assert [t.phys[U] for t in halves] == ["link_R0", "link_R90", "link_R180", "link_R270"]
  assert [t.targets[D] for t in tops] == [("link_R0",), ("link_R90",), ("link_R180",), ("link_R270",)]
  assert halves[1].phys[E] == "link" and halves[1].targets[E] == ("link",)  # horizontal: never a variant
  ids = encoding_ids(tmp_path / "t.csv")
  assert ids["link"] == 1  # horizontal, not In
  assert [ids[f"link_R{d}"] for d in (0, 90, 180, 270)] == [1001, 1002, 1003, 1004]

def test_a_shared_name_that_does_not_rotate_shares_its_id(tmp_path: Path):
  write_rows(tmp_path / "t.csv", [
    csv_row("a", ["open"] * 4 + ["open", WALL], [["open"]] * 4 + [["open"], [WALL]]),
    csv_row("b", [WALL] * 5 + ["open"], [[WALL]] * 5 + [["open"]])])
  ids = encoding_ids(tmp_path / "t.csv")
  assert ids == {WALL: 0, "open": 1}

def test_targets_get_their_flags_from_the_encoding(tmp_path: Path):
  # only the This sides have boxes: `top` targets the rotating `stair` without saying so
  write_rows(tmp_path / "t.csv", [
    csv_row("bottom", [WALL] * 4 + ["stair", WALL], [[WALL]] * 4 + [["stair"], [WALL]], {U: "TRUE"}, {U: "TRUE"}),
    csv_row("top", [WALL] * 5 + ["stair"], [[WALL]] * 5 + [["stair"]], {D: "TRUE"}, {D: "TRUE"})])
  tops = read_csv(tmp_path / "t.csv")[4:]
  assert [t.targets[D] for t in tops] == [("stair_R0",), ("stair_R90",), ("stair_R180",), ("stair_R270",)]
  assert encoding_ids(tmp_path / "t.csv")["stair_R0"] == 1001

def test_unmatched_targets():
  # `x` is an own encoding on north only, so a down target of `x` can never match, but a horizontal one can
  rooms = [sheet.Room(2, "t", 0, [], ["x", WALL, WALL, WALL, WALL, WALL], [["x"], [WALL], [WALL], [WALL], [WALL], ["x", WALL]])]
  assert sheet.unmatched_targets(rooms) == ["row 2 (t): down target 'x' is no room's own encoding on up, so it can never match"]

def test_unmatched_targets_are_errors(tmp_path: Path):
  write_rows(tmp_path / "t.csv", [csv_row("t", ["x"] + [WALL] * 5, [["x"]] + [[WALL]] * 4 + [["x", WALL]])])
  with pytest.raises(TileError, match=re.escape("down target 'x' is no room's own encoding on up")):
    read_csv(tmp_path / "t.csv")

def test_the_test_rooms_build():
  # make_cases.py's rooms are pasted into the sheet for the in-game tests, so they have to pass every check
  rows = list(csv.reader(open(Path(__file__).parents[2] / "manual_test" / "test_rooms.csv", encoding="utf-8")))
  rooms, errors = sheet.parse_rooms(rows)
  assert errors == [] and len(rooms) == 35


# ------------------------------------------------------------------------------------- sheet layout

SHEET_HEADER = ["Structure Name", "", "Maze1?", "Ignore", "Room Weight", "Categories", "North", "In?", "East",
                "In?", "South", "In?", "West", "In?", "Up", "In?", "Rot?", "Down", "In?", "Rot?", "Disabled", "Errors"]

def sheet_pair(name: str, phys: list[str], targets: list[str], inner: list[str], rot: list[str],
               ignore: str = "FALSE", disabled: str = "FALSE") -> list[list[str]]:
  """A This row and its Target row in the Google sheet's layout."""
  this = [name, "This", "TRUE", ignore, "0", "cat"] if name else ["", "This", "", "", "", ""]
  target = ["", "Target", "", "", "", ""]
  for d in range(6):
    this += [phys[d], inner[d]] + ([rot[d - 4]] if d >= 4 else [])
    target += [targets[d], ""] + ([""] if d >= 4 else [])
  this.append(disabled if name else "")
  return [this, target]

def test_converts_the_sheet_layout():
  rows = [SHEET_HEADER,
          *sheet_pair("maze:a", ["open"] * 4 + ["lift", "lift"], ["open"] * 4 + ["lift, constraint", "lift"],
                      ["FALSE"] * 4 + ["TRUE", "TRUE"], ["TRUE", "TRUE"]),
          *sheet_pair("", [""] * 6, [""] * 6, ["FALSE"] * 6, ["FALSE"] * 2)]  # an empty pair, like the sheet's tail
  converted = sheet.convert_sheet(rows)
  assert converted[0] == sheet.CSV_HEADER
  assert len(converted) == len(rows)  # row numbers still match the sheet
  assert converted[2] == [""] * len(sheet.CSV_HEADER)
  rooms, errors = sheet.parse_rooms(converted)
  assert errors == []
  [room] = rooms
  assert room.row == 2 and room.categories == ["cat"]
  assert room.inner == [False] * 4 + [True, True] and room.rot == [False] * 4 + [True, True]
  assert room.targets[U] == ["lift", WALL]
  assert sheet.lookups(rooms)[1].sides[U] == "lift_R90"
  assert sheet.encoding_ids(rooms)["lift_R0"] == 1001

def test_ignored_rooms_are_left_out():
  # `b` has a target nothing has, but it's ignored, so it isn't checked either
  rows = [SHEET_HEADER,
          *sheet_pair("maze:a", ["open"] * 6, ["open"] * 6, ["FALSE"] * 6, ["FALSE"] * 2),
          *sheet_pair("maze:b", ["open"] * 6, ["nowhere"] * 6, ["FALSE"] * 6, ["FALSE"] * 2, ignore="TRUE")]
  converted = sheet.convert_sheet(rows)
  assert len(converted) == len(rows)
  assert converted[3] == converted[4] == [""] * len(sheet.CSV_HEADER)
  rooms, errors = sheet.parse_rooms(converted)
  assert errors == [] and [room.name for room in rooms] == ["maze:a"]

def test_disabled_rooms_start_without_the_enabled_tag():
  rows = [SHEET_HEADER,
          *sheet_pair("maze:a", ["open"] * 6, ["open"] * 6, ["FALSE"] * 6, ["FALSE"] * 2),
          *sheet_pair("maze:b", ["open"] * 6, ["open"] * 6, ["FALSE"] * 6, ["FALSE"] * 2, disabled="TRUE")]
  rooms, errors = sheet.parse_rooms(sheet.convert_sheet(rows))
  assert errors == [] and [room.disabled for room in rooms] == [False, True]
  summons = [line for line in sheet.lookups_ir(sheet.lookups(rooms), sheet.encoding_ids(rooms)).splitlines()
             if line.startswith("summon")]
  assert len(summons) == 8  # disabled rooms are still built
  assert all("Tags:[new,enabled,cat_cat]" in line for line in summons[:4])
  assert all("Tags:[new,cat_cat]" in line for line in summons[4:])

@pytest.mark.parametrize("rows, message", [
  ([SHEET_HEADER, *sheet_pair("maze:a", ["open"] * 6, ["open"] * 6, ["FALSE"] * 6, ["FALSE"] * 2, ignore="maybe")],
   "row 2: Ignore is 'maybe', it must be TRUE, FALSE or blank"),
  ([SHEET_HEADER, ["maze:a", "This"]], "row 2: a This row needs a Target row right under it"),
  ([SHEET_HEADER, ["maze:a", "This"], ["", "Target"], ["", "Target"]],
   "row 4: a Target row has to be right under a This row"),
  ([SHEET_HEADER, ["maze:a", "This"], ["", "Target"], ["maze:b"]], "row 4: has data but isn't marked This or Target"),
  ([[c for c in SHEET_HEADER if c != "Rot?"], ["maze:a", "This"], ["", "Target"]], "expected 'Rot?' 2 column(s) after 'Up'"),
])
def test_sheet_layout_errors(rows: list[list[str]], message: str):
  with pytest.raises(ValueError, match=re.escape(message)):
    sheet.convert_sheet(rows)

def test_reciprocity():
  assert reciprocity_errors(problem([OPEN_4WAY, HALF, SOLID], (1, 1, 1)).tiles) == []
  # 'x' accepts 'y' on the north, but the 'y' face doesn't accept 'x' back
  bad = tile("bad", ["x", WALL, "y", WALL, WALL, WALL], [["y"], [WALL], ["y"], [WALL], [WALL], [WALL]])
  assert reciprocity_errors(rotations(bad))
  # a wall face that doesn't target wall can't be reciprocal with a constraint
  leaky = tile("leaky", [WALL] * 6, [["open"]] + [[WALL]] * 5)
  assert any(f"vs {WALL}" in e for e in reciprocity_errors(rotations(leaky)))

def test_lint_catches_near_identical_encodings():
  near = WALL.title()
  t = tile("t", [near, WALL, WALL, WALL, WALL, WALL], [[near]] + [[WALL]] * 5)
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
  # walled tiles tie a lot (every wall face is id 0), so this also covers tied neighbors being pushed
  p = problem([HALF, HALF_UP, HALF_DOWN], (2, 2, 3))
  algo = Algorithm(p)
  for seed in range(300):
    run = algo.run(random.Random(seed), None, 100_000)
    assert run.outcome == "done"
    assert check_filling(p, run.grid) == ([], []), seed

def test_never_finishes_valid_when_unsolvable():
  for p in (problem([OPEN_4WAY], (2, 1, 2)), problem([HALF], (3, 1, 3)),
            problem([HALF], (4, 1, 4), (0, 0, 3), (3, 0, 0))):
    for seed in range(10):
      run = Algorithm(p).run(random.Random(seed), 8, 100_000)
      assert run.outcome == "error" or check_filling(p, run.grid) != ([], [])

def test_a_select_with_nothing_to_ignore_gives_up():
  # no lookup fits the walls, and constraints are never ignored, so every cell gives up untouched
  p = problem([OPEN_4WAY], (2, 1, 2))
  trace = []
  run = Algorithm(p).run(random.Random(0), 8, 1000, trace)
  assert run.outcome == "done"
  assert set(run.grid.values()) == {None}
  assert all(e.gave_up and e.candidates == 0 for e in trace)

def test_first_cell_sees_unfilled_neighbors_as_wildcards():
  p = problem([HALF], (2, 1, 1))
  trace = []
  Algorithm(p).run(random.Random(0), None, 1000, trace)
  first = trace[0]
  assert first.popped and first.ignored == []
  assert first.candidates == 1                 # only the rotation facing east fits the walls
  assert first.placed == "half@90"
  assert first.pushed == [(1, 0, 0)]

def test_each_failed_filter_ignores_the_next_side_by_the_next_tick():
  for seed in range(20):
    _, p = random_problem(random.Random(seed))
    trace = []
    Algorithm(p).run(random.Random(seed), 12, 2_000, trace)
    for prev, e in zip(trace, trace[1:]):
      if e.popped:
        assert e.ignored == []               # a new select's first filter checks every side
      else:
        assert e.pos == prev.pos
        assert e.ignored == prev.ignored + prev.relaxed

def test_pick_takes_the_highest_roll_plus_weight():
  heavy = Tile("heavy", 0, (WALL,) * 6, ((WALL,),) * 6, weight=100)
  light = Tile("light", 0, (WALL,) * 6, ((WALL,),) * 6, weight=-100)
  rng = random.Random(0)
  assert {pick(0b11, [light, heavy], rng) for _ in range(200)} == {1}  # 100..200 always beats -100..0
  assert {pick(0b11, [light, light], rng) for _ in range(200)} == {0, 1}

def test_split_grid_finishes_with_unreached_cells():
  """Known issue: the BFS can't cross a wall of constraints, so the far side is never filled."""
  p = problem([SOLID], (3, 1, 1), (1, 0, 0))
  assert reachable(p) == {(0, 0, 0)}
  run = Algorithm(p).run(random.Random(0), None, 1000)
  assert run.outcome == "done"
  assert check_filling(p, run.grid)[0] == [(2, 0, 0)]

def test_a_valid_finish_agrees_with_the_solver():
  for seed in range(150):
    _, p = random_problem(random.Random(seed))
    if len(reachable(p)) != len(p.free_cells()):
      continue
    verdict = solve(p, 50_000)
    if verdict.status == "unknown":
      continue
    for k in range(3):
      run = Algorithm(p).run(random.Random(k), 12, 5_000)
      if run.outcome == "done" and check_filling(p, run.grid) == ([], []):
        assert verdict.status == "solvable", seed


# -------------------------------------------------------------------------------------------- CLI

def test_run_command_reports_unsolvable(tmp_path: Path, capsys):
  write_csv([HALF], tmp_path / "half.csv")
  code = main(["run", str(tmp_path / "half.csv"), "--size", "3", "1", "3", "--trials", "5",
               "--limit-max", "4"])
  out = capsys.readouterr().out
  assert "exact solver: unsolvable" in out
  assert "5 runs: 0 finished" in out
  assert "BUG" not in out
  # some runs give up and empty the queue instead of passing LIMIT, which is flagged
  assert code == (1 if "WARNING" in out else 0)

def test_run_command_rejects_nonreciprocal(tmp_path: Path):
  leaky = tile("leaky", [WALL] * 6, [["open"]] + [[WALL]] * 5)
  write_csv([leaky, OPEN_4WAY], tmp_path / "leaky.csv")
  with pytest.raises(SystemExit):
    main(["run", str(tmp_path / "leaky.csv"), "--size", "1", "1", "1"])
