"""Turns IR (or a .mct file) into a WorldEdit schematic of chain command blocks. See LANG.md.

  cd py
  uv run compile/schem.py compile/in/walls.mct    -- writes compile/out/walls.schem
  uv run compile/schem.py compile/ir/walls.txt    -- same, starting from IR
  options: --width 16  --gap 3  --track-output

Output is a Sponge v3 .schem for Minecraft 1.21.10. Every block is a chain command block, and the
origin (where //paste puts it) is the first one. Place your own trigger block just west of it, facing east.

Layout: the chain snakes across a width x width layer. Row 0 runs east, and each row end turns 180
degrees into the next row (rows advance south). A layer's last corner is the bottom of a bridge: it
and the `gap` blocks above it are empty chain blocks facing up, and the next layer starts directly
above, mirrored so its rows advance north.

A conditional block checks the block behind it, not the one that fed it, so it can't sit on a turn
or on the first block of a layer. When one would, empty chain blocks are inserted before the
command it depends on until the whole run of conditionals is on a straight stretch.

Compiler comments (#--) label the command below them with a waxed oak sign on top of its block,
front facing west, with glowing text. The text is word-wrapped onto the front's 4 lines, then the back's, and cut off
after that. Comments after the last command have nothing to label and are dropped.

The schematic always covers the full width x width footprint, plus a row for signs above the top
layer, and has a marker block in the +x +y +z corner so both corners can be clicked for //pos.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import nbtlib
from nbtlib.tag import ByteArray, Byte, Compound, Int, IntArray, List, Short, String

from compile import CompileError, compile_source

OUT_DIR = Path(__file__).with_name("out")
DATA_VERSION = 4556 # Minecraft 1.21.10
SPONGE_VERSION = 3
AIR = "minecraft:air"
CHAIN = "minecraft:chain_command_block"
BLOCK_ENTITY_ID = "minecraft:command_block" # shared by impulse, chain and repeating blocks
SIGN = "minecraft:oak_sign[rotation=4,waterlogged=false]" # rotation 4: front faces west
SIGN_ENTITY_ID = "minecraft:sign"
SIGN_LINES = 4 # per side
SIGN_LINE_WIDTH = 90 # pixels in the default font
MARKER = "minecraft:glass" # fills the +x +y +z corner so WorldEdit can select the whole schematic

# Pixel advance of each character in Minecraft's default font (glyph plus 1px spacing); others are 6.
CHAR_WIDTHS = {
  **dict.fromkeys("!',.:;i|", 2),
  **dict.fromkeys("`l", 3),
  **dict.fromkeys(" \"()*I[]t{}", 4),
  **dict.fromkeys("<>fk", 5),
  **dict.fromkeys("@~", 7),
}

MODIFIER_LINES = { # (conditional, needs_redstone)
  "!conditional": (True, False),
  "!needs_redstone": (False, True),
  "!conditional, needs_redstone": (True, True),
}

Vec = tuple[int, int, int]
FACING: dict[str, Vec] = {
  "east": (1, 0, 0),
  "west": (-1, 0, 0),
  "south": (0, 0, 1),
  "north": (0, 0, -1),
  "up": (0, 1, 0),
}
TRIGGER_POS: Vec = (-1, 0, 0) # the user's own block that starts the chain


class SchemError(Exception):
  """Invalid IR, or IR that can't be laid out. The message is ready to print."""


@dataclass(frozen=True)
class Command:
  text: str # "" for padding and connector blocks
  conditional: bool = False
  needs_redstone: bool = False
  line: int = 0 # IR line number, 0 for blocks schem.py adds
  comments: tuple[str, ...] = () # compiler comments right above it, without the #--

EMPTY = Command("")

@dataclass(frozen=True)
class Slot:
  """One position along the snake. Connector slots are the bridges between layers (each layer's
  last corner plus the column above it), which always hold empty blocks."""
  pos: Vec
  facing: str
  connector: bool

