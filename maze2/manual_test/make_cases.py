"""Writes the in-game test rooms for maze2 to maze2/manual_test/test_rooms.csv (the room CSV layout in rooms.py).

  uv run poe cases

Every test is one category, so the sheet is compiled once and each test is run by enabling only its
category. See TESTS.md for what each test checks and how to run it.

Encodings: constraint (the wall encoding, which rooms.py always numbers 0, so rooms can sit against
constraint nodes), open, door, hatch, join, and the t_tri end and mid encodings.
"""

import sys
from pathlib import Path

PY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PY / "sim"))
sys.path.insert(0, str(PY / "rooms"))
from rooms import CONSTRAINT_ENCODING  # noqa: E402
from tiles import Tile, write_csv  # noqa: E402

# walls use the constraint encoding: constraint nodes only accept id 0, so any face that can end up
# against the maze bounds has to be it
WALL = CONSTRAINT_ENCODING

OUT = Path(__file__).with_name("test_rooms.csv")

# horizontal shapes: which of N E S W are open. Rotations make every other arrangement.
SHAPES = {
  "closed": (0, 0, 0, 0),
  "deadend": (1, 0, 0, 0),
  "corner": (1, 1, 0, 0),
  "straight": (1, 0, 1, 0),
  "tee": (1, 1, 1, 0),
  "cross": (1, 1, 1, 1),
}
# basic rooms that also make up t_nofit: none of them has two adjacent walls, so no corner of the
# grid can be filled
NOFIT = {"straight", "tee", "cross"}


def room(name: str, phys: list[str], targets: list[list[str]], categories: list[str]) -> Tile:
  return Tile(name, 0, tuple(phys), tuple(tuple(t) for t in targets), tuple(categories))


def basic() -> list[Tile]:
  """t_basic: every horizontal wall/open arrangement, as a bottom layer room (down is wall, up is
  open) and a top layer room (up is wall, down is open). Every target list has one entry.
  Whatever the filled neighbors need, some room fits, so the algorithm never has to edit."""
  rooms = []
  for layer, (up, down) in (("bottom", ("open", WALL)), ("top", (WALL, "open"))):
    for shape, opens in SHAPES.items():
      phys = ["open" if o else WALL for o in opens] + [up, down]
      cats = ["t_basic"] + (["t_nofit"] if shape in NOFIT else [])
      rooms.append(room(f"test:basic_{shape}_{layer}", phys, [[e] for e in phys], cats))
  return rooms


def slots() -> list[Tile]:
  """t_slots: the same rooms, but every target list has 3 entries and the real match is never in
  slot 1. Doors match in slot 3, walls and hatches in slot 2. The other entries are encodings no
  t_slots room has (open, join), so they can never match."""
  targets = {
    "door": ["join", "open", "door"],
    WALL: ["open", WALL, "join"],
    "hatch": ["join", "hatch", "open"],
  }
  rooms = []
  for layer, (up, down) in (("bottom", ("hatch", WALL)), ("top", (WALL, "hatch"))):
    for shape, opens in SHAPES.items():
      phys = ["door" if o else WALL for o in opens] + [up, down]
      rooms.append(room(f"test:slots_{shape}_{layer}", phys, [targets[e] for e in phys], ["t_slots"]))
  return rooms


def domino() -> list[Tile]:
  """t_domino: halves of a domino. Each room joins exactly one neighbor (north, up or down) and is
  wall everywhere else, so a valid filling pairs up every cell. That needs an even number of cells
  and, on a checkerboard colouring, as many of one colour as the other."""
  rooms = []
  for name, side in (("half", 0), ("half_up", 4), ("half_down", 5)):
    phys = [WALL] * 6
    phys[side] = "join"
    rooms.append(room(f"test:domino_{name}", phys, [[e] for e in phys], ["t_domino"]))
  return rooms


def tri() -> list[Tile]:
  """t_tri: triominoes, built from ends and middles. A middle piece has two `mid` faces, each of
  which accepts any of 3 end encodings, and an end has one face that accepts only `mid`. Ends never
  join ends, and middles never join middles, so every piece is end-middle-end: 3 cells.

  Unlike the earlier tests, matching faces have different encodings (end_side meets mid), and the
  mid lists have 3 targets. Each end encoding only exists on one side of one room, so which slot of
  the mid list matches depends on where the end is: below the middle is slot 1, beside it slot 2,
  above it slot 3. The other slots hold encodings that other tests' rooms have on the side the mid
  face meets (so rooms.py accepts them), but no t_tri room has, so they never match in this test."""
  N, E, S, U, D = 0, 1, 2, 4, 5
  mid_targets = {
    D: ["end_up", "open", "hatch"], # meets the up face of the room below
    "side": ["open", "end_side", "door"],
    U: ["open", "hatch", "end_down"], # meets the down face of the room above
  }

  def piece(name: str, faces: dict[int, str]) -> Tile:
    phys = [faces.get(side, WALL) for side in range(6)]
    targets = [mid_targets[side if side in (U, D) else "side"] if e == "mid" else ["mid"] if e.startswith("end_")
               else [WALL] for side, e in enumerate(phys)]
    return room(f"test:tri_{name}", phys, targets, ["t_tri"])

  return [
    piece("end_side", {N: "end_side"}),
    piece("end_up", {U: "end_up"}),
    piece("end_down", {D: "end_down"}),
    piece("mid_straight", {N: "mid", S: "mid"}),
    piece("mid_corner", {N: "mid", E: "mid"}),
    piece("mid_side_up", {N: "mid", U: "mid"}),
    piece("mid_side_down", {N: "mid", D: "mid"}),
    piece("mid_up_down", {U: "mid", D: "mid"}),
  ]


def all_rooms() -> list[Tile]:
  return basic() + slots() + domino() + tri()


if __name__ == "__main__":
  rooms = all_rooms()
  write_csv(rooms, OUT)
  print(f"wrote {OUT} ({len(rooms)} rooms)")
