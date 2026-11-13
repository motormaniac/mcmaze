"""Tests for schem.py: IR parsing, the snake layout, conditional padding, signs and the schematic file."""

import random
from pathlib import Path

import nbtlib
import pytest

import schem
from schem import (FACING, MARKER, SIGN, SIGN_LINE_WIDTH, TRIGGER_POS, Command, SchemError, layout,
                   main, parse_ir, schematic, sign_lines, slot_at, text_width, wrap)

CHAIN = "minecraft:chain_command_block"


def add(a: tuple[int, int, int], b: tuple[int, int, int]) -> tuple[int, int, int]:
  return (a[0] + b[0], a[1] + b[1], a[2] + b[2])

def commands(*flags: bool) -> list[Command]:
  """One command per flag, conditional when the flag is True."""
  return [Command(f"say {i}", conditional, False, i + 1) for i, conditional in enumerate(flags)]

def decode_varints(data: list[int]) -> list[int]:
  values: list[int] = []
  value = shift = 0
  for byte in data:
    byte = int(byte) & 0xFF
    value |= (byte & 0x7F) << shift
    shift += 7
    if not byte & 0x80:
      values.append(value)
      value = shift = 0
  return values

def load(blocks: list[schem.Block], width: int, gap: int, tmp_path: Path, **kwargs: bool):
  """Saves and reloads a schematic. Returns (root, states by (x, y, z), entities by (x, y, z))."""
  path = tmp_path / "a.schem"
  schematic(blocks, width, gap, **kwargs).save(path)
  root = nbtlib.load(path)["Schematic"]
  w, h, l = int(root["Width"]), int(root["Height"]), int(root["Length"])
  palette = {int(index): state for state, index in root["Blocks"]["Palette"].items()}
  indices = decode_varints(list(root["Blocks"]["Data"]))
  assert len(indices) == w * h * l
  states = {(x, y, z): palette[indices[x + z * w + y * w * l]]
            for y in range(h) for z in range(l) for x in range(w)}
  entities = {tuple(int(v) for v in e["Pos"]): e for e in root["Blocks"]["BlockEntities"]}
  return root, states, entities


# ---- IR ----

def test_parse_ir_example_from_lang_md() -> None:
  ir = (
    "#-- place the walls\n"
    "execute if entity @e[tag=!fail]\n"
    "!conditional\n"
    "place template maze:walls ~ ~ ~\n"
    "!conditional, needs_redstone\n"
    "say \"placed walls\"\n"
  )
  assert parse_ir(ir, "walls.txt") == [
    Command("execute if entity @e[tag=!fail]", False, False, 2, ("place the walls",)),
    Command("place template maze:walls ~ ~ ~", True, False, 4),
    Command("say \"placed walls\"", True, True, 6),
  ]

def test_parse_ir_needs_redstone_only() -> None:
  assert parse_ir("!needs_redstone\nsay hi\n", "a.txt") == [Command("say hi", False, True, 2)]

def test_comments_attach_to_the_command_below() -> None:
  ir = "#-- one\n#--two\n#--\n!conditional\nsay a\nsay b\n#-- end\n"
  assert [c.comments for c in parse_ir(ir, "a.txt")] == [("one", "two", ""), ()] # "end" is dropped

@pytest.mark.parametrize("ir, error", [
  ("say hi", "a.txt:1: IR must end with a newline"),
  ("say hi\r\n", "a.txt:1: IR must use \\n line endings"),
  ("say hi\n\nsay bye\n", "a.txt:2: blank line"),
  ("!conditional\n", "a.txt:1: modifier must be followed directly by a command"),
  ("!conditional\n#-- note\nsay hi\n", "a.txt:1: modifier must be followed directly by a command"),
  ("!conditional\n!needs_redstone\nsay hi\n", "a.txt:1: modifier must be followed directly by a command"),
  ("!needs_redstone, conditional\nsay hi\n", "a.txt:1: invalid modifier '!needs_redstone, conditional'"),
  ("!conditional,needs_redstone\nsay hi\n", "a.txt:1: invalid modifier '!conditional,needs_redstone'"),
  (" say hi\n", "a.txt:1: command has leading or trailing whitespace"),
  ("#-- only a comment\n", "a.txt:1: IR has no commands"),
  ("", "a.txt:1: IR must end with a newline"),
])
def test_parse_ir_rejects(ir: str, error: str) -> None:
  with pytest.raises(SchemError) as info:
    parse_ir(ir, "a.txt")
  assert str(info.value) == error


# ---- layout ----

