"""The command line for the .mct toolchain. See LANG.md.

  cd py
  uv run compile/main.py compile/in/walls.mct               -- .mct -> compile/out/walls.schem
  uv run compile/main.py --ir compile/in/walls.mct          -- .mct -> compile/ir/walls.irt
  uv run compile/main.py --ir --schem compile/in/walls.mct  -- .mct -> both of the above
  uv run compile/main.py compile/ir/walls.irt               -- .irt -> compile/out/walls.schem
  options: -o PATH  --width 16  --length 16  --gap 3  --track-output

Like gcc, where each file starts depends on its extension: a .mct file goes through the compiler
(compile.py) and then the schematic builder (schem.py), and a .irt file only goes through the builder.
--ir and --schem pick which files get written. With neither, only the schematic is.
"""

import argparse
import sys
from pathlib import Path

from compile import CompileError, compile_source
from schem import SchemError, layout, parse_ir, schematic

HERE = Path(__file__).parent
IR_DIR = HERE / "ir"
OUT_DIR = HERE / "out"


def write_ir(ir: str, out_path: Path) -> None:
  out_path.parent.mkdir(parents=True, exist_ok=True)
  out_path.write_text(ir, encoding="utf-8", newline="\n")
  print(f"wrote {out_path}")

def build(path: Path, args: argparse.Namespace) -> None:
  """Runs one input file through the chain. Raises CompileError or SchemError."""
  if path.suffix == ".mct":
    ir = compile_source(path.read_text(encoding="utf-8"), path.name)
    if args.ir:
      write_ir(ir, args.o or IR_DIR / f"{path.stem}.irt")
    if not args.schem:
      return
  else:
    ir = path.read_bytes().decode("utf-8") # read_text would translate \r\n

  commands = parse_ir(ir, path.name)
  blocks = layout(commands, args.width, args.length, args.gap, path.name)
  out_path = args.o or OUT_DIR / f"{path.stem}.schem"
  out_path.parent.mkdir(parents=True, exist_ok=True)
  schematic(blocks, args.width, args.length, args.gap, args.track_output).save(out_path)
  empty = len(blocks) - len(commands)
  signs = sum(bool(c.comments) for c in commands)
  print(f"wrote {out_path} ({len(commands)} commands, {empty} empty blocks, {signs} signs)")

def main(argv: list[str]) -> int:
  parser = argparse.ArgumentParser(prog="uv run compile/main.py",
    description="Compile .mct files to IR (.irt) and build WorldEdit schematics (.schem).")
  parser.add_argument("files", type=Path, nargs="+", metavar="file", help="a .mct source or .irt IR file")
  parser.add_argument("--ir", action="store_true", help="write the IR of each .mct file to compile/ir/")
  parser.add_argument("--schem", action="store_true",
    help="write a schematic to compile/out/ (the default, unless --ir is given)")
  parser.add_argument("-o", type=Path, metavar="PATH",
    help="write the output here (only with one input file and one of --ir/--schem)")
  parser.add_argument("--width", type=int, default=16, help="blocks in each row, east-west (x) (default 16)")
  parser.add_argument("--length", type=int,
    help="rows in each layer, north-south (z) (default: same as --width)")
  parser.add_argument("--gap", type=int, default=3, help="empty blocks between layers (default 3)")
  parser.add_argument("--track-output", action="store_true", help="have command blocks keep their last output")
  args = parser.parse_args(argv)
  if not args.ir:
    args.schem = True
  if args.length is None:
    args.length = args.width

  if args.width < 2:
    parser.error("--width must be at least 2")
  if args.length < 1:
    parser.error("--length must be at least 1")
  if args.gap < 0:
    parser.error("--gap must be at least 0")
  if args.o and len(args.files) > 1:
    parser.error("-o can only be used with one input file")
  if args.o and args.ir and args.schem:
    parser.error("-o can't name both outputs, so use it with only one of --ir and --schem")
  for path in args.files:
    if path.suffix not in (".mct", ".irt"):
      parser.error(f"{path}: expected a .mct or .irt file")
    if path.suffix == ".irt" and not args.schem:
      parser.error(f"{path}: already IR, so --ir alone has nothing to do")
    if not path.is_file():
      parser.error(f"{path}: file not found")

  status = 0
  for path in args.files: # like gcc, keep going after a failed file
    try:
      build(path, args)
    except (CompileError, SchemError) as e:
      print(e, file=sys.stderr)
      status = 1
  return status

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
