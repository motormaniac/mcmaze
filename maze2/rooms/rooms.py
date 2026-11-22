"""Builds the maze2 lookup entities and the bulk place chain from the room sheet.

  uv run poe rooms           -- download the sheet to maze2/rooms/rooms.csv, then build from it
  uv run poe rooms some.csv  -- build from a CSV without downloading

The sheet gives each room two rows: a This row (name, weight, categories, the room's own encoding on each
side, and the In?/Rot? checkboxes) with a Target row right under it (the target list of each side).
fetch() finds each column by its header and saves rooms.csv in the room CSV layout (CSV_HEADER), one row
per room, which every CSV this script reads must use (maze2/manual_test/test_rooms.csv uses it too). Each
Target row becomes a blank row, so a room's row in rooms.csv is its This row's number in the sheet.
A room with Ignore checked becomes two blank rows, so it isn't checked or built, as if it weren't there.
A room's lookups are summoned with ENABLED_TAG unless Disabled is checked. Disabled rooms are still built, but
the algorithm skips their lookups until something tags them (like $enable_category in constraint.mct).

Writes two IR files (see tools/mct/LANG.md), which `uv run poe mct` turns into schematics:
  maze2/ir/lookups.irt  kills the old lookups, then summons one lookup per room rotation
  maze2/ir/place.irt    places the structure of every graph node, picked by its ref

Each room is one structure in its default rotation. Each of its 4 rotations around Y becomes its own
lookup, with ref = 4 * room index + rotation index (in ROTATIONS order).
Rotating clockwise moves each side's encoding and target list from north to east, east to south, etc.
Up and down never move.

Horizontal sides only ever match horizontal sides, and up and down only match each other, so the two
axes have separate encodings: the same name on a horizontal side and on up or down is two encodings.
In and Rot belong to the encoding on its axis, not the side: every room that has an encoding on that axis
must check the same boxes for it, and a target gets them from the encoding it names on its own axis.
- In marks a connection inside a multiblock. In encodings are numbered from INNER_FIRST_ID instead of 1,
  so the algorithm ignores them last (see "Prioritizing multiblocks" in maze2.mct).
- Rot makes the encoding turn with its room. Only up and down have the box. A rotating encoding becomes
  one encoding per rotation: rotation k (in ROTATIONS order) uses `stair_R{90*k}` (`stair_R0`,
  `stair_R90`, ...), so two rooms stacked on it only match when they are rotated the same way.
A name used on both axes that doesn't rotate on up and down shares one id between them, which is
harmless since the axes never meet, as long as both axes check In the same way for it.

The CONSTRAINT_ENCODING encoding (the maze boundary) is always id 0, and can't be In or Rot. Every other
encoding is numbered in order of first appearance, reading the rooms top to bottom and each room's sides,
then its targets, left to right: encodings without In from 1, In encodings from INNER_FIRST_ID. A rotating
encoding takes 4 ids in a row, in ROTATIONS order. Target lists shorter than TARGET_AMOUNT are padded with
EMPTY_TARGET.
Every target has to be able to match something: some room's own encoding on the side it faces (see
unmatched_targets). Nothing is written if any room has an error, and every error is printed.

sheet_checks.gs runs the same checks inside the sheet (pasted into its Apps Script) and shows them in
the Errors column. When a check here changes, change it there too.
"""

import argparse
import csv
import io
import re
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).parent

# where the data comes from
SHEET_ID = "1mnQcWEaTwluAJlambKJbKJhSU-XOdP26-KMLGE8lRIQ"
SHEET_TAB = "Chart"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_TAB}"
CSV_PATH = HERE / "rooms.csv"

# the sheet's layout. The This/Target column has no header, so it's found by its values.
SHEET_THIS = "This"
SHEET_TARGET = "Target"
SHEET_IN = "In?" # header of the column right after each side's column
SHEET_ROT = "Rot?" # header of the column right after In?, on ROTATING_SIDES only
SHEET_IGNORE = "Ignore" # checkbox on the This row: leave the room out entirely
SHEET_DISABLED = "Disabled" # checkbox on the This row: summon the room's lookups without ENABLED_TAG

# where the IR goes
IR_DIR = HERE.parent / "ir"
LOOKUPS_IR = IR_DIR / "lookups.irt"
PLACE_IR = IR_DIR / "place.irt"