def test_first_layer_of_width_3() -> None:
  slots = [slot_at(i, 3, 2) for i in range(9)]
  assert [(s.pos, s.facing) for s in slots] == [
    ((0, 0, 0), "east"), ((1, 0, 0), "east"), ((2, 0, 0), "south"),
    ((2, 0, 1), "west"), ((1, 0, 1), "west"), ((0, 0, 1), "south"),
    ((0, 0, 2), "east"), ((1, 0, 2), "east"), ((2, 0, 2), "up"),
  ]
  assert [s.connector for s in slots] == [False] * 8 + [True] # the last corner is part of the bridge

def test_bridge_and_mirrored_second_layer() -> None:
  # width 3 ends layer 0 at the southeast corner; gap 2 puts layer 1 at y = 3
  assert [(slot_at(i, 3, 2).pos, slot_at(i, 3, 2).connector) for i in (9, 10)] == [
    ((2, 1, 2), True), ((2, 2, 2), True),
  ]
  layer1 = [slot_at(i, 3, 2) for i in range(11, 20)]
  assert [(s.pos, s.facing) for s in layer1] == [
    ((2, 3, 2), "west"), ((1, 3, 2), "west"), ((0, 3, 2), "north"),
    ((0, 3, 1), "east"), ((1, 3, 1), "east"), ((2, 3, 1), "north"),
    ((2, 3, 0), "west"), ((1, 3, 0), "west"), ((0, 3, 0), "up"),
  ]

def test_even_width_ends_layer_in_southwest_corner() -> None:
  assert slot_at(15, 4, 3).pos == (0, 0, 3)
  assert slot_at(15, 4, 3).facing == "up"
  assert slot_at(19, 4, 3).pos == (0, 4, 3) # first block of layer 1, after 3 bridge blocks above the corner
  assert slot_at(19, 4, 3).facing == "east"

@pytest.mark.parametrize("width", [2, 3, 4, 5, 16])
@pytest.mark.parametrize("gap", [0, 1, 3])
def test_every_block_points_at_the_next(width: int, gap: int) -> None:
  for i in range(3 * (width * width + gap)):
    here, there = slot_at(i, width, gap), slot_at(i + 1, width, gap)
    assert add(here.pos, FACING[here.facing]) == there.pos, i

@pytest.mark.parametrize("width", [2, 3, 4, 16])
@pytest.mark.parametrize("gap", [0, 3])
def test_layout_stays_inside_layers(width: int, gap: int) -> None:
  blocks = layout(commands(*[False] * 100), width, gap, "a.txt")
  assert blocks[0].pos == (0, 0, 0)
  assert all(0 <= b.pos[0] < width and 0 <= b.pos[2] < width and b.pos[1] >= 0 for b in blocks)
  assert len({b.pos for b in blocks}) == len(blocks)

def test_bridge_corner_is_always_empty() -> None:
  blocks = layout(commands(*[False] * 10), 3, 3, "a.txt")
  assert [b.command.text for b in blocks] == (
    [f"say {i}" for i in range(8)] + ["", "", "", ""] + ["say 8", "say 9"] # corner + 3 bridge blocks
  )
  assert blocks[8].pos == (2, 0, 2)

@pytest.mark.parametrize("seed", range(10))
def test_no_command_ever_sits_on_a_bridge(seed: int) -> None:
  rng = random.Random(seed)
  width, gap = rng.randint(2, 6), rng.randint(0, 3)
  for i, block in enumerate(layout(commands(*[False] * 200), width, gap, "a.txt")):
    if slot_at(i, width, gap).connector:
      assert block.command.text == ""

def test_no_bridge_when_chain_ends_before_the_corner() -> None:
  assert len(layout(commands(*[False] * 8), 3, 3, "a.txt")) == 8

def test_commands_can_sit_on_turns() -> None:
  blocks = layout(commands(*[False] * 4), 3, 3, "a.txt")
  assert [(b.pos, b.facing, b.command.text) for b in blocks][2:4] == [
    ((2, 0, 0), "south", "say 2"), ((2, 0, 1), "west", "say 3"),
  ]

def test_conditional_on_turn_is_padded() -> None:
  # width 4: say 3 would land on (3, 0, 0), the turn, so say 2 and say 3 shift to the next row
  blocks = layout(commands(False, False, False, True), 4, 3, "a.txt")
  assert [b.command.text for b in blocks] == ["say 0", "say 1", "", "", "say 2", "say 3"]
  assert blocks[5].pos == (2, 0, 1)

def test_conditional_on_first_block_of_layer_is_padded() -> None:
  # width 3, gap 0: slots 0-7 are layer 0, slot 8 is its corner, slot 9 starts layer 1
  blocks = layout(commands(*[False] * 8, True), 3, 0, "a.txt")
  assert [b.command.text for b in blocks] == [f"say {i}" for i in range(7)] + ["", "", "say 7", "say 8"]
  assert blocks[9].pos[1] == 1 # say 7 starts layer 1, and say 8 follows it

