from dataclasses import dataclass
from pathlib import Path

import yaml

INPUT_FILE = "input.yaml"
OUTPUT_FILE = "output.txt"
# TARGET = "@p"
TARGET = "@e[type=armor_stand,name=multiblock]"

# Rotate CW = Switch x, z, then negate x
# execute as @e[type=armor_stand,name=multiblock] at @s unless block ~ ~ ~-4 air unless block ~ ~ ~-4 netherite_block run tag @s add fail
# execute as @e[type=armor_stand,name=multiblock,tag=!fail] run tag @s add move
# conditional
# {Run place command}

type Offset = tuple[int, int]
"""(x, z) offset of a check block"""

CODE_MAP: dict[str, str] = {
  "c": "netherite_block",
  "o": "diamond_block",
  "h": "gold_block",
}
ROTATIONS = ["0","CW-90","180","CCW-90"]
# front, right, back, left
SINGLE_OFFSETS: list[Offset] = [(0,4), (-4,0), (0,-4), (4,0)]

# def rotate_tup_clockwise(tup):
#   return (-tup[1], tup[0])

# def rotate_string_clockwise(code,offset_length):
#   """Rotates a string code clockwise.
#   code: string to rotate.
#   offset_length:int the length of the offsets list, which is used to determine where to split the string into floors.
#   """
#   if len(code) == offset_length:
#     return code[offset_length-1] + code[0:offset_length-1]
#   elif len(code) == 2*offset_length:
#     return code[offset_length-1] + code[0:offset_length-1] + code[offset_length*2-1] + code[offset_length:offset_length*2-1]
#   else:
#     raise ValueError("Code length must be either equal to offset_length or 2*offset_length")


@dataclass
class Building:
  name: str
  floors: list[str]
  """code strings, bottom floor first. The characters follow the same order as the offsets."""
  note: str | None = None

@dataclass
class Group:
  """Buildings that share the same offsets and fill."""
  buildings: list[Building]
  offsets: list[Offset]
  fill: int = 1
  """the floor area of these buildings, in cells. Ex: 1x2x1 = 1, 2x2 = 4, 2x2x2 =8"""
  size: str | None = None
  note: str | None = None


def optional_str(value: object) -> str | None:
  return None if value is None else str(value)

def parse_offsets(raw: object) -> list[Offset]:
  if not isinstance(raw, list):
    raise ValueError(f"offsets must be a list of [x, z] pairs, got: {raw!r}")
  offsets: list[Offset] = []
  for item in raw:
    if not (isinstance(item, list) and len(item) == 2 and all(isinstance(n, int) for n in item)):
      raise ValueError(f"Each offset must be [x, z], got: {item!r}")
    offsets.append((item[0], item[1]))
  return offsets

def parse_building(name: str, raw: object) -> Building:
  """
  A building in the yaml is either a list of floors, Ex: [coccoh, hhcoch]
  or a mapping with floors and an optional note, Ex: {floors: [coccoh, hhcoch], note: "..."}
  """
  if isinstance(raw, list):
    floors, note = raw, None
  elif isinstance(raw, dict) and isinstance(raw.get("floors"), list):
    floors, note = raw["floors"], raw.get("note")
  else:
    raise ValueError(f"Building {name}: expected a list of floors or {{floors: [...], note: ...}}, got: {raw!r}")
  return Building(name, [str(floor) for floor in floors], optional_str(note))

def parse_group(raw: object) -> Group:
  if not isinstance(raw, dict) or not isinstance(raw.get("buildings"), dict):
    raise ValueError(f"Each group needs a buildings mapping, got: {raw!r}")
  fill = raw.get("fill", 1)
  if not isinstance(fill, int):
    raise ValueError(f"fill must be a whole number, got: {fill!r}")
  return Group(
    buildings=[parse_building(str(name), building) for name, building in raw["buildings"].items()],
    offsets=parse_offsets(raw["offsets"]) if "offsets" in raw else list(SINGLE_OFFSETS),
    fill=fill,
    size=optional_str(raw.get("size")),
    note=optional_str(raw.get("note")),
  )

def load_input(path: Path) -> dict[str, list[Group]]:
  """Reads the yaml file into a mapping of section name -> groups."""
  with open(path, "r") as f:
    raw: object = yaml.safe_load(f)
  if not isinstance(raw, dict):
    raise ValueError(f"{path.name} must map section names to lists of groups")
  sections: dict[str, list[Group]] = {}
  for section, groups in raw.items():
    if not isinstance(groups, list):
      raise ValueError(f"Section {section} must be a list of groups, got: {groups!r}")
    try:
      sections[str(section)] = [parse_group(group) for group in groups]
    except ValueError as e:
      raise ValueError(f"Error in section {section}: {e}")
  return sections


def rel(n: int) -> str:
  """Formats a relative coordinate, leaving 0 blank so ^0 is written as ^."""
  return str(n) if n != 0 else ""

def check_command(block: str, x: int, y: int, z: int) -> str:
  """
  x, y, z: relative coordinate offsets
  block: block to check for ex: "netherite_block"
  """
  pos = f"^{rel(x)} ^{rel(y)} ^{rel(z)}"
  return f"execute as {TARGET} at @s unless block {pos} air unless block {pos} {block} run tag @s add fail"

