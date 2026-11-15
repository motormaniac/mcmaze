"""Builds the maze2 lookup entities and the bulk place chain from the room sheet.

  cd py
  uv run rooms/rooms.py           -- download the sheet to rooms/rooms.csv, then build from it
  uv run rooms/rooms.py some.csv  -- build from a CSV without downloading

Writes two IR files (see compile/LANG.md), which compile/main.py turns into schematics:
  compile/ir/lookups.irt  kills the old lookups, then summons one lookup per room rotation
  compile/ir/place.irt    places the structure of every graph node, picked by its ref

Each row of the sheet is one structure in its default rotation. Each of its 4 rotations around Y
becomes its own lookup, with ref = 4 * row index + rotation index (in ROTATIONS order).
Rotating clockwise moves each side's encoding and target list from north to east, east to south, etc.
Up and down never move.

Encodings are numbered in order of first appearance, reading the rows top to bottom and each row
left to right. Target lists shorter than TARGET_AMOUNT are padded with EMPTY_TARGET.
Nothing is written if any row has an error, and every error is printed.
"""

import argparse
import csv
import io
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).parent

# where the data comes from
SHEET_ID = "1mnQcWEaTwluAJlambKJbKJhSU-XOdP26-KMLGE8lRIQ"
SHEET_TAB = "Chart"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_TAB}"
CSV_PATH = HERE / "rooms.csv"

# where the IR goes
IR_DIR = HERE.parent / "compile" / "ir"
LOOKUPS_IR = IR_DIR / "lookups.irt"
PLACE_IR = IR_DIR / "place.irt"

# sheet columns (0 based, so column A is 0). Data starts on the row after the HEADER cell.
# Headers: Room Weight, Categories, Structure Name, North..Down, Target North..Target Down
WEIGHT_COL = 0
CATEGORIES_COL = 1
NAME_COL = 2
SIDES_COL = 3 # the 6 own encodings, in SIDES order
TARGETS_COL = 9 # the 6 target lists, in SIDES order
HEADER = "Structure Name" # the NAME_COL cell of the header row
SHEET_HEADER_ROW = 2 # row number of the header in the sheet, so errors can name sheet rows

# entities (keep in sync with maze2.mct)
ENTITY_TYPE = "item_display"
LOOKUP_NAME = "lookup"
GRAPH_NAME = "graph"
LOOKUP = f"type={ENTITY_TYPE},name={LOOKUP_NAME}"
GRAPH = f"type={ENTITY_TYPE},name={GRAPH_NAME}"
LOOKUP_NBT = f"CustomName:{LOOKUP_NAME},view_range:0f,width:0f,height:0f"
LOOKUP_POS = "0 0 0" # absolute coordinates. Must have the same Y and Z as randChoose.
NEW_TAG = "new"
CONSTRAINT_TAG = "constraint"
CATEGORY_PREFIX = "cat_"

# scoreboards (keep in sync with maze2.mct)
SIDES = ("north", "east", "south", "west", "up", "down")
TARGET_SCORE = "target_{side}{k}"
TARGET_AMOUNT = 6
EMPTY_TARGET = -1
WEIGHT_SCORE = "rngWeight"
REF_SCORE = "ref"
ENABLED_SCORE = "enabled"
MIN_WEIGHT, MAX_WEIGHT = -100, 100

# rooms are ROOM_SIZE blocks on each side, with the graph node at the center block
ROOM_SIZE = 7
ROTATIONS = ("none", "clockwise_90", "180", "counterclockwise_90")

ENCODING_RE = re.compile(r"[^\s(),]+")
CATEGORY_RE = re.compile(r"[A-Za-z0-9_.+-]+")
STRUCTURE_RE = re.compile(r"([a-z0-9_.-]+:)?[a-z0-9_./-]+")


@dataclass
class Room:
  row: int # sheet row, for messages
  name: str
  weight: int
  categories: list[str]
  sides: list[str] # one encoding per side, in SIDES order
  targets: list[list[str]] # one target list per side, in SIDES order

@dataclass
class Lookup:
  room: Room
  rotation: int # index into ROTATIONS
  ref: int
  sides: list[str]
  targets: list[list[str]]


def fetch(path: Path) -> None:
  """Downloads the SHEET_TAB tab of the sheet as CSV."""
  with urllib.request.urlopen(SHEET_URL, timeout=30) as response:
    text = response.read().decode("utf-8")
  path.write_text(text, encoding="utf-8", newline="")
  print(f"downloaded {SHEET_TAB} to {path}")