# entities (keep in sync with maze2.mct)
ENTITY_TYPE = "item_display"
LOOKUP_NAME = "lookup"
GRAPH_NAME = "graph"
LOOKUP = f"type={ENTITY_TYPE},name={LOOKUP_NAME}"
GRAPH = f"type={ENTITY_TYPE},name={GRAPH_NAME}"
LOOKUP_NBT = f"CustomName:{LOOKUP_NAME},view_range:0f,width:0f,height:0f"
LOOKUP_POS = "-58.0 3.0 3.0" # absolute coordinates. Must have the same Y and Z as randChoose.
NEW_TAG = "new"
CONSTRAINT_TAG = "constraint"
ENABLED_TAG = "enabled" # lookups without it are skipped by the filter in maze2.mct
CATEGORY_PREFIX = "cat_"

# the encoding constraint nodes have on every side. Always id 0 ($CONSTRAINT_ENCODING_TYPE in constraint.mct).
CONSTRAINT_ENCODING = "constraint"
CONSTRAINT_ID = 0
# In encodings are numbered from here, so they beat every other encoding in the priority list (maze2.mct)
INNER_FIRST_ID = 1001

# scoreboards (keep in sync with maze2.mct)
SIDES = ("north", "east", "south", "west", "up", "down")
HORIZONTAL_SIDES = SIDES[:4]
OPPOSITE = {"up": "down", "down": "up"}
TARGET_SCORE = "target_{side}{k}"
TARGET_AMOUNT = 6
EMPTY_TARGET = -1
WEIGHT_SCORE = "rngWeight"
REF_SCORE = "ref"
MIN_WEIGHT, MAX_WEIGHT = -100, 100

# rooms are ROOM_SIZE blocks on each side, with the graph node at the center block
ROOM_SIZE = 7
ROTATIONS = ("none", "clockwise_90", "180", "counterclockwise_90")

# only up and down have a Rot box. A rotating `stair` becomes `stair_R0`, `stair_R90`, ...
ROTATING_SIDES = ("up", "down")
VARIANT_SUFFIX = "_R"
# the two axes, which never match each other (see axis())
HORIZONTAL, VERTICAL = "horizontal", "up/down"

# the room CSV layout: one row per room. Flags are TRUE, FALSE or blank (FALSE).
HEADER = "Structure Name" # the NAME_COL cell of the header row
CSV_HEADER = ["Room Weight", "Categories", HEADER,
              *(side.title() for side in SIDES),
              *(f"In {side.title()}" for side in SIDES),
              *(f"Rot {side.title()}" for side in ROTATING_SIDES),
              *(f"Target {side.title()}" for side in SIDES),
              SHEET_DISABLED]
WEIGHT_COL = CSV_HEADER.index("Room Weight") # 0 based, so column A is 0
CATEGORIES_COL = CSV_HEADER.index("Categories")
NAME_COL = CSV_HEADER.index(HEADER)
SIDES_COL = CSV_HEADER.index("North") # the 6 own encodings, in SIDES order
INNER_COL = CSV_HEADER.index("In North") # the 6 In flags, in SIDES order
ROT_COL = CSV_HEADER.index("Rot Up") # the Rot flags, in ROTATING_SIDES order
TARGETS_COL = CSV_HEADER.index("Target North") # the 6 target lists, in SIDES order
DISABLED_COL = CSV_HEADER.index(SHEET_DISABLED)
TRUE, FALSE = "TRUE", "FALSE"

ENCODING_RE = re.compile(r"[^\s(),]+")
CATEGORY_RE = re.compile(r"[A-Za-z0-9_.+-]+")
STRUCTURE_RE = re.compile(r"([a-z0-9_.-]+:)?[a-z0-9_./-]+")


@dataclass
class Room:
  row: int # row in the CSV (and the sheet), for messages
  name: str
  weight: int
  categories: list[str]
  sides: list[str] # one encoding per side, in SIDES order
  targets: list[list[str]] # one target list per side, in SIDES order
  inner: list[bool] = field(default_factory=lambda: [False] * len(SIDES)) # In, in SIDES order
  rot: list[bool] = field(default_factory=lambda: [False] * len(SIDES)) # Rot, in SIDES order (horizontal: False)
  disabled: bool = False # its lookups start without ENABLED_TAG