def test_leading_conditional_checks_the_trigger() -> None:
  blocks = layout(commands(True, False), 4, 3, "a.txt")
  assert [b.command.text for b in blocks] == ["say 0", "say 1"]
  assert add(blocks[0].pos, (-1, 0, 0)) == TRIGGER_POS

def test_longest_conditional_run_fits() -> None:
  blocks = layout(commands(False, False, True, True), 4, 3, "a.txt")
  heads = [b for b in blocks if b.command.text == "say 1"]
  assert heads[0].pos == (3, 0, 1) # padded to the start of row 1

@pytest.mark.parametrize("width, flags, error", [
  (4, (False, True, True, True), "a.txt:1: this command is followed by 3 conditional commands, but --width 4 fits at most 2"),
  (2, (False, True), "a.txt:1: this command is followed by 1 conditional command, but --width 2 fits at most 0"),
  (3, (True, True), "a.txt:1: the chain starts with 2 conditional commands, but --width 3 fits at most 1"),
])
def test_too_many_conditionals(width: int, flags: tuple[bool, ...], error: str) -> None:
  with pytest.raises(SchemError) as info:
    layout(commands(*flags), width, 3, "a.txt")
  assert str(info.value) == error

def test_comments_need_a_gap() -> None:
  cmds = [Command("say a", line=1), Command("say b", line=3, comments=("hi",))]
  with pytest.raises(SchemError) as info:
    layout(cmds, 4, 0, "a.txt")
  assert str(info.value) == "a.txt:3: this command has a comment, but its sign needs --gap 1 or more to fit above it"

@pytest.mark.parametrize("seed", range(50))
def test_every_conditional_checks_its_predecessor(seed: int) -> None:
  rng = random.Random(seed)
  width, gap = rng.randint(3, 7), rng.randint(0, 4)
  flags: list[bool] = []
  while len(flags) < 150:
    flags.append(False)
    flags.extend([True] * rng.randint(0, width - 2) if rng.random() < 0.4 else [])
  cmds = commands(*flags)
  blocks = layout(cmds, width, gap, "a.txt")

  assert [b.command for b in blocks if b.command.text] == cmds # same commands, same order
  by_pos = {b.pos: b for b in blocks}
  for b in blocks:
    if b.command.conditional:
      dx, dy, dz = FACING[b.facing]
      behind = by_pos.get((b.pos[0] - dx, b.pos[1] - dy, b.pos[2] - dz))
      expected = cmds[cmds.index(b.command) - 1] if cmds.index(b.command) > 0 else None
      assert (behind.command if behind else None) == expected


# ---- sign text ----

def test_short_comment_is_one_line() -> None:
  assert wrap("place the walls") == ["place the walls"]

def test_wrap_breaks_between_words_and_fits_the_sign() -> None:
  text = "this comment is much too long to fit on a single line of a sign"
  lines = wrap(text)
  assert len(lines) > 1
  assert " ".join(lines) == text
  assert all(text_width(line) <= SIGN_LINE_WIDTH for line in lines)

def test_wrap_splits_a_word_longer_than_a_line() -> None:
  lines = wrap("a" * 40)
  assert "".join(lines) == "a" * 40
  assert all(text_width(line) <= SIGN_LINE_WIDTH for line in lines)

def test_narrow_characters_fit_more_per_line() -> None:
  assert wrap("i" * 45) == ["i" * 45] # 2px each

def test_each_comment_starts_a_new_line() -> None:
  assert sign_lines(("a", "b")) == ["a", "b", "", "", "", "", "", ""]

def test_sign_text_is_cut_off_after_8_lines() -> None:
  lines = sign_lines(tuple(f"line {i}" for i in range(10)))
  assert lines == [f"line {i}" for i in range(8)]


# ---- schematic ----

def test_schematic_round_trip(tmp_path: Path) -> None:
  cmds = [Command("say a"), Command("say b", True, True), Command("say c"), Command("say d"), Command("say e")]
  blocks = layout(cmds, 3, 1, "a.txt") # row 0 east, then row 1 back west
  root, states, entities = load(blocks, 3, 1, tmp_path, track_output=True)

  assert root["Version"] == 3
  assert root["DataVersion"] == 4556
  assert (root["Width"], root["Height"], root["Length"]) == (3, 2, 3) # full footprint + sign row
  assert [int(v) for v in root["Offset"]] == [0, 0, 0]

  assert {pos: state for pos, state in states.items() if state != "minecraft:air"} == {
    (0, 0, 0): f"{CHAIN}[conditional=false,facing=east]",  # say a
    (1, 0, 0): f"{CHAIN}[conditional=true,facing=east]",   # say b
    (2, 0, 0): f"{CHAIN}[conditional=false,facing=south]", # say c
    (2, 0, 1): f"{CHAIN}[conditional=false,facing=west]",  # say d
    (1, 0, 1): f"{CHAIN}[conditional=false,facing=west]",  # say e
    (2, 1, 2): MARKER,
  }

  assert set(entities) == {(0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 0, 1), (1, 0, 1)}
  b = entities[(1, 0, 0)]
  assert b["Id"] == "minecraft:command_block"
  assert b["Data"]["Command"] == "say b"
  assert b["Data"]["auto"] == 0
  assert b["Data"]["TrackOutput"] == 1
  assert entities[(0, 0, 0)]["Data"]["auto"] == 1
  assert entities[(1, 0, 1)]["Data"]["Command"] == "say e"