@dataclass(frozen=True)
class Block:
  pos: Vec
  facing: str
  command: Command


# ---- IR ----

def parse_ir(text: str, filename: str) -> list[Command]:
  """Reads IR text into commands, rejecting anything LANG.md doesn't allow. Raises SchemError."""
  def error(line: int, message: str) -> SchemError:
    return SchemError(f"{filename}:{line}: {message}")

  if "\r" in text:
    raise error(text[:text.index("\r")].count("\n") + 1, "IR must use \\n line endings")
  if not text.endswith("\n"):
    raise error(text.count("\n") + 1, "IR must end with a newline")

  commands: list[Command] = []
  comments: list[str] = []
  pending: tuple[int, bool, bool] | None = None # (line, conditional, needs_redstone)
  for n, line in enumerate(text[:-1].split("\n"), start=1):
    if line == "":
      raise error(n, "blank line")
    if line.startswith("#--"):
      if pending:
        raise error(pending[0], "modifier must be followed directly by a command")
      comments.append(line[3:].strip())
      continue
    if line.startswith("!"):
      if line not in MODIFIER_LINES:
        raise error(n, f"invalid modifier {line!r}")
      if pending:
        raise error(pending[0], "modifier must be followed directly by a command")
      pending = (n, *MODIFIER_LINES[line])
      continue
    if line != line.strip():
      raise error(n, "command has leading or trailing whitespace")
    conditional, needs_redstone = pending[1:] if pending else (False, False)
    commands.append(Command(line, conditional, needs_redstone, n, tuple(comments)))
    comments.clear()
    pending = None

  if pending:
    raise error(pending[0], "modifier must be followed directly by a command")
  if not commands:
    raise error(1, "IR has no commands")
  return commands


# ---- layout ----

def slot_at(i: int, width: int, gap: int) -> Slot:
  """Where the i-th block of the snake goes. Each block faces the next one."""
  cells = width * width
  layer, k = divmod(i, cells + gap)
  y = layer * (gap + 1)
  if k >= cells: # bridge column above this layer's last corner
    x, _, z = slot_at(layer * (cells + gap) + cells - 1, width, gap).pos
    return Slot((x, y + 1 + k - cells, z), "up", True)

  row, j = divmod(k, width)
  east = (layer * width + row) % 2 == 0 # direction alternates every row, across layers too
  forward = layer % 2 == 0 # even layers advance south, odd layers north
  x = j if east else width - 1 - j
  z = row if forward else width - 1 - row
  if j < width - 1:
    return Slot((x, y, z), "east" if east else "west", False)
  if row < width - 1:
    return Slot((x, y, z), "south" if forward else "north", False)
  return Slot((x, y, z), "up", True) # the last corner starts the bridge, so a sign never goes under it

def conditional_ok(i: int, width: int, gap: int) -> bool:
  """True if a conditional block at slot i would check slot i - 1, the block that feeds it."""
  slot = slot_at(i, width, gap)
  dx, dy, dz = FACING[slot.facing]
  x, y, z = slot.pos
  feeder = slot_at(i - 1, width, gap).pos if i > 0 else TRIGGER_POS
  return not slot.connector and (x - dx, y - dy, z - dz) == feeder

def split_groups(commands: list[Command]) -> list[list[Command]]:
  """Each unconditional command plus the conditionals right after it. Only the first group can
  start with a conditional, which then checks the user's trigger block."""
  groups: list[list[Command]] = []
  for command in commands:
    if command.conditional and groups:
      groups[-1].append(command)
    else:
      groups.append([command])
  return groups

