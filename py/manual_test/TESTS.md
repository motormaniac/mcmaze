# maze2 in-game tests

Five runs. All of them use the same rooms sheet (compile once) and the same 3 × 2 × 2 grid. Only the
interior constraints change: test 4 adds two, and test 5 moves one of those by one cell.

## How to read the maps

Each map is one horizontal layer, seen from above: **north is up, east is right**. Each letter is one
node position, and neighboring positions are 7 blocks apart. Position (x, y, z) is at
`start + (7x, 7y, 7z)` blocks, so x = 1 is 7 blocks east of the start node, and z = 1 is 7 blocks
south of it.

| Symbol | Meaning |
|---|---|
| `S` | start node: run init here. It's cell (0,0,0). Don't place anything. |
| `.` | an empty cell the algorithm fills. Don't place anything. |
| `C` | a constraint node you place: tag `constraint`, `target_<side>1 = 0` (wall) on all six sides, `target_<side>2..6 = -1` |
| blank | nothing |

The grid is the 6 cells of layers y = 0 and y = 1. Layers y = -1 and y = 2 are the bottom and top
bounds.

## Rooms (compile once)

Put these 27 rows in the sheet (they're also in [test_rooms.csv](test_rooms.csv)). Every room has
weight 0. Structure names don't matter.

Encodings get numbered in order of first appearance. With only these rows, the ids and `visualize`
wool are:

| id | encoding | wool |
|---|---|---|
| 0 | wall | white |
| 1 | open | orange |
| 2 | hatch | magenta |
| 3 | join | light blue |
| 4 | door | yellow |

If the sheet has other rooms above these, the ids shift. Constraints must target whatever id `wall`
gets.

| Room Weight | Categories | Structure Name | North | East | South | West | Up | Down | Target North | Target East | Target South | Target West | Target Up | Target Down |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | t_basic | `test:basic_closed_bottom` | wall | wall | wall | wall | open | wall | wall | wall | wall | wall | open | wall |
| 0 | t_basic | `test:basic_deadend_bottom` | open | wall | wall | wall | open | wall | open | wall | wall | wall | open | wall |
| 0 | t_basic | `test:basic_corner_bottom` | open | open | wall | wall | open | wall | open | open | wall | wall | open | wall |
| 0 | t_basic, t_nofit | `test:basic_straight_bottom` | open | wall | open | wall | open | wall | open | wall | open | wall | open | wall |
| 0 | t_basic, t_nofit | `test:basic_tee_bottom` | open | open | open | wall | open | wall | open | open | open | wall | open | wall |
| 0 | t_basic, t_nofit | `test:basic_cross_bottom` | open | open | open | open | open | wall | open | open | open | open | open | wall |
| 0 | t_basic | `test:basic_closed_top` | wall | wall | wall | wall | wall | open | wall | wall | wall | wall | wall | open |
| 0 | t_basic | `test:basic_deadend_top` | open | wall | wall | wall | wall | open | open | wall | wall | wall | wall | open |
| 0 | t_basic | `test:basic_corner_top` | open | open | wall | wall | wall | open | open | open | wall | wall | wall | open |
| 0 | t_basic, t_nofit | `test:basic_straight_top` | open | wall | open | wall | wall | open | open | wall | open | wall | wall | open |
| 0 | t_basic, t_nofit | `test:basic_tee_top` | open | open | open | wall | wall | open | open | open | open | wall | wall | open |
| 0 | t_basic, t_nofit | `test:basic_cross_top` | open | open | open | open | wall | open | open | open | open | open | wall | open |
| 0 | t_slots | `test:slots_closed_bottom` | wall | wall | wall | wall | hatch | wall | open, wall, join | open, wall, join | open, wall, join | open, wall, join | join, hatch, open | open, wall, join |
| 0 | t_slots | `test:slots_deadend_bottom` | door | wall | wall | wall | hatch | wall | join, open, door | open, wall, join | open, wall, join | open, wall, join | join, hatch, open | open, wall, join |
| 0 | t_slots | `test:slots_corner_bottom` | door | door | wall | wall | hatch | wall | join, open, door | join, open, door | open, wall, join | open, wall, join | join, hatch, open | open, wall, join |
| 0 | t_slots | `test:slots_straight_bottom` | door | wall | door | wall | hatch | wall | join, open, door | open, wall, join | join, open, door | open, wall, join | join, hatch, open | open, wall, join |
| 0 | t_slots | `test:slots_tee_bottom` | door | door | door | wall | hatch | wall | join, open, door | join, open, door | join, open, door | open, wall, join | join, hatch, open | open, wall, join |
| 0 | t_slots | `test:slots_cross_bottom` | door | door | door | door | hatch | wall | join, open, door | join, open, door | join, open, door | join, open, door | join, hatch, open | open, wall, join |
| 0 | t_slots | `test:slots_closed_top` | wall | wall | wall | wall | wall | hatch | open, wall, join | open, wall, join | open, wall, join | open, wall, join | open, wall, join | join, hatch, open |
| 0 | t_slots | `test:slots_deadend_top` | door | wall | wall | wall | wall | hatch | join, open, door | open, wall, join | open, wall, join | open, wall, join | open, wall, join | join, hatch, open |
| 0 | t_slots | `test:slots_corner_top` | door | door | wall | wall | wall | hatch | join, open, door | join, open, door | open, wall, join | open, wall, join | open, wall, join | join, hatch, open |
| 0 | t_slots | `test:slots_straight_top` | door | wall | door | wall | wall | hatch | join, open, door | open, wall, join | join, open, door | open, wall, join | open, wall, join | join, hatch, open |
| 0 | t_slots | `test:slots_tee_top` | door | door | door | wall | wall | hatch | join, open, door | join, open, door | join, open, door | open, wall, join | open, wall, join | join, hatch, open |
| 0 | t_slots | `test:slots_cross_top` | door | door | door | door | wall | hatch | join, open, door | join, open, door | join, open, door | join, open, door | open, wall, join | join, hatch, open |
| 0 | t_domino | `test:domino_half` | join | wall | wall | wall | wall | wall | join | wall | wall | wall | wall | wall |
| 0 | t_domino | `test:domino_half_up` | wall | wall | wall | wall | join | wall | wall | wall | wall | wall | join | wall |
| 0 | t_domino | `test:domino_half_down` | wall | wall | wall | wall | wall | join | wall | wall | wall | wall | wall | join |

## Each run

1. Kill the old non-constraint graph nodes and place the constraints for the test's layout.
2. Enable only the test's category:
   ```
   scoreboard players set @e[type=item_display,name=lookup] enabled 0
   scoreboard players set @e[type=item_display,name=lookup,tag=cat_<category>] enabled 1
   ```
3. Set `.maxEdit`, run init at `S`, run the loop until it stops, then run `visualize`.

**A finished run passes when** every cell is filled, every pair of touching faces is the same color,
and every face against a constraint is white.

---

## Test 1: basic

| Category | Layout | `.maxEdit` | Runs | Expected |
|---|---|---|---|---|
| `t_basic` | A | 0 | 2 | finishes in 12 gt |

**What you should see:** 12 rooms with only white (wall) and orange (open) faces. Orange touches orange,
and white touches white. The bottom layer's down faces are white, and its up faces are orange. The top
layer is the reverse.

**Why:** these rooms cover every wall/open arrangement, so whatever the filled neighbors need, some room
fits. A correct run never has to edit, which is why `.maxEdit` is 0 and any edit is an error. It fails
if a side checks the wrong neighbor or the wrong target, a rotation is wrong, empty neighbors aren't
skipped, the bounds aren't checked, or a direction isn't expanded.

### Layout A: no interior constraints (32 constraints)

```
y = 2: above the grid (top bound), 6 constraints, +14 blocks from start
        x=-1 x=0  x=1  x=2  x=3  
  z=-1
  z=0        C    C    C
  z=1        C    C    C
  z=2

y = 1: grid layer 1, 10 constraints, +7 blocks from start
        x=-1 x=0  x=1  x=2  x=3  
  z=-1       C    C    C
  z=0   C    .    .    .    C
  z=1   C    .    .    .    C
  z=2        C    C    C

y = 0: grid layer 0, 10 constraints, +0 blocks from start
        x=-1 x=0  x=1  x=2  x=3  
  z=-1       C    C    C
  z=0   C    S    .    .    C
  z=1   C    .    .    .    C
  z=2        C    C    C

y = -1: below the grid (bottom bound), 6 constraints, -7 blocks from start
        x=-1 x=0  x=1  x=2  x=3  
  z=-1
  z=0        C    C    C
  z=1        C    C    C
  z=2
```

---

## Test 2: three targets

| Category | Layout | `.maxEdit` | Runs | Expected |
|---|---|---|---|---|
| `t_slots` | A (same as test 1) | 0 | 2 | finishes in 12 gt |

**What you should see:** the same shapes as test 1, with yellow (door) and white faces sideways and
magenta (hatch) between the layers. Yellow touches yellow, white touches white, magenta touches magenta.

**Why:** every target list has 3 entries, and the real match is never first. Doors match in slot 3,
walls and hatches in slot 2. The other entries are encodings no room in this test has. If test 1 passes
and this errors, slot 2 or 3 isn't read.

---

## Test 3: nothing fits the corner

| Category | Layout | `.maxEdit` | Runs | Expected |
|---|---|---|---|---|
| `t_nofit` | A (same as test 1) | 3 | 1 | error within ~5 gt, nothing placed |

**Run this right after tests 1 and 2** without resetting the lookups.

**Why:** this category is only the test 1 rooms that never have two walls side by side (straight, tee,
cross). A corner cell has bounds on two sides that meet, so nothing fits it, and the start cell is a
corner. The start cell takes the "fits nothing" branch until it passes `.maxEdit`.
If a room gets placed, either constraints aren't treated as strong, or a disabled lookup was picked.
The test 1 and 2 lookups still have leftover `filter` scores, which is why the order matters.

---

## Test 4: dominoes

| Category | Layout | `.maxEdit` | Runs | Expected |
|---|---|---|---|---|
| `t_domino` | B | 20 | 3 | finishes, usually in 1–3 s (rarely up to ~10 s) |

**What you should see:** 10 rooms. Each has exactly one light blue (join) face, touching another light
blue face, and white everywhere else. The cells pair up like dominoes.

**Why:** a valid fill has to pair up every cell, and early random choices often make that impossible,
so most runs have to undo rooms. This tests the "fits strong only" branch: raising the edit count,
pushing weaker neighbors back into the queue, and the `i = -1` push guard. In simulation, 5,000 runs
all finished, and the highest edit count was 14.

### Layout B: two interior constraints (34 constraints)

Same as A, plus a constraint at **(0,0,1)** (7 blocks south of `S`) and one at **(2,1,1)** (14 east,
7 up, 7 south).

```
y = 2: above the grid (top bound), 6 constraints, +14 blocks from start
        x=-1 x=0  x=1  x=2  x=3  
  z=-1
  z=0        C    C    C
  z=1        C    C    C
  z=2

y = 1: grid layer 1, 11 constraints, +7 blocks from start
        x=-1 x=0  x=1  x=2  x=3  
  z=-1       C    C    C
  z=0   C    .    .    .    C
  z=1   C    .    .    C    C
  z=2        C    C    C

y = 0: grid layer 0, 11 constraints, +0 blocks from start
        x=-1 x=0  x=1  x=2  x=3  
  z=-1       C    C    C
  z=0   C    S    .    .    C
  z=1   C    C    .    .    C
  z=2        C    C    C

y = -1: below the grid (bottom bound), 6 constraints, -7 blocks from start
        x=-1 x=0  x=1  x=2  x=3  
  z=-1
  z=0        C    C    C
  z=1        C    C    C
  z=2
```

---

## Test 5: dominoes that can't pair up

| Category | Layout | `.maxEdit` | Runs | Expected |
|---|---|---|---|---|
| `t_domino` | C | 20 | 1 | error after ~280 gt (~14 s) |

**Why:** color the cells like a checkerboard. Every domino covers one cell of each color. In layout C,
both blocked cells are the same color, so the free cells can't all pair up, even though every cell
still looks fine on its own. The run keeps undoing rooms until it passes `.maxEdit`. A finished run
here is always wrong.

### Layout C: move one constraint (34 constraints)

Same as B, but the constraint at (2,1,1) moves one cell north to **(2,1,0)** (14 east, 7 up).

```
y = 2: above the grid (top bound), 6 constraints, +14 blocks from start
        x=-1 x=0  x=1  x=2  x=3  
  z=-1
  z=0        C    C    C
  z=1        C    C    C
  z=2

y = 1: grid layer 1, 11 constraints, +7 blocks from start
        x=-1 x=0  x=1  x=2  x=3  
  z=-1       C    C    C
  z=0   C    .    .    C    C
  z=1   C    .    .    .    C
  z=2        C    C    C

y = 0: grid layer 0, 11 constraints, +0 blocks from start
        x=-1 x=0  x=1  x=2  x=3  
  z=-1       C    C    C
  z=0   C    S    .    .    C
  z=1   C    C    .    .    C
  z=2        C    C    C

y = -1: below the grid (bottom bound), 6 constraints, -7 blocks from start
        x=-1 x=0  x=1  x=2  x=3  
  z=-1
  z=0        C    C    C
  z=1        C    C    C
  z=2
```

---

## Not covered

- Room weights: all 0, so picks are uniform.
- More than 3 targets: 3 stands in for any number.
- Constraints that split the grid into separate regions: the far side is never reached (a known issue).