def check_empty_command(min_x: int, max_x: int, min_z: int, max_z: int, two_floors: bool = False) -> str:
  """
  Format the command to check for an empty area.
  """
  max_y = "13" if two_floors else "6"
  return f"execute as @e[type=armor_stand,name=multiblock] at @s unless blocks ^{rel(min_x)} ^ ^{rel(min_z)} ^{rel(max_x)} ^{max_y} ^{rel(max_z)} ~ ~100 ~ all run tag @s add fail"


def generate(floors: list[str], offsets: list[Offset]) -> list[str]:
  """Accept a list of (x, z) offsets starting from straight north then rotating clockwise.
  The same offsets are used for the bottom and top level.
  floors is a list of 1 or 2 code strings, bottom floor first. The characters follow the same order as the offsets.
  """
  if len(floors) not in (1, 2):
    raise ValueError(f"A building must have 1 or 2 floors, got {len(floors)}")
  for floor in floors:
    if len(floor) != len(offsets):
      raise ValueError(f"Floor {floor!r} has {len(floor)} blocks but there are {len(offsets)} offsets")
    for char in floor:
      if char not in CODE_MAP:
        raise ValueError(f"Unknown block code {char!r} in floor {floor!r}")
  commands: list[str] = []
  # generate check for empty command
  min_x = min(offset[0] for offset in offsets) + 1
  max_x = max(offset[0] for offset in offsets) - 1
  min_z = min(offset[1] for offset in offsets) + 1
  max_z = max(offset[1] for offset in offsets) - 1
  two_floors = len(floors) == 2
  commands.append(check_empty_command(min_x, max_x, min_z, max_z, two_floors))

  for floor, y in zip(floors, (0, 7)):
    for char, (x, z) in zip(floor, offsets):
      commands.append(check_command(CODE_MAP[char], x, y, z))
  return commands

def building_commands(building: Building, offsets: list[Offset], amount: int) -> str:
  """All output lines for one building, ending in a blank line."""
  label = building.name
  output_txt = f"# {label}: {' '.join(building.floors)}\n"
  output_txt += "\n".join(generate(building.floors, offsets)) + "\n"
  output_txt += "{if success New random position}\n"
  # Rotations
  output_txt += "-- conditional; Rotations (choose only 1 of the 4:)\n"
  output_txt += f"execute as @e[type=armor_stand,name=multiblock] at @s run place template maze:{label} ~-3 ~ ~-3\n"
  output_txt += f"execute as @e[type=armor_stand,name=multiblock] at @s run place template maze:{label} ~3 ~ ~-3 clockwise_90\n"
  output_txt += f"execute as @e[type=armor_stand,name=multiblock] at @s run place template maze:{label} ~3 ~ ~3 180\n"
  output_txt += f"execute as @e[type=armor_stand,name=multiblock] at @s run place template maze:{label} ~-3 ~ ~3 counterclockwise_90\n"
  output_txt += "-- conditional\n"
  output_txt += f"scoreboard players remove @e[type=armor_stand,name=multiblock,tag=!fail] multiblockFill {amount}\n\n"
  return output_txt

def group_commands(group: Group) -> str:
  """Headers and commands for every building in a group."""
  output_txt = ""
  if group.size is not None:
    output_txt += f"-- {group.size}\n"
  if group.note is not None:
    output_txt += f"-- {group.note}\n"
  previous_floor_count: int | None = None
  for building in group.buildings:
    floor_count = len(building.floors)
    # print a "-- 2 floors" header whenever the floor count changes within a group
    if previous_floor_count is not None and floor_count != previous_floor_count:
      output_txt += f"-- {floor_count} floor{'s' if floor_count > 1 else ''}\n"
    previous_floor_count = floor_count
    if building.note is not None:
      output_txt += f"-- {building.note}\n"
    try:
      output_txt += building_commands(building, group.offsets, group.fill)
    except ValueError as e:
      raise ValueError(f"Error processing building {building.name}: {e}")
  return output_txt

def main() -> None:
  output_txt = ""
  output_txt += "# Repeats for all:\n"
  output_txt += "-- Rotations:\n"
  TP_ROTATIONS = ["180", "-90", "0", "90"]
  for rotation in TP_ROTATIONS:
    output_txt += f"execute as @e[type=armor_stand,name=multiblock] run rotate @s {rotation} 0\n"
  output_txt += "-- Run at the end:\nexecute if entity @e[type=armor_stand,name=multiblock,tag=!fail] run setblock -74 3 21 redstone_block\n"
  output_txt += "-- conditional\n{Run place command}\n"
  output_txt += "\n"

  sections = load_input(Path(__file__).with_name(INPUT_FILE))
  for section, groups in sections.items():
    output_txt += f"# {section.capitalize()}\n"
    for group in groups:
      output_txt += group_commands(group)

  with open(Path(__file__).with_name(OUTPUT_FILE), "w") as f:
    f.write(output_txt)

if __name__ == "__main__":
  main()