def parse_list(cell: str) -> list[str]:
  """`(open, close)` or `open, close` or `open` -> ['open', 'close']. Keeps empty entries for errors."""
  text = cell.strip()
  if text.startswith("(") and text.endswith(")"):
    text = text[1:-1]
  if not text.strip():
    return []
  return [item.strip() for item in text.split(",")]

def parse_rooms(rows: list[list[str]]) -> tuple[list[Room], list[str]]:
  """Reads every room below the header row. Returns the rooms and every error found."""
  header = next((i for i, row in enumerate(rows) if len(row) > NAME_COL and row[NAME_COL].strip() == HEADER), None)
  if header is None:
    return [], [f"no header row with {HEADER!r} in column {chr(ord('A') + NAME_COL)}"]

  rooms: list[Room] = []
  errors: list[str] = []
  width = TARGETS_COL + len(SIDES)
  for i, row in enumerate(rows[header + 1:], start=1):
    row = [cell.strip() for cell in row] + [""] * (width - len(row))
    sheet_row = SHEET_HEADER_ROW + i
    name = row[NAME_COL]
    sides = row[SIDES_COL:SIDES_COL + len(SIDES)]
    target_cells = row[TARGETS_COL:TARGETS_COL + len(SIDES)]
    if not name and not row[CATEGORIES_COL] and not any(sides) and not any(target_cells):
      continue # blank row (the weight column defaults to 0, so it doesn't count)

    def error(message: str) -> None:
      errors.append(f"row {sheet_row} ({name or 'no name'}): {message}")

    if not name:
      error("missing structure name")
    elif not STRUCTURE_RE.fullmatch(name):
      error(f"structure name {name!r} isn't a valid resource location (lowercase a-z, 0-9, _ . - / only)")

    weight = 0
    if row[WEIGHT_COL]:
      try:
        value = float(row[WEIGHT_COL])
      except ValueError:
        value = None
      if value is None or not value.is_integer() or not MIN_WEIGHT <= value <= MAX_WEIGHT:
        error(f"room weight {row[WEIGHT_COL]!r} must be a whole number from {MIN_WEIGHT} to {MAX_WEIGHT}")
      else:
        weight = int(value)

    categories = parse_list(row[CATEGORIES_COL])
    for category in categories:
      if not CATEGORY_RE.fullmatch(category):
        error(f"category {category!r} can only use letters, digits and _ . + -")

    for side, encoding in zip(SIDES, sides):
      if not encoding:
        error(f"missing {side} encoding")
      elif not ENCODING_RE.fullmatch(encoding):
        error(f"{side} encoding {encoding!r} must be one encoding with no spaces, commas or brackets")

    targets: list[list[str]] = []
    for side, cell in zip(SIDES, target_cells):
      items = list(dict.fromkeys(parse_list(cell))) # drop duplicates, keep order
      if not items:
        error(f"{side} target list is empty")
      elif len(items) > TARGET_AMOUNT:
        error(f"{side} target list has {len(items)} encodings, the most is {TARGET_AMOUNT}")
      for item in items:
        if not item:
          error(f"{side} target list has an empty entry (extra comma?)")
        elif not ENCODING_RE.fullmatch(item):
          error(f"{side} target {item!r} must be one encoding with no spaces, commas or brackets")
      targets.append(items)

    rooms.append(Room(sheet_row, name, weight, categories, sides, targets))

  # a target nothing can ever have would never match, so it's almost certainly a typo
  known = {encoding for room in rooms for encoding in room.sides}
  for room in rooms:
    for side, items in zip(SIDES, room.targets):
      for item in items:
        if item and item not in known:
          errors.append(f"row {room.row} ({room.name}): {side} target {item!r} isn't any room's own encoding")

  if not rooms and not errors:
    errors.append("no rooms found below the header row")
  return rooms, errors

def encoding_ids(rooms: list[Room]) -> dict[str, int]:
  """Numbers every encoding from 0 in order of first appearance, row by row, left to right."""
  ids: dict[str, int] = {}
  for room in rooms:
    for encoding in room.sides + [item for items in room.targets for item in items]:
      ids.setdefault(encoding, len(ids))
  return ids

def rotate[T](values: list[T], turns: int) -> list[T]:
  """Turns per-side values clockwise: the north value moves to east, and so on. Up and down stay."""
  horizontal = values[:4]
  return [horizontal[(i - turns) % 4] for i in range(4)] + values[4:]

