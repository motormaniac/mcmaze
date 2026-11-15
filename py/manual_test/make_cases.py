"""Writes the in-game test rooms for maze2 to manual_test/test_rooms.csv (room sheet layout).

  cd py
  uv run manual_test/make_cases.py

Every test is one category, so the sheet is compiled once and each test is run by enabling only its
category. See manual_test/TESTS.md for what each test checks and how to run it.

Encodings: wall (constraint encoding, id 0), open, door, hatch, join.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sim"))
from tiles import WALL, Tile, write_csv  # noqa: E402

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


def all_rooms() -> list[Tile]:
  return basic() + slots() + domino()


if __name__ == "__main__":
  rooms = all_rooms()
  write_csv(rooms, OUT)
  print(f"wrote {OUT} ({len(rooms)} rooms)")