@dataclass
class Lookup:
  room: Room
  rotation: int # index into ROTATIONS
  ref: int
  sides: list[str]
  targets: list[list[str]]


def convert_sheet(rows: list[list[str]]) -> list[list[str]]:
  """Rearranges the downloaded sheet into CSV_HEADER's layout, finding each column by its header.
  Each side's column is followed by its In? box, and on up and down by its Rot? box after that.
  A This row and the Target row right under it become one room row, and the Target row a blank row,
  so row numbers still match the sheet. A room with Ignore checked becomes two blank rows. Other
  columns are dropped."""
  if not rows:
    raise ValueError("the sheet is empty")
  header = [cell.strip().lower() for cell in rows[0]]

  def find(name: str) -> int:
    matches = [i for i, cell in enumerate(header) if cell == name.lower()]
    if len(matches) != 1:
      raise ValueError(f"expected one {name!r} column in the sheet header, found {len(matches)}: {rows[0]}")
    return matches[0]

  def after(column: int, offset: int, name: str) -> int:
    if column + offset >= len(header) or header[column + offset] != name.lower():
      raise ValueError(f"expected {name!r} {offset} column(s) after {rows[0][column]!r} in the sheet header: {rows[0]}")
    return column + offset

  sides = [find(side) for side in SIDES]
  inner = [after(column, 1, SHEET_IN) for column in sides]
  rot = [after(sides[SIDES.index(side)], 2, SHEET_ROT) for side in ROTATING_SIDES]
  columns = [find("Room Weight"), find("Categories"), find(HEADER), *sides, *inner, *rot]
  ignore = find(SHEET_IGNORE)
  disabled = find(SHEET_DISABLED)

  def cell(row: list[str], i: int) -> str:
    return row[i].strip() if i < len(row) else ""

  width = max(len(row) for row in rows)
  markers = [i for i in range(width) if any(cell(row, i) == SHEET_THIS for row in rows[1:])]
  if len(markers) != 1:
    raise ValueError(f"expected one column with {SHEET_THIS!r} rows in it, found {len(markers)}")

  def kind(i: int) -> str:
    return cell(rows[i], markers[0]) if 0 < i < len(rows) else ""

  blank = [""] * len(CSV_HEADER)
  converted = [CSV_HEADER]
  errors = []
  for i, row in enumerate(rows[1:], start=1):
    if kind(i) == SHEET_THIS:
      if kind(i + 1) != SHEET_TARGET:
        errors.append(f"row {i + 1}: a {SHEET_THIS} row needs a {SHEET_TARGET} row right under it")
      target = rows[i + 1] if kind(i + 1) == SHEET_TARGET else []
      ignored = parse_flag(cell(row, ignore))
      if ignored is None:
        errors.append(f"row {i + 1}: {SHEET_IGNORE} is {cell(row, ignore)!r}, it must be {TRUE}, {FALSE} or blank")
      converted.append(blank if ignored else
                       [cell(row, c) for c in columns] + [cell(target, c) for c in sides] + [cell(row, disabled)])
    elif kind(i) == SHEET_TARGET:
      if kind(i - 1) != SHEET_THIS:
        errors.append(f"row {i + 1}: a {SHEET_TARGET} row has to be right under a {SHEET_THIS} row")
      converted.append(blank)
    else:
      if any(cell(row, c) for c in columns[:3] + sides):
        errors.append(f"row {i + 1}: has data but isn't marked {SHEET_THIS} or {SHEET_TARGET}")
      converted.append(blank)
  if errors:
    raise ValueError("\n".join(errors))
  return converted

def fetch(path: Path) -> None:
  """Downloads the SHEET_TAB tab of the sheet and saves it to `path` in CSV_HEADER's layout."""
  with urllib.request.urlopen(SHEET_URL, timeout=30) as response:
    text = response.read().decode("utf-8-sig")
  rows = convert_sheet(list(csv.reader(io.StringIO(text))))
  with open(path, "w", encoding="utf-8", newline="") as f:
    csv.writer(f, quoting=csv.QUOTE_ALL).writerows(rows)
  print(f"downloaded {SHEET_TAB} to {path}", flush=True)