def layout(commands: list[Command], width: int, gap: int, filename: str) -> list[Block]:
  """Places every command along the snake, padding before a group when a conditional would land
  on a turn. Raises SchemError if a run of conditionals is too long to ever fit in a row."""
  def next_cells(start: int, count: int) -> list[int]:
    cells: list[int] = []
    i = start
    while len(cells) < count:
      if not slot_at(i, width, gap).connector:
        cells.append(i)
      i += 1
    return cells

  if gap == 0:
    for command in commands:
      if command.comments:
        raise SchemError(f"{filename}:{command.line}: this command has a comment, "
                         "but its sign needs --gap 1 or more to fit above it")

  limit = max(width - 2, 0)
  placed: dict[int, Command] = {}
  i = 0
  for group in split_groups(commands):
    conditionals = sum(c.conditional for c in group)
    if conditionals > limit:
      run = f"{conditionals} conditional command{'' if conditionals == 1 else 's'}"
      if group[0].conditional:
        what = f"the chain starts with {run}"
      else:
        what = f"this command is followed by {run}"
      raise SchemError(f"{filename}:{group[0].line}: {what}, but --width {width} fits at most {limit}")

    while True:
      cells = next_cells(i, len(group))
      if all(conditional_ok(c, width, gap) for c, command in zip(cells, group) if command.conditional):
        break
      assert not group[0].conditional, "a leading conditional always fits at slot 0"
      i = cells[0] + 1 # cells[0] becomes padding
    placed.update(zip(cells, group))
    i = cells[-1] + 1

  blocks: list[Block] = []
  for i in range(max(placed) + 1):
    slot = slot_at(i, width, gap)
    blocks.append(Block(slot.pos, slot.facing, placed.get(i, EMPTY)))
  return blocks


# ---- schematic ----

def varint(value: int) -> list[int]:
  out: list[int] = []
  while True:
    byte = value & 0x7F
    value >>= 7
    if value:
      out.append(byte | 0x80)
    else:
      out.append(byte)
      return out

def block_state(block: Block) -> str:
  conditional = "true" if block.command.conditional else "false"
  return f"{CHAIN}[conditional={conditional},facing={block.facing}]"

def text_width(text: str) -> int:
  return sum(CHAR_WIDTHS.get(c, 6) for c in text)

def wrap(text: str) -> list[str]:
  """Word-wraps text to sign lines. Words too long for one line are split."""
  lines: list[str] = []
  line = ""
  for word in text.split():
    candidate = f"{line} {word}" if line else word
    if text_width(candidate) <= SIGN_LINE_WIDTH:
      line = candidate
      continue
    if line:
      lines.append(line)
    while text_width(word) > SIGN_LINE_WIDTH:
      cut = 1
      while text_width(word[:cut + 1]) <= SIGN_LINE_WIDTH:
        cut += 1
      lines.append(word[:cut])
      word = word[cut:]
    line = word
  lines.append(line) # an empty comment is a blank line
  return lines

def sign_lines(comments: tuple[str, ...]) -> list[str]:
  """All 8 lines of a sign, front then back. Each comment starts a new line; overflow is cut off."""
  lines = [line for comment in comments for line in wrap(comment)][:2 * SIGN_LINES]
  return lines + [""] * (2 * SIGN_LINES - len(lines))

def sign_entity(pos: Vec, comments: tuple[str, ...]) -> Compound:
  lines = sign_lines(comments)
  def side(messages: list[str]) -> Compound:
    return Compound({
      "messages": List[String]([String(m) for m in messages]), # a plain string is a literal text component
      "color": String("black"),
      "has_glowing_text": Byte(1),
    })
  return Compound({
    "Pos": IntArray(list(pos)),
    "Id": String(SIGN_ENTITY_ID),
    "Data": Compound({
      "front_text": side(lines[:SIGN_LINES]),
      "back_text": side(lines[SIGN_LINES:]),
      "is_waxed": Byte(1),
    }),
  })

