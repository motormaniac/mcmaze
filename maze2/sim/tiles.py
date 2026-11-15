"""Cell types, rotations, the maze problem, and input validation for the maze2 simulator.

Directions are indexed N, E, S, W, U, D = 0..5. North is -Z, east +X, south +Z, west -X, up +Y, down -Y.

Matching rule (from maze2/src/maze2.mct): a cell `a` may sit on side `d` of a filled cell `b` when
a.phys[d] is one of b.targets[opposite(d)]. The algorithm only checks that one half. Inputs must be
reciprocal, which makes the other half (b.phys[opp] in a.targets[d]) hold whenever the first does.

Constraint nodes (the maze bounds and any interior blockers) expose `wall` as their encoding and
target only `wall`, on every side.
"""

import csv
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path

DIRS = ("north", "east", "south", "west", "up", "down")
N, E, S, W, U, D = range(6)
OPP = (S, W, N, E, D, U)
OFFSET = ((0, 0, -1), (1, 0, 0), (0, 0, 1), (-1, 0, 0), (0, 1, 0), (0, -1, 0))
WALL = "wall"

Pos = tuple[int, int, int]


class TileError(Exception):
  pass


@dataclass(frozen=True)
class Tile:
  """One lookup: a cell type in one rotation."""
  name: str
  rotation: int                          # degrees clockwise seen from above: 0, 90, 180, 270
  phys: tuple[str, ...]                  # 6 encodings, indexed by direction
  targets: tuple[tuple[str, ...], ...]   # 6 non-empty target lists, in slot order
  categories: tuple[str, ...] = field(default=(), compare=False)

  @property
  def label(self) -> str:
    return f"{self.name}@{self.rotation}"


def rotate(tile: Tile) -> Tile:
  """Turns a tile 90 degrees clockwise seen from above: what faced north now faces east."""
  def turn(faces: tuple) -> tuple:
    return (faces[W], faces[N], faces[E], faces[S], faces[U], faces[D])
  return Tile(tile.name, (tile.rotation + 90) % 360, turn(tile.phys), turn(tile.targets),
              tile.categories)


def rotations(tile: Tile) -> list[Tile]:
  out = [tile]
  for _ in range(3):
    out.append(rotate(out[-1]))
  return out


def add(p: Pos, d: int) -> Pos:
  o = OFFSET[d]
  return (p[0] + o[0], p[1] + o[1], p[2] + o[2])


# ---------------------------------------------------------------------------------------- CSV input
# The room sheet is parsed by maze2/rooms/rooms.py, the same code that builds the in-game lookups.

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rooms"))
import rooms as sheet  # noqa: E402

WOOL = ("white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray", "light_gray",
        "cyan", "purple", "blue", "brown", "green", "red", "black")  # visualize.mct colors by id


def read_rooms(path: Path) -> list["sheet.Room"]:
  rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
  rooms, errors = sheet.parse_rooms(rows)
  if errors:
    raise TileError(f"{path}:\n  " + "\n  ".join(errors))
  return rooms


def read_csv(path: Path, categories: list[str] | None = None) -> list[Tile]:
  """Reads the room sheet and returns every rotation of each room. With `categories`, only rooms
  tagged with at least one of them are kept (the rest are disabled in game)."""
  rooms = read_rooms(path)
  if categories is not None:
    rooms = [r for r in rooms if set(r.categories) & set(categories)]
    if not rooms:
      raise TileError(f"{path}: no rooms in categories {categories}")
  # rotated by rooms.py, like the in-game lookups, so `_R` encodings turn exactly as they do in game
  return [Tile(lookup.room.name, 90 * lookup.rotation, tuple(lookup.sides),
               tuple(tuple(t) for t in lookup.targets), tuple(lookup.room.categories))
          for lookup in sheet.lookups(rooms)]


def encoding_ids(path: Path) -> dict[str, int]:
  """The in-game number of every encoding, numbered over the whole sheet."""
  return sheet.encoding_ids(read_rooms(path))


def write_csv(base: list[Tile], path: Path) -> None:
  """Writes rooms (default rotation only) in the room sheet layout, with weight 0."""
  sides = ["North", "East", "South", "West", "Up", "Down"]
  header = ["Room Weight", "Categories", "Structure Name", *sides, *(f"Target {s}" for s in sides)]
  with open(path, "w", newline="", encoding="utf-8") as f:
    out = csv.writer(f)
    out.writerow(header)
    for tile in base:
      out.writerow(["0", ", ".join(tile.categories), tile.name, *tile.phys,
                    *(", ".join(t) for t in tile.targets)])


