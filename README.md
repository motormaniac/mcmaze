# Codebase for the Minecraft Maze Generate Map
## File Layout
- [book/](book/) - generating the command book
  - [book.py](book/book.py) - script for generating the book command based on the input from book_command.txt
  - [book_command.txt](book/book_command.txt) - a formatted list of all commands within the book
- [commands/](commands/) - txt files containing all commands used within the world
  - [game.txt](commands/game.txt) - game loop logic
  - [items.txt](commands/items.txt) - item logic
  - [maze.txt](commands/maze.txt) - maze generation
  - [tutorial.txt](commands/tutorial.txt) - (unused) the commands for the tutorial
- [encode/](encode/) - Generate the command block encoding commands for multiblocks
  - [encode.py](encode/encode.py) - This script takes the input from input.txt and rewrites output.txt
  - [input.txt](encode/input.txt) - A formatted list of the data for each multiblock
  - [output.txt](encode/output.txt) - Copy pastable commands from the output
  - [test_input.txt](encode/test_input.txt) - used for testing without modifying input.txt
  - [test_output.txt](encode/test_output.txt) - used for testing without modifying output.txt
- [mazejs/](mazejs/) - The original proof of concept for the maze generation. It's an html website.