def parse_list(cell: str) -> list[str]:
  """`(open, close)` or `open, close` or `open` -> ['open', 'close']. Keeps empty entries for errors."""
  text = cell.strip()
  if text.startswith("(") and text.endswith(")"):
    text = text[1:-1]
  if not text.strip():
    return []
  return [item.strip() for item in text.split(",")]

def parse_flag(cell: str) -> bool | None:
  """TRUE -> True, FALSE or blank -> False, anything else -> None."""
  return {"": False, FALSE: False, TRUE: True}.get(cell.strip().upper())

def axis(side: str) -> str:
  """HORIZONTAL or VERTICAL. Encodings on different axes never match, so they're separate encodings."""
  return HORIZONTAL if side in HORIZONTAL_SIDES else VERTICAL

def encoding_flags(rooms: list[Room]) -> tuple[dict[str, set[str]], set[str]]:
  """The In encodings of each axis, and the rotating encodings (up and down only), from each encoding's
  first own use on its axis (parse_rooms makes sure every use agrees). Targets aren't read: they get
  their encoding's flags."""
  inner: dict[str, set[str]] = {HORIZONTAL: set(), VERTICAL: set()}
  rotating: set[str] = set()
  seen: set[tuple[str, str]] = set()
  for room in rooms:
    for side, encoding, is_inner, rotates in zip(SIDES, room.sides, room.inner, room.rot):
      if (axis(side), encoding) in seen:
        continue
      seen.add((axis(side), encoding))
      if is_inner:
        inner[axis(side)].add(encoding)
      if rotates:
        rotating.add(encoding)
  return inner, rotating

def variant(encoding: str, side: str, turns: int, rotating: set[str]) -> str:
  """The encoding `side` of a room turned `turns` times clockwise uses: rotating `stair` on up or down ->
  `stair_R90` for 1 turn. Horizontal sides and encodings that don't rotate don't change."""
  if axis(side) == VERTICAL and encoding in rotating:
    return f"{encoding}{VARIANT_SUFFIX}{90 * turns}"
  return encoding

def variants(encoding: str, side: str, rotating: set[str]) -> list[str]:
  """Every encoding `encoding` on `side` can become, in ROTATIONS order."""
  return list(dict.fromkeys(variant(encoding, side, turns, rotating) for turns in range(len(ROTATIONS))))

def encoding_uses(rooms: list[Room], targets: bool = True) -> list[tuple[str, str, bool]]:
  """(encoding, base encoding, is In) for every use of an encoding in the lookups, in order: room by room,
  sides then targets (unless `targets` is False), left to right. A rotating encoding gives each variant."""
  inner, rotating = encoding_flags(rooms)
  uses = []
  for room in rooms:
    sided = list(zip(SIDES, room.sides))
    if targets:
      sided += [(side, item) for side, items in zip(SIDES, room.targets) for item in items]
    for side, base in sided:
      for encoding in variants(base, side, rotating):
        uses.append((encoding, base, base in inner[axis(side)]))
  return uses

def check_flags(rooms: list[Room]) -> list[str]:
  """In and Rot belong to the encoding on its axis, so every side on that axis that has an encoding must
  check the same boxes. Horizontal sides have no Rot box, and can share a name with up and down."""
  errors = []
  first: dict[tuple[str, str], tuple[Room, str, bool, bool]] = {}
  reported: set[tuple[str, str, str]] = set()
  for room in rooms:
    for side, encoding, is_inner, rotates in zip(SIDES, room.sides, room.inner, room.rot):
      if not encoding:
        continue
      if encoding == CONSTRAINT_ENCODING:
        if is_inner or rotates:
          errors.append(f"row {room.row} ({room.name}): {side} is {CONSTRAINT_ENCODING}, which can't be In or "
                        f"Rot (it's always id {CONSTRAINT_ID})")
        continue
      key = (axis(side), encoding)
      if key not in first:
        first[key] = (room, side, is_inner, rotates)
        continue
      room0, side0, inner0, rotates0 = first[key]
      where = f"on {side0} in row {room0.row} ({room0.name})"
      if is_inner != inner0 and (*key, "In") not in reported:
        reported.add((*key, "In"))
        errors.append(f"row {room.row} ({room.name}): {side} encoding {encoding!r} has In "
                      f"{'checked' if is_inner else 'unchecked'}, but {where} it's "
                      f"{'checked' if inner0 else 'unchecked'}. Every {key[0]} side has to check In the same way for it")
      if rotates != rotates0 and (*key, "Rot") not in reported:
        reported.add((*key, "Rot"))
        errors.append(f"row {room.row} ({room.name}): {side} encoding {encoding!r} "
                      f"{'rotates' if rotates else 'does not rotate'}, but {where} it "
                      f"{'does' if rotates0 else 'does not'}. Give the rotating one its own name")
  if errors:
    return errors

  # a name on both axes that doesn't rotate on up and down is the same encoding to the lookups, so one id
  own = encoding_uses(rooms, targets=False)
  split = {e for e, _, is_inner in own if is_inner} & {e for e, _, is_inner in own if not is_inner}
  for encoding in sorted(split):
    errors.append(f"encoding {encoding!r} has In checked on one axis but not the other. Since it doesn't "
                  f"rotate on up and down, both axes share one id, so give one of them its own name")
  return errors

