# Codebase for the Minecraft Maze Generate Map
## Running the Python scripts
The Python scripts live in [py/](py/), which is a [uv](https://docs.astral.sh/uv/) project. Run them with `uv run` from inside `py/`:
```
cd py
uv run book/book.py
uv run encode/encode.py
```
The first `uv run` sets up the Python environment automatically, so there's nothing to install beforehand besides uv itself.

## File Layout
- [commands/](commands/) - txt files containing all commands used within the world
  - [game.txt](commands/game.txt) - game loop logic
  - [items.txt](commands/items.txt) - item logic
  - [maze.txt](commands/maze.txt) - maze generation
  - [tutorial.txt](commands/tutorial.txt) - (unused) the commands for the tutorial
- [mazejs/](mazejs/) - The original proof of concept for the maze generation. It's an html website.
- [py/](py/) - Python scripts for generating commands
  - [book/](py/book/) - generating the command book
    - [book.py](py/book/book.py) - script for generating the book command based on the input from book.yaml
    - [book.yaml](py/book/book.yaml) - the title, author, and pages of commands within the book
  - [encode/](py/encode/) - Generate the command block encoding commands for multiblocks
    - [encode.py](py/encode/encode.py) - This script takes the input from input.yaml and rewrites output.txt
    - [input.yaml](py/encode/input.yaml) - The data for each multiblock and staircase, grouped by shared offsets and fill
    - [output.txt](py/encode/output.txt) - Copy pastable commands from the output
    - [test_input.yaml](py/encode/test_input.yaml) - used for testing without modifying input.yaml
    - [test_output.txt](py/encode/test_output.txt) - used for testing without modifying output.txt
