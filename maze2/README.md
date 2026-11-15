# maze2

Everything for the new maze generator. Run all commands from the repo root.

## How the files fit together
```
room sheet (Google Sheets) --> rooms/rooms.py --+
                                                +--> ir/*.irt --> tools/mct (schem.py) --> schem/*.schem --> paste into the world
src/*.mct --> tools/mct (compile.py) -----------+

manual_test/make_cases.py --> manual_test/test_rooms.csv --> rooms/rooms.py (instead of the sheet)
                                                        \--> sim/simulate.py
```

| Folder | What's in it |
|---|---|
| [src/](src/) | `.mct` sources. `maze2.mct` is the algorithm, `init.mct` adds the scoreboards, `constraint.mct` spawns constraint nodes and enables test categories, `visualize.mct` shows each node's encodings as wool, and `const.mct` holds shared constants for the others to import |
| [rooms/](rooms/) | `rooms.py` downloads the room sheet to `rooms.csv` (or reads any CSV), then writes `ir/lookups.irt` and `ir/place.irt` |
| [sim/](sim/) | Python model of the algorithm and an exact solver, for checking a room set before running it in game |
| [manual_test/](manual_test/) | `TESTS.md` is the in-game test plan. `make_cases.py` writes its rooms to `test_rooms.csv` |
| `ir/`, `schem/` | Generated IR and schematics (gitignored) |

## Common commands
```
uv run poe build                                   # download the sheet, then build every IR file and schematic
uv run poe mct-all                                 # rebuild without downloading the sheet
uv run poe rooms maze2/manual_test/test_rooms.csv  # lookups/place from the test rooms
uv run poe cases                                   # rewrite test_rooms.csv
uv run poe sim check maze2/manual_test/test_rooms.csv
```
