"""Tests for main.py: which stages run for each input, where output goes, and error handling."""

from pathlib import Path

import nbtlib
import pytest

import main as cli

MCT = "func $main () (\n  #-- greet\n  say hi;\n  !conditional\n  say bye;\n)\n"
IR = "#-- greet\nsay hi\n!conditional\nsay bye\n"


@pytest.fixture
def dirs(tmp_path: Path) -> Path:
  return tmp_path

def test_mct_goes_all_the_way_to_a_schematic(dirs: Path) -> None:
  (dirs / "walls.mct").write_text(MCT)
  assert cli.main([str(dirs / "walls.mct"), "--width", "4"]) == 0
  walls = nbtlib.load(dirs / "schem" / "walls.schem")["Schematic"]
  assert walls["Width"] == 4
  assert any(e["Id"] == "minecraft:sign" for e in walls["Blocks"]["BlockEntities"])
  assert not (dirs / "ir").exists() # the IR is only written with --ir

@pytest.mark.parametrize("args, size", [
  ([], (16, 16)),
  (["--width", "4"], (4, 4)),                # length defaults to width
  (["--width", "4", "--length", "7"], (4, 7)),
  (["--length", "3"], (16, 3)),
  (["--w", "4", "--l", "7"], (4, 7)),        # short aliases
])
def test_width_and_length(dirs: Path, args: list[str], size: tuple[int, int]) -> None:
  (dirs / "walls.mct").write_text(MCT)
  assert cli.main([str(dirs / "walls.mct"), *args]) == 0
  walls = nbtlib.load(dirs / "schem" / "walls.schem")["Schematic"]
  assert (walls["Width"], walls["Length"]) == size

def test_ir_flag_stops_at_ir(dirs: Path) -> None:
  (dirs / "walls.mct").write_text(MCT)
  assert cli.main(["--ir", str(dirs / "walls.mct")]) == 0
  assert (dirs / "ir" / "walls.irt").read_bytes() == IR.encode()
  assert not (dirs / "schem").exists()

def test_schem_alone_is_the_default(dirs: Path) -> None:
  (dirs / "walls.mct").write_text(MCT)
  assert cli.main(["--schem", str(dirs / "walls.mct")]) == 0
  assert (dirs / "schem" / "walls.schem").is_file()
  assert not (dirs / "ir").exists()

def test_ir_and_schem_write_both(dirs: Path) -> None:
  (dirs / "walls.mct").write_text(MCT)
  assert cli.main(["--ir", "--schem", str(dirs / "walls.mct")]) == 0
  assert (dirs / "ir" / "walls.irt").read_bytes() == IR.encode()
  assert (dirs / "schem" / "walls.schem").is_file()

def test_irt_skips_the_compiler(dirs: Path) -> None:
  (dirs / "chain.irt").write_bytes(b"say hi\n!needs_redstone\nsay bye\n")
  assert cli.main([str(dirs / "chain.irt")]) == 0
  assert (dirs / "schem" / "chain.schem").is_file()

def test_dash_o_names_the_output(dirs: Path) -> None:
  (dirs / "walls.mct").write_text(MCT)
  assert cli.main(["--ir", str(dirs / "walls.mct"), "-o", str(dirs / "x" / "y.irt")]) == 0
  assert (dirs / "x" / "y.irt").read_bytes() == IR.encode()
  assert cli.main([str(dirs / "x" / "y.irt"), "-o", str(dirs / "z.schem")]) == 0
  assert (dirs / "z.schem").is_file()

def test_ir_and_schem_on_irt_just_builds(dirs: Path) -> None:
  (dirs / "chain.irt").write_bytes(b"say hi\n")
  assert cli.main(["--ir", "--schem", str(dirs / "chain.irt")]) == 0
  assert (dirs / "schem" / "chain.schem").is_file()
  assert not (dirs / "ir").exists()

def test_several_inputs_keep_going_after_a_failure(dirs: Path, capsys: pytest.CaptureFixture[str]) -> None:
  (dirs / "bad.irt").write_bytes(b"say hi\n!conditional\n")
  (dirs / "good.mct").write_text(MCT)
  assert cli.main([str(dirs / "bad.irt"), str(dirs / "good.mct")]) == 1
  assert capsys.readouterr().err.strip() == "bad.irt:2: modifier must be followed directly by a command"
  assert not (dirs / "schem" / "bad.schem").exists()
  assert (dirs / "schem" / "good.schem").is_file()

def test_compile_errors_are_reported(dirs: Path, capsys: pytest.CaptureFixture[str]) -> None:
  (dirs / "empty.mct").write_text("-- nothing\n")
  assert cli.main(["--ir", str(dirs / "empty.mct")]) == 1
  assert capsys.readouterr().err.strip() == "empty.mct: missing func $main ()"
  assert not (dirs / "ir").exists()

@pytest.mark.parametrize("args", [
  ["a.irt", "--width", "1"],
  ["a.irt", "--length", "0"],
  ["a.irt", "--gap", "-1"],
  ["--ir", "a.irt"],            # already IR
  ["--ir", "--schem", "a.mct", "-o", "x"], # -o with two outputs
  ["a.mct", "b.mct", "-o", "x"], # -o with several inputs
  ["a.txt"],                    # unknown extension
  ["missing.mct"],              # file not found
])
def test_usage_errors(dirs: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
  monkeypatch.chdir(dirs)
  for name in ("a.irt", "a.mct", "b.mct", "a.txt"):
    (dirs / name).write_text(MCT)
  with pytest.raises(SystemExit) as info:
    cli.main(args)
  assert info.value.code == 2
  assert not (dirs / "schem").exists()

def test_src_and_ir_write_next_to_their_folder(dirs: Path) -> None:
  (dirs / "src").mkdir()
  (dirs / "src" / "walls.mct").write_text(MCT)
  assert cli.main(["--ir", "--schem", str(dirs / "src" / "walls.mct")]) == 0
  assert (dirs / "ir" / "walls.irt").read_bytes() == IR.encode()
  assert (dirs / "schem" / "walls.schem").is_file()
  (dirs / "schem" / "walls.schem").unlink()
  assert cli.main([str(dirs / "ir" / "walls.irt")]) == 0
  assert (dirs / "schem" / "walls.schem").is_file()