def unmatched_targets(rooms: list[Room]) -> list[str]:
  """Targets no room can ever match. A target on up or down has to be some room's own encoding on the
  opposite side. A horizontal target has to be some room's own encoding on any horizontal side, since
  rooms turn. Constraint targets always match the boundary, and unknown targets are errors already."""
  own: dict[str, set[str]] = {side: set() for side in SIDES}
  for room in rooms:
    for side, encoding in zip(SIDES, room.sides):
      own[side].add(encoding)
  known = set().union(*own.values())
  messages = []
  for room in rooms:
    for side, items in zip(SIDES, room.targets):
      need = HORIZONTAL_SIDES if side in HORIZONTAL_SIDES else (OPPOSITE[side],)
      for item in items:
        if item and item != CONSTRAINT_ENCODING and item in known and not any(item in own[s] for s in need):
          where = "any horizontal side" if side in HORIZONTAL_SIDES else OPPOSITE[side]
          messages.append(f"row {room.row} ({room.name}): {side} target {item!r} is no room's own encoding on "
                          f"{where}, so it can never match")
  return messages

def parse_rooms(rows: list[list[str]]) -> tuple[list[Room], list[str]]:
  """Reads every room below the header row. Returns the rooms and every error found."""
  header = next((i for i, row in enumerate(rows) if len(row) > NAME_COL and row[NAME_COL].strip() == HEADER), None)
  if header is None:
    return [], [f"no header row with {HEADER!r} in column {chr(ord('A') + NAME_COL)}"]
  if [cell.strip().lower() for cell in rows[header]] != [cell.lower() for cell in CSV_HEADER]:
    return [], [f"row {header + 1}: the header doesn't match the room CSV layout. Expected: {', '.join(CSV_HEADER)}"]

  rooms: list[Room] = []
  errors: list[str] = []
  width = len(CSV_HEADER)
  for index in range(header + 1, len(rows)):
    row = [cell.strip() for cell in rows[index]] + [""] * (width - len(rows[index]))
    row_number = index + 1
    name = row[NAME_COL]
    sides = row[SIDES_COL:SIDES_COL + len(SIDES)]
    target_cells = row[TARGETS_COL:TARGETS_COL + len(SIDES)]
    if not name and not row[CATEGORIES_COL] and not any(sides) and not any(target_cells):
      continue # blank row (weight and flags have defaults, so they don't count)

    def error(message: str) -> None:
      errors.append(f"row {row_number} ({name or 'no name'}): {message}")

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

    def flag(box: str, side: str, cell: str) -> bool:
      value = parse_flag(cell)
      if value is None:
        error(f"{box} {side} is {cell!r}, it must be {TRUE}, {FALSE} or blank")
      return bool(value)

    inner = [flag("In", side, cell) for side, cell in zip(SIDES, row[INNER_COL:INNER_COL + len(SIDES)])]
    rot = [False] * len(SIDES)
    for side, cell in zip(ROTATING_SIDES, row[ROT_COL:ROT_COL + len(ROTATING_SIDES)]):
      rot[SIDES.index(side)] = flag("Rot", side, cell)
    disabled = parse_flag(row[DISABLED_COL])
    if disabled is None:
      error(f"{SHEET_DISABLED} is {row[DISABLED_COL]!r}, it must be {TRUE}, {FALSE} or blank")

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

    rooms.append(Room(row_number, name, weight, categories, sides, targets, inner, rot, bool(disabled)))

  errors += check_flags(rooms)

  # a target nothing can ever have would never match, so it's almost certainly a typo.
  # Constraint nodes have the constraint encoding, so a room can target it without any room having it.
  known = {CONSTRAINT_ENCODING} | {encoding for room in rooms for encoding in room.sides}
  for room in rooms:
    for side, items in zip(SIDES, room.targets):
      for item in items:
        if item and item not in known:
          errors.append(f"row {room.row} ({room.name}): {side} target {item!r} isn't any room's own encoding")
  # one that exists, but only on sides it never faces, can't match either
  errors += unmatched_targets(rooms)

  # a rotating encoding's variants can't share a name with another encoding
  _, rotating = encoding_flags(rooms)
  for encoding in sorted(rotating):
    for name in variants(encoding, ROTATING_SIDES[0], rotating):
      if name in known:
        errors.append(f"encoding {name!r} has the same name as a variant of the rotating encoding {encoding!r}")

  # encodings without In can't run into the In ids
  plain = {name for name, base, is_inner in encoding_uses(rooms) if not is_inner and base != CONSTRAINT_ENCODING}
  most = INNER_FIRST_ID - CONSTRAINT_ID - 1
  if len(plain) > most:
    errors.append(f"{len(plain)} encodings without In, the most is {most} (In encodings start at {INNER_FIRST_ID})")

  if not rooms and not errors:
    errors.append("no rooms found below the header row")
  return rooms, errors