def lookups(rooms: list[Room]) -> list[Lookup]:
  return [
    Lookup(room, turns, len(ROTATIONS) * i + turns, rotate(room.sides, turns), rotate(room.targets, turns))
    for i, room in enumerate(rooms)
    for turns in range(len(ROTATIONS))
  ]

def place_offset(rotation: int) -> str:
  """Where `place template` needs its origin so the rotated room is centered on the node.
  The template rotates around its origin corner, so the corner moves with each rotation."""
  low = -(ROOM_SIZE // 2)
  high = low + ROOM_SIZE - 1
  x, z = [(low, low), (high, low), (high, high), (low, high)][rotation]
  return " ".join(f"~{n}" if n else "~" for n in (x, low, z))

def lookups_ir(all_lookups: list[Lookup], ids: dict[str, int]) -> str:
  new = f"@e[{LOOKUP},tag={NEW_TAG}]"
  lines = [f"kill @e[{LOOKUP}]"]
  for lookup in all_lookups:
    tags = ",".join([NEW_TAG] + [CATEGORY_PREFIX + category for category in lookup.room.categories])
    lines.append(f"#-- {lookup.room.name} {ROTATIONS[lookup.rotation]} ref {lookup.ref}")
    lines.append(f"summon {ENTITY_TYPE} {LOOKUP_POS} {{{LOOKUP_NBT},Tags:[{tags}]}}")
    for side, encoding in zip(SIDES, lookup.sides):
      lines.append(f"scoreboard players set {new} {side} {ids[encoding]}")
    for side, items in zip(SIDES, lookup.targets):
      values = [ids[item] for item in items] + [EMPTY_TARGET] * (TARGET_AMOUNT - len(items))
      for k, value in enumerate(values, start=1):
        lines.append(f"scoreboard players set {new} {TARGET_SCORE.format(side=side, k=k)} {value}")
    lines.append(f"scoreboard players set {new} {WEIGHT_SCORE} {lookup.room.weight}")
    lines.append(f"scoreboard players set {new} {REF_SCORE} {lookup.ref}")
    lines.append(f"scoreboard players set {new} {ENABLED_SCORE} 1")
    lines.append(f"tag {new} remove {NEW_TAG}")
  return "\n".join(lines) + "\n"

def place_ir(all_lookups: list[Lookup]) -> str:
  lines = [
    f"execute as @e[{GRAPH},tag=!{CONSTRAINT_TAG},scores={{{REF_SCORE}={lookup.ref}}}] at @s"
    f" run place template {lookup.room.name} {place_offset(lookup.rotation)} {ROTATIONS[lookup.rotation]}"
    for lookup in all_lookups
  ]
  return "\n".join(lines) + "\n"

def write(path: Path, text: str) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8", newline="\n")
  commands = sum(not line.startswith("#--") for line in text.splitlines())
  print(f"wrote {path} ({commands} commands)")

def build(csv_path: Path) -> int:
  rows = list(csv.reader(io.StringIO(csv_path.read_text(encoding="utf-8-sig"))))
  rooms, errors = parse_rooms(rows)
  if errors:
    for message in errors:
      print(f"{csv_path.name}: {message}", file=sys.stderr)
    print(f"{len(errors)} error(s), nothing written", file=sys.stderr)
    return 1

  ids = encoding_ids(rooms)
  all_lookups = lookups(rooms)
  write(LOOKUPS_IR, lookups_ir(all_lookups, ids))
  write(PLACE_IR, place_ir(all_lookups))
  print(f"{len(rooms)} rooms, {len(all_lookups)} lookups")
  print("encodings: " + ", ".join(f"{id}={encoding}" for encoding, id in ids.items()))
  return 0

def main(argv: list[str]) -> int:
  parser = argparse.ArgumentParser(prog="uv run rooms/rooms.py",
    description="Build the maze2 lookups and place chains (.irt) from the room sheet.")
  parser.add_argument("csv", type=Path, nargs="?",
    help=f"a CSV export of the sheet (default: download the sheet to {CSV_PATH.name} first)")
  args = parser.parse_args(argv)
  if args.csv is None:
    fetch(CSV_PATH)
    args.csv = CSV_PATH
  elif not args.csv.is_file():
    parser.error(f"{args.csv}: file not found")
  return build(args.csv)

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