def test_sign_goes_on_top_of_its_command(tmp_path: Path) -> None:
  long = "a comment long enough that it has to wrap onto more than one line of the sign"
  cmds = [Command("say a"), Command("say b", comments=("short", long))]
  _, states, entities = load(layout(cmds, 4, 3, "a.txt"), 4, 3, tmp_path)

  assert states[(1, 1, 0)] == SIGN
  assert states[(0, 1, 0)] == "minecraft:air" # no comment, no sign
  sign = entities[(1, 1, 0)]
  assert sign["Id"] == "minecraft:sign"
  assert sign["Data"]["is_waxed"] == 1
  assert sign["Data"]["front_text"]["has_glowing_text"] == 1
  assert sign["Data"]["back_text"]["has_glowing_text"] == 1
  front = list(sign["Data"]["front_text"]["messages"])
  back = list(sign["Data"]["back_text"]["messages"])
  assert front + back == sign_lines(("short", long))
  assert front[0] == "short"

def test_footprint_is_always_the_full_layer(tmp_path: Path) -> None:
  root, states, _ = load(layout([Command("say a")], 16, 3, "a.txt"), 16, 3, tmp_path)
  assert (root["Width"], root["Height"], root["Length"]) == (16, 2, 16)
  assert states[(15, 1, 15)] == MARKER

def test_marker_is_skipped_when_the_corner_is_taken(tmp_path: Path) -> None:
  # width 2, gap 0: the third command lands on (1, 0, 1), which is the +x +y +z corner
  root, states, _ = load(layout(commands(False, False, False), 2, 0, "a.txt"), 2, 0, tmp_path)
  assert (root["Width"], root["Height"], root["Length"]) == (2, 1, 2)
  assert states[(1, 0, 1)].startswith(CHAIN)
  assert MARKER not in states.values()

def test_schematic_track_output_off_by_default() -> None:
  root = schematic(layout([Command("say a")], 16, 3, "a.txt"), 16, 3)["Schematic"]
  assert root["Blocks"]["BlockEntities"][0]["Data"]["TrackOutput"] == 0

def test_large_palette_index_is_varint_encoded() -> None:
  assert schem.varint(0) == [0]
  assert schem.varint(127) == [127]
  assert schem.varint(128) == [0x80, 0x01]
  assert decode_varints([b - 256 if b > 127 else b for b in schem.varint(300)]) == [300]


# ---- CLI ----

def test_main_builds_from_mct_and_ir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setattr(schem, "OUT_DIR", tmp_path / "out")
  mct = tmp_path / "walls.mct"
  mct.write_text("func $main () (\n  #-- greet\n  say hi;\n  !conditional\n  say bye;\n)\n")
  ir = tmp_path / "chain.txt"
  ir.write_bytes(b"say hi\n!needs_redstone\nsay bye\n")

  assert main([str(mct), "--width", "4"]) == 0
  assert main([str(ir)]) == 0
  walls = nbtlib.load(tmp_path / "out" / "walls.schem")["Schematic"]
  assert walls["Width"] == 4
  assert any(e["Id"] == "minecraft:sign" for e in walls["Blocks"]["BlockEntities"])
  assert (tmp_path / "out" / "chain.schem").is_file()

def test_main_reports_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                             capsys: pytest.CaptureFixture[str]) -> None:
  monkeypatch.setattr(schem, "OUT_DIR", tmp_path / "out")
  ir = tmp_path / "bad.txt"
  ir.write_bytes(b"say hi\n!conditional\n")
  assert main([str(ir)]) == 1
  assert capsys.readouterr().err.strip() == "bad.txt:2: modifier must be followed directly by a command"
  assert not (tmp_path / "out").exists()

def test_main_rejects_width_1(tmp_path: Path) -> None:
  ir = tmp_path / "a.txt"
  ir.write_bytes(b"say hi\n")
  with pytest.raises(SystemExit):
    main([str(ir), "--width", "1"])