def encoding_ids(rooms: list[Room]) -> dict[str, int]:
  """Gives the constraint encoding CONSTRAINT_ID, and numbers every other encoding in order of first
  appearance, room by room, sides then targets, left to right: from CONSTRAINT_ID + 1 without In, from
  INNER_FIRST_ID with In. A rotating encoding gets an id for each of its variants, in ROTATIONS order.
  A name on both axes that doesn't rotate is one encoding to the lookups, so it gets one id."""
  next_id = {False: CONSTRAINT_ID + 1, True: INNER_FIRST_ID}
  ids: dict[str, int] = {}
  for encoding, base, is_inner in encoding_uses(rooms):
    if encoding in ids:
      continue
    if base == CONSTRAINT_ENCODING:
      ids[encoding] = CONSTRAINT_ID
    else:
      ids[encoding] = next_id[is_inner]
      next_id[is_inner] += 1
  return dict(sorted(ids.items(), key=lambda item: item[1]))

def rotate[T](values: list[T], turns: int) -> list[T]:
  """Turns per-side values clockwise: the north value moves to east, and so on. Up and down stay."""
  horizontal = values[:4]
  return [horizontal[(i - turns) % 4] for i in range(4)] + values[4:]

def lookups(rooms: list[Room]) -> list[Lookup]:
  """Every rotation of every room. Each one moves the horizontal sides, then swaps rotating encodings
  (only ever on up and down) for that rotation's variant."""
  _, rotating = encoding_flags(rooms)
  return [
    Lookup(room, turns, len(ROTATIONS) * i + turns,
           [variant(encoding, side, turns, rotating) for side, encoding in zip(SIDES, rotate(room.sides, turns))],
           [[variant(item, side, turns, rotating) for item in items]
            for side, items in zip(SIDES, rotate(room.targets, turns))])
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
    tags = ",".join([NEW_TAG] + [ENABLED_TAG] * (not lookup.room.disabled)
                    + [CATEGORY_PREFIX + category for category in lookup.room.categories])
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
  parser = argparse.ArgumentParser(prog="uv run poe rooms",
    description="Build the maze2 lookups and place chains (.irt) from the room sheet.")
  parser.add_argument("csv", type=Path, nargs="?",
    help=f"a CSV in the room CSV layout (default: download the sheet to {CSV_PATH.name} first)")
  args = parser.parse_args(argv)
  if args.csv is None:
    try:
      fetch(CSV_PATH)
    except ValueError as e:
      print(f"{SHEET_TAB}: {e}", file=sys.stderr)
      return 1
    args.csv = CSV_PATH
  elif not args.csv.is_file():
    parser.error(f"{args.csv}: file not found")
  return build(args.csv)

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
