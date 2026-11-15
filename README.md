# Codebase for the Minecraft Maze Generate Map
## Running the Python scripts
The repo root is a [uv](https://docs.astral.sh/uv/) project. Run everything with `uv run` from the repo root:
```
uv run tools/book/book.py
uv run tools/encode/encode.py
uv run pytest
```
The first `uv run` sets up the Python environment automatically, so there's nothing to install beforehand besides uv itself.

### Tasks
Shortcuts for common commands are defined under `[tool.poe.tasks]` in [pyproject.toml](pyproject.toml) and run with [Poe the Poet](https://poethepoet.natn.io/). Anything after the task name is passed through to the script, and file paths are relative to the folder you run the task from.
```
uv run poe build                                 # download the room sheet, then build every maze2 IR file and schematic
uv run poe mct-all                               # same, without downloading the sheet first
uv run poe rooms                                 # room sheet -> maze2/ir/lookups.irt and place.irt
uv run poe rooms maze2/manual_test/test_rooms.csv # same, from a CSV instead of the sheet
uv run poe cases                                 # rewrite maze2/manual_test/test_rooms.csv
uv run poe sim check maze2/manual_test/test_rooms.csv
uv run poe                                       # list all tasks
```

`poe mct` compiles one file. Output goes to the `ir/` and `schem/` folders next to the input's `src/` (or `ir/`) folder, so maze2 files always land in `maze2/ir/` and `maze2/schem/`:
```
uv run poe mct maze2/src/maze2.mct              # .mct -> maze2/schem/maze2.schem
uv run poe mct --ir maze2/src/maze2.mct         # .mct -> maze2/ir/maze2.irt
uv run poe mct --ir --schem maze2/src/maze2.mct # .mct -> both the IR and the schematic
uv run poe mct maze2/ir/maze2.irt               # IR -> schematic, skipping the compiler
uv run poe mct maze2/src/maze2.mct -o maze.schem --width 16 --length 8 --gap 3 --track-output
```

## File Layout
- [maze2/](maze2/) - everything for the new maze generator. See [maze2/README.md](maze2/README.md)
  - [src/](maze2/src/) - the `.mct` sources for the maze2 command chains
  - [rooms/](maze2/rooms/) - the room sheet and the script that turns it into lookup and place IR
  - [sim/](maze2/sim/) - a Python simulator of the algorithm, for checking test cases before running them in game
  - [manual_test/](maze2/manual_test/) - the in-game test plan and its rooms
  - `ir/`, `schem/` - generated IR and schematics (gitignored)
- [commands/](commands/) - txt files containing the other commands used within the world
  - [game.txt](commands/game.txt) - game loop logic
  - [items.txt](commands/items.txt) - item logic
  - [maze.txt](commands/maze.txt) - maze generation (maze1)
  - [tutorial.txt](commands/tutorial.txt) - (unused) the commands for the tutorial
- [tools/](tools/) - general tools that aren't tied to one feature
  - [mct/](tools/mct/) - the `.mct` compiler and schematic builder. The language is described in [LANG.md](tools/mct/LANG.md)
    - [vscode/](tools/mct/vscode/) - syntax highlighting for `.mct` files
  - [book/](tools/book/) - generating the command book
    - [book.py](tools/book/book.py) - script for generating the book command based on the input from book.yaml
    - [book.yaml](tools/book/book.yaml) - the title, author, and pages of commands within the book
  - [encode/](tools/encode/) - Generate the command block encoding commands for multiblocks
    - [encode.py](tools/encode/encode.py) - This script takes the input from input.yaml and rewrites output.txt
    - [input.yaml](tools/encode/input.yaml) - The data for each multiblock and staircase, grouped by shared offsets and fill
    - [output.txt](tools/encode/output.txt) - Copy pastable commands from the output
    - [test_input.yaml](tools/encode/test_input.yaml) - used for testing without modifying input.yaml
    - [test_output.txt](tools/encode/test_output.txt) - used for testing without modifying output.txt
- [legacy/](legacy/) - kept for reference
  - [mazejs/](legacy/mazejs/) - The original proof of concept for the maze generation. It's an html website.
