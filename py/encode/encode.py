from pathlib import Path

INPUT_FILE = "input.txt"
OUTPUT_FILE = "output.txt"
# TARGET = "@p"
TARGET = "@e[type=armor_stand,name=multiblock]"
DELIMITER = "|"

# Rotate CW = Switch x, z, then negate x
# execute as @e[type=armor_stand,name=multiblock] at @s unless block ~ ~ ~-4 air unless block ~ ~ ~-4 netherite_block run tag @s add fail
# execute as @e[type=armor_stand,name=multiblock,tag=!fail] run tag @s add move
# conditional
# {Run place command}

CODE_MAP = {
  "c": "netherite_block",
  "o": "diamond_block",
  "h": "gold_block",
}
ROTATIONS = ["0","CW-90","180","CCW-90"]
# front, right, back, left
SINGLE_OFFSETS = [(0,4), (-4,0), (0,-4), (4,0)]

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

def check_command(block, x, y, z):
  """
  x, y, z: relative coordinate offsets
  block: block to check for ex: "netherite_block"
  """
  x = x if x != 0 else ""
  y = y if y != 0 else ""
  z = z if z != 0 else ""
  return f"execute as {TARGET} at @s unless block ^{x} ^{y} ^{z} air unless block ^{x} ^{y} ^{z} {block} run tag @s add fail"
def check_empty_command(min_x, max_x, min_z, max_z, two_floors=False):
  """
  Format the command to check for an empty area.
  """
  min_x = min_x if min_x != 0 else ""
  max_x = max_x if max_x != 0 else ""
  min_z = min_z if min_z != 0 else ""
  max_z = max_z if max_z != 0 else ""
  max_y = "13" if two_floors else "6"
  return f"execute as @e[type=armor_stand,name=multiblock] at @s unless blocks ^{min_x} ^ ^{min_z} ^{max_x} ^{max_y} ^{max_z} ~ ~100 ~ all run tag @s add fail"


def generate(code:str, offsets:list[tuple[int, int]]):
  """Accept a list of tuples of size 3 starting from straight north then rotating clockwise.
  The same offsets are used for the bottom and top level.
  code is a character string starting on the bottom floor, then the top floor. The characters follow the same order as the offsets.
  """
  code = code.replace(" ", "")
  if len(code) != len(offsets) and len(code) != 2*len(offsets):
    raise ValueError(f"Code length must be either equal to offset_length or 2*offset_length")
  commands = []
  # generate check for empty command
  min_x = min(offset[0] for offset in offsets) + 1
  max_x = max(offset[0] for offset in offsets) - 1
  min_z = min(offset[1] for offset in offsets) + 1
  max_z = max(offset[1] for offset in offsets) - 1
  two_floors = len(code) == 2*len(offsets)
  commands.append(check_empty_command(min_x, max_x, min_z, max_z, two_floors))


  # first floor
  for i, offset in enumerate(offsets):
    commands.append(check_command(CODE_MAP[code[i]], offset[0], 0, offset[1]))
  # second floor
  if len(code) != 2*len(offsets):
    return commands
  for i, offset in enumerate(offsets):
    commands.append(check_command(CODE_MAP[code[i+len(offsets)]], offset[0], 7, offset[1]))
  return commands

def parse_input_line(line):
  """
  Parses an input line of the format:
  code  Ex: "cocohoho"
  label|code  Ex: "staircase_one|cocohoho"
  label|code|offsets  Ex: "staircase_one|cocohoho|0,-4 4,0 0,4 -4,0"

  Returns
  label: string or None
  code: string
  offsets: list of tuples or None. Each tuple is (x,z) coordinate offsets for directions: north, east, south, west.
  amount: the floor area of this building, in cells. Default is 1. Ex: 1x2x1 = 1, 2x2 = 4, 2x2x2 =8
  """
  words = line.strip().split(DELIMITER)
  label = None
  code = None
  offsets = None
  amount = 1
  if len(words) == 1:
    code = words[0].strip()
  if len(words) >= 2:
    label = words[0].strip()
    code = words[1].strip()
  if len(words) >= 3:
    offsets = [tuple(int(x) for x in offset.split(",")) for offset in words[2].strip().split(" ")]
  if len(words) >= 4:
    amount = int(words[3].strip())
  return label, code, offsets, amount

def main():
  output_txt = ""
  output_txt += "# Repeats for all:\n"
  output_txt += "-- Rotations:\n"
  TP_ROTATIONS = ["180", "-90", "0", "90"]
  for i in range(4):
    output_txt += f"execute as @e[type=armor_stand,name=multiblock] run rotate @s {TP_ROTATIONS[i]} 0\n"
  output_txt += "-- Run at the end:\nexecute if entity @e[type=armor_stand,name=multiblock,tag=!fail] run setblock -74 3 21 redstone_block\n"
  output_txt += "-- conditional\n{Run place command}\n"
  output_txt += "\n"

  with open(Path(__file__).with_name(INPUT_FILE), "r") as f:
    for line in f:
      # don't process emptylines and comments
      if line.strip() == "" or line.strip().startswith("#") or line.strip().startswith("--"):
        output_txt += line
        continue
      label, code, offsets, amount = parse_input_line(line)
      
      # single
      try:
        output = generate(code, SINGLE_OFFSETS if offsets is None else offsets)
        output_txt += f"# {"" if label is None else label+": "}{code}\n"
        output_txt += "\n".join(output) + "\n"
        output_txt += "{if success New random position}\n"
        # Rotations
        output_txt += "-- conditional; Rotations (choose only 1 of the 4:)\n"
        output_txt += f"execute as @e[type=armor_stand,name=multiblock] at @s run place template maze:{label} ~-3 ~ ~-3\n"
        output_txt += f"execute as @e[type=armor_stand,name=multiblock] at @s run place template maze:{label} ~3 ~ ~-3 clockwise_90\n"
        output_txt += f"execute as @e[type=armor_stand,name=multiblock] at @s run place template maze:{label} ~3 ~ ~3 180\n"
        output_txt += f"execute as @e[type=armor_stand,name=multiblock] at @s run place template maze:{label} ~-3 ~ ~3 counterclockwise_90\n"
        output_txt += "-- conditional\n"
        output_txt += f"scoreboard players remove @e[type=armor_stand,name=multiblock,tag=!fail] multiblockFill {amount}\n\n"
      except ValueError as e:
        raise ValueError(f"Error processing line: {line.strip()}\nError: {e}")
  with open(Path(__file__).with_name(OUTPUT_FILE), "w") as f:
    f.write(output_txt)

if __name__ == "__main__":
  main()