# ------------------------------------------------------------------------------------------ problem

@dataclass
class Problem:
  tiles: list[Tile]
  size: tuple[int, int, int]             # X (width), Y (height), Z (length)
  constraints: frozenset[Pos] = frozenset()
  wall: str = WALL

  def __post_init__(self) -> None:
    if min(self.size) < 1:
      raise TileError(f"every dimension must be at least 1, got {self.size}")
    for p in self.constraints:
      if not self.in_box(p):
        raise TileError(f"constraint {p} is outside the grid")
    if (0, 0, 0) in self.constraints:
      raise TileError("the start cell (0,0,0) can't be a constraint")

  def in_box(self, p: Pos) -> bool:
    return all(0 <= p[i] < self.size[i] for i in range(3))

  def blocked(self, p: Pos) -> bool:
    """True for constraint nodes: anything outside the box, and interior constraints."""
    return not self.in_box(p) or p in self.constraints

  def free_cells(self) -> list[Pos]:
    X, Y, Z = self.size
    return [(x, y, z) for y in range(Y) for z in range(Z) for x in range(X)
            if (x, y, z) not in self.constraints]


def accepts(a: Tile, d: int, b: Tile) -> bool:
  """The algorithm's one-sided check: may `a` sit on side d of filled cell `b`?"""
  return a.phys[d] in b.targets[OPP[d]]


def matches(a: Tile, d: int, b: Tile) -> bool:
  """Both halves: `b` on side d of `a` is a valid pair."""
  return accepts(a, d, b) and accepts(b, OPP[d], a)


def wall_accepts(a: Tile, d: int, wall: str = WALL) -> bool:
  """The algorithm's check against a constraint on side d of `a`."""
  return a.phys[d] == wall


def wall_matches(a: Tile, d: int, wall: str = WALL) -> bool:
  return a.phys[d] == wall and wall in a.targets[d]


# --------------------------------------------------------------------------------------- validation

def reciprocity_errors(tiles: list[Tile], wall: str = WALL) -> list[str]:
  """Every (pair, side) where one half of the match holds and the other doesn't."""
  errors = []
  for d in range(6):
    for a in tiles:
      if wall_accepts(a, d, wall) != (wall in a.targets[d]):
        errors.append(f"{a.label} {DIRS[d]} vs {wall}: encoding {a.phys[d]!r}, "
                      f"targets {sorted(a.targets[d])}")
      for b in tiles:
        if accepts(a, d, b) != accepts(b, OPP[d], a):
          errors.append(f"{b.label} on the {DIRS[d]} of {a.label}: {a.label}.{DIRS[d]}={a.phys[d]!r} "
                        f"{'in' if accepts(a, d, b) else 'not in'} {b.label}.target_{DIRS[OPP[d]]}, "
                        f"but {b.label}.{DIRS[OPP[d]]}={b.phys[OPP[d]]!r} "
                        f"{'in' if accepts(b, OPP[d], a) else 'not in'} {a.label}.target_{DIRS[d]}")
  return sorted(set(errors))


def lint(tiles: list[Tile], wall: str = WALL) -> list[str]:
  """Things that are legal but probably mistakes."""
  notes = []
  names = sorted({t.name for t in tiles})
  phys = {e for t in tiles for e in t.phys} | {wall}
  targeted = {e for t in tiles for ts in t.targets for e in ts}
  every = phys | targeted
  for e in sorted(every):
    if e != e.strip():
      notes.append(f"encoding {e!r} has leading or trailing whitespace")
  folded: dict[str, set[str]] = {}
  for e in every:
    folded.setdefault(e.strip().lower(), set()).add(e)
  for group in folded.values():
    if len(group) > 1:
      notes.append(f"encodings differ only by case/whitespace: {sorted(group)}")
  for e in sorted(targeted - phys):
    notes.append(f"{e!r} is targeted but no cell or constraint has it as an encoding")
  seen: dict[tuple, str] = {}
  for t in tiles:
    key = (t.name, t.phys, t.targets)
    if key in seen:
      notes.append(f"{t.label} is identical to {seen[key]} (rotationally symmetric)")
    else:
      seen[key] = t.label
  if len(names) != sum(1 for t in tiles if t.rotation == 0):
    notes.append("duplicate structure names")
  return notes