def command_entity(block: Block, track_output: bool) -> Compound:
  return Compound({
    "Pos": IntArray(list(block.pos)),
    "Id": String(BLOCK_ENTITY_ID),
    "Data": Compound({
      "Command": String(block.command.text),
      "auto": Byte(not block.command.needs_redstone),
      "TrackOutput": Byte(track_output),
      "powered": Byte(0),
      "conditionMet": Byte(0),
      "SuccessCount": Int(0),
      "UpdateLastExecution": Byte(1),
    }),
  })

def schematic(blocks: list[Block], width: int, gap: int, track_output: bool = False) -> nbtlib.File:
  """Builds a Sponge v3 schematic. The first block must be at (0, 0, 0), the minimum corner. It
  covers the full width x width footprint, up to the sign row above the top layer."""
  length = width
  height = max(b.pos[1] for b in blocks) + 1 + (gap > 0) # signs need gap > 0, so there's no row without one

  palette = {AIR: 0}
  grid = [0] * (width * height * length)
  entities: list[Compound] = []
  def put(pos: Vec, state: str) -> None:
    x, y, z = pos
    grid[x + z * width + y * width * length] = palette.setdefault(state, len(palette))

  for block in blocks:
    put(block.pos, block_state(block))
    entities.append(command_entity(block, track_output))
    if block.command.comments:
      x, y, z = block.pos
      put((x, y + 1, z), SIGN)
      entities.append(sign_entity((x, y + 1, z), block.command.comments))
  if grid[-1] == 0:
    put((width - 1, height - 1, length - 1), MARKER)

  data = [b - 256 if b > 127 else b for index in grid for b in varint(index)] # NBT bytes are signed
  return nbtlib.File({"Schematic": Compound({
    "Version": Int(SPONGE_VERSION),
    "DataVersion": Int(DATA_VERSION),
    "Width": Short(width),
    "Height": Short(height),
    "Length": Short(length),
    "Offset": IntArray([0, 0, 0]),
    "Blocks": Compound({
      "Palette": Compound({state: Int(index) for state, index in palette.items()}),
      "Data": ByteArray(data),
      "BlockEntities": List[Compound](entities),
    }),
  })}, gzipped=True)


# ---- CLI ----

def main(argv: list[str]) -> int:
  parser = argparse.ArgumentParser(prog="uv run compile/schem.py",
    description="Turn a .mct file or its IR (.txt) into a WorldEdit schematic.")
  parser.add_argument("file", type=Path, help="a .mct file, or IR from compile.py (.txt)")
  parser.add_argument("--width", type=int, default=16, help="side length of each square layer (default 16)")
  parser.add_argument("--gap", type=int, default=3, help="empty blocks between layers (default 3)")
  parser.add_argument("--track-output", action="store_true", help="have command blocks keep their last output")
  args = parser.parse_args(argv)

  path: Path = args.file
  if args.width < 2:
    parser.error("--width must be at least 2")
  if args.gap < 0:
    parser.error("--gap must be at least 0")
  if path.suffix not in (".mct", ".txt"):
    print(f"{path}: expected a .mct or .txt file", file=sys.stderr)
    return 2
  if not path.is_file():
    print(f"{path}: file not found", file=sys.stderr)
    return 2

  try:
    if path.suffix == ".mct":
      ir = compile_source(path.read_text(encoding="utf-8"), path.name)
    else:
      ir = path.read_bytes().decode("utf-8") # read_text would translate \r\n
    commands = parse_ir(ir, path.name)
    blocks = layout(commands, args.width, args.gap, path.name)
  except (CompileError, SchemError) as e:
    print(e, file=sys.stderr)
    return 1

  OUT_DIR.mkdir(exist_ok=True)
  out_path = OUT_DIR / f"{path.stem}.schem"
  schematic(blocks, args.width, args.gap, args.track_output).save(out_path)
  empty = len(blocks) - len(commands)
  signs = sum(bool(c.comments) for c in commands)
  print(f"wrote {out_path} ({len(commands)} commands, {empty} empty blocks, {signs} signs)")
  return 0

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
