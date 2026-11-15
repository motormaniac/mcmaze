# maze2 in-game tests

Eight runs. All of them use the same rooms sheet (compile once) and the same 3 × 2 × 2 grid. Only the
interior constraints change: test 4 adds two, test 5 moves one of those by one cell, test 6 moves it
back, test 7 adds a third, and test 8 removes them all.

| # | Category | Layout | `.maxEdit` | Expected |
|---|---|---|---|---|
| 1 | `t_basic` | A | 0 | finishes in 12 gt |
| 2 | `t_slots` | A | 0 | finishes in 12 gt |
| 3 | `t_nofit` | A | 3 | error within ~5 gt |
| 4 | `t_domino` | B | 20 | finishes, usually in 1–3 s |
| 5 | `t_domino` | C | 20 | error after ~14 s |
| 6 | `t_tri` | B | 30 | error after ~20 s |
| 7 | `t_tri` | D | 30 | finishes, usually in 1–3 s |
| 8 | `t_tri` | A | 100 | finishes, usually in 2–20 s (rarely up to ~1 min) |

## How to read the maps

Each map is one horizontal layer, seen from above: **north is up, east is right**. Each letter is one
node position, and neighboring positions are 7 blocks apart. Position (x, y, z) is at
`start + (7x, 7y, 7z)` blocks, so x = 1 is 7 blocks east of the start node, and z = 1 is 7 blocks
south of it.

| Symbol | Meaning |
|---|---|
| `S` | start node: run init here. It's cell (0,0,0). Don't place anything. |
| `.` | an empty cell the algorithm fills. Don't place anything. |
| `C` | a constraint node you place: tag `constraint`, `target_<side>1 = 0` (`constraint`) on all six sides, `target_<side>2..6 = -1` |
| blank | nothing |

The grid is the 6 cells of layers y = 0 and y = 1. Layers y = -1 and y = 2 are the bottom and top
bounds.

## Rooms (compile once)

Put these 35 rows in the sheet (they're also in [test_rooms.csv](test_rooms.csv)). Every room has
weight 0. Structure names don't matter.

The walls use the `constraint` encoding, so rooms can sit against constraint nodes (which only accept
id 0). `constraint` is always id 0, and the other encodings are numbered from 1 in order of first
appearance. With only these rows, the ids and `visualize` wool are:

| id | encoding | wool |
|---|---|---|
| 0 | constraint (wall) | white |
| 1 | open | orange |
| 2 | hatch | magenta |
| 3 | join | light blue |
| 4 | door | yellow |
| 5 | end_side | lime |
| 6 | mid | pink |
| 7 | end_up | gray |
| 8 | end_down | light gray |

If the sheet has other rooms above these, ids 1–8 shift, but `constraint` stays 0, so the constraint
nodes don't change.

| Room Weight | Categories | Structure Name | North | East | South | West | Up | Down | Target North | Target East | Target South | Target West | Target Up | Target Down |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | t_basic | `test:basic_closed_bottom` | constraint | constraint | constraint | constraint | open | constraint | constraint | constraint | constraint | constraint | open | constraint |
| 0 | t_basic | `test:basic_deadend_bottom` | open | constraint | constraint | constraint | open | constraint | open | constraint | constraint | constraint | open | constraint |
| 0 | t_basic | `test:basic_corner_bottom` | open | open | constraint | constraint | open | constraint | open | open | constraint | constraint | open | constraint |
| 0 | t_basic, t_nofit | `test:basic_straight_bottom` | open | constraint | open | constraint | open | constraint | open | constraint | open | constraint | open | constraint |
| 0 | t_basic, t_nofit | `test:basic_tee_bottom` | open | open | open | constraint | open | constraint | open | open | open | constraint | open | constraint |
| 0 | t_basic, t_nofit | `test:basic_cross_bottom` | open | open | open | open | open | constraint | open | open | open | open | open | constraint |
| 0 | t_basic | `test:basic_closed_top` | constraint | constraint | constraint | constraint | constraint | open | constraint | constraint | constraint | constraint | constraint | open |
| 0 | t_basic | `test:basic_deadend_top` | open | constraint | constraint | constraint | constraint | open | open | constraint | constraint | constraint | constraint | open |
| 0 | t_basic | `test:basic_corner_top` | open | open | constraint | constraint | constraint | open | open | open | constraint | constraint | constraint | open |
| 0 | t_basic, t_nofit | `test:basic_straight_top` | open | constraint | open | constraint | constraint | open | open | constraint | open | constraint | constraint | open |
| 0 | t_basic, t_nofit | `test:basic_tee_top` | open | open | open | constraint | constraint | open | open | open | open | constraint | constraint | open |
| 0 | t_basic, t_nofit | `test:basic_cross_top` | open | open | open | open | constraint | open | open | open | open | open | constraint | open |
| 0 | t_slots | `test:slots_closed_bottom` | constraint | constraint | constraint | constraint | hatch | constraint | open, constraint, join | open, constraint, join | open, constraint, join | open, constraint, join | join, hatch, open | open, constraint, join |
| 0 | t_slots | `test:slots_deadend_bottom` | door | constraint | constraint | constraint | hatch | constraint | join, open, door | open, constraint, join | open, constraint, join | open, constraint, join | join, hatch, open | open, constraint, join |
| 0 | t_slots | `test:slots_corner_bottom` | door | door | constraint | constraint | hatch | constraint | join, open, door | join, open, door | open, constraint, join | open, constraint, join | join, hatch, open | open, constraint, join |
| 0 | t_slots | `test:slots_straight_bottom` | door | constraint | door | constraint | hatch | constraint | join, open, door | open, constraint, join | join, open, door | open, constraint, join | join, hatch, open | open, constraint, join |
| 0 | t_slots | `test:slots_tee_bottom` | door | door | door | constraint | hatch | constraint | join, open, door | join, open, door | join, open, door | open, constraint, join | join, hatch, open | open, constraint, join |
| 0 | t_slots | `test:slots_cross_bottom` | door | door | door | door | hatch | constraint | join, open, door | join, open, door | join, open, door | join, open, door | join, hatch, open | open, constraint, join |
| 0 | t_slots | `test:slots_closed_top` | constraint | constraint | constraint | constraint | constraint | hatch | open, constraint, join | open, constraint, join | open, constraint, join | open, constraint, join | open, constraint, join | join, hatch, open |
| 0 | t_slots | `test:slots_deadend_top` | door | constraint | constraint | constraint | constraint | hatch | join, open, door | open, constraint, join | open, constraint, join | open, constraint, join | open, constraint, join | join, hatch, open |
| 0 | t_slots | `test:slots_corner_top` | door | door | constraint | constraint | constraint | hatch | join, open, door | join, open, door | open, constraint, join | open, constraint, join | open, constraint, join | join, hatch, open |
| 0 | t_slots | `test:slots_straight_top` | door | constraint | door | constraint | constraint | hatch | join, open, door | open, constraint, join | join, open, door | open, constraint, join | open, constraint, join | join, hatch, open |
| 0 | t_slots | `test:slots_tee_top` | door | door | door | constraint | constraint | hatch | join, open, door | join, open, door | join, open, door | open, constraint, join | open, constraint, join | join, hatch, open |
| 0 | t_slots | `test:slots_cross_top` | door | door | door | door | constraint | hatch | join, open, door | join, open, door | join, open, door | join, open, door | open, constraint, join | join, hatch, open |
| 0 | t_domino | `test:domino_half` | join | constraint | constraint | constraint | constraint | constraint | join | constraint | constraint | constraint | constraint | constraint |
| 0 | t_domino | `test:domino_half_up` | constraint | constraint | constraint | constraint | join | constraint | constraint | constraint | constraint | constraint | join | constraint |
| 0 | t_domino | `test:domino_half_down` | constraint | constraint | constraint | constraint | constraint | join | constraint | constraint | constraint | constraint | constraint | join |
| 0 | t_tri | `test:tri_end_side` | end_side | constraint | constraint | constraint | constraint | constraint | mid | constraint | constraint | constraint | constraint | constraint |
| 0 | t_tri | `test:tri_end_up` | constraint | constraint | constraint | constraint | end_up | constraint | constraint | constraint | constraint | constraint | mid | constraint |
| 0 | t_tri | `test:tri_end_down` | constraint | constraint | constraint | constraint | constraint | end_down | constraint | constraint | constraint | constraint | constraint | mid |
| 0 | t_tri | `test:tri_mid_straight` | mid | constraint | mid | constraint | constraint | constraint | end_up, end_side, end_down | constraint | end_up, end_side, end_down | constraint | constraint | constraint |
| 0 | t_tri | `test:tri_mid_corner` | mid | mid | constraint | constraint | constraint | constraint | end_up, end_side, end_down | end_up, end_side, end_down | constraint | constraint | constraint | constraint |
| 0 | t_tri | `test:tri_mid_side_up` | mid | constraint | constraint | constraint | mid | constraint | end_up, end_side, end_down | constraint | constraint | constraint | end_up, end_side, end_down | constraint |
| 0 | t_tri | `test:tri_mid_side_down` | mid | constraint | constraint | constraint | constraint | mid | end_up, end_side, end_down | constraint | constraint | constraint | constraint | end_up, end_side, end_down |
| 0 | t_tri | `test:tri_mid_up_down` | constraint | constraint | constraint | constraint | mid | mid | constraint | constraint | constraint | constraint | end_up, end_side, end_down | end_up, end_side, end_down |

## Each run

1. Kill the old non-constraint graph nodes and place the constraints for the test's layout.
2. Enable only the test's category:
   ```
   scoreboard players set @e[type=item_display,name=lookup] enabled 0
   scoreboard players set @e[type=item_display,name=lookup,tag=cat_<category>] enabled 1
   ```
3. Set `.maxEdit`, run init at `S`, run the loop until it stops, then run `visualize`.

**A finished run passes when** every cell is filled, every face against a constraint is white, and
every pair of touching faces is an allowed pair. In tests 1–5 that means the same color. In tests 6–8
it means a pink (mid) face touching a lime, gray or light gray face, or white touching white.

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

## Tests 6–8: triominoes

These rooms are the first where matching faces have **different encodings**, and where a target list
has **more than one real match**. In tests 1–5, every face matched its own encoding (join to join,
door to door), so a filter that compared a face with the neighbor's *face* instead of its *target
list* would pass all of them. These tests catch that.

The rooms are two kinds of pieces:

- **Ends** have one connecting face. `end_side` (lime) is on the north face, `end_up` (gray) on the up
  face, `end_down` (light gray) on the down face. An end face accepts only `mid`.
- **Middles** have two `mid` faces (pink), in every pairing: straight, corner, side + up, side + down,
  up + down. A mid face accepts `end_up, end_side, end_down`, in that slot order.

Every other face is a white wall (`constraint`) that accepts only `constraint`. Ends can't join
ends, and middles can't join middles, so every finished piece is end, middle, end: **3 cells** in a straight line or an L, flat or
bent between the layers. Which slot of the mid list matches depends on the end's direction: an end below
the middle matches slot 1, beside it slot 2, above it slot 3.

**What you should see in a finished run:** the cells split into groups of 3. Each group has a pink cell
in the middle with two pink faces, each touching a lime, gray or light gray face. Gray faces always
point up and light gray faces always point down. No pink face touches another pink face, and no lime
or gray face touches anything but pink.

### Test 6: 10 cells

| Category | Layout | `.maxEdit` | Runs | Expected |
|---|---|---|---|---|
| `t_tri` | B (same as test 4) | 30 | 1 | error after ~400 gt (~20 s) |

**Why:** layout B has 10 free cells, and 10 isn't a multiple of 3, so the cells can't split into
triominoes. A finished run here is always wrong. If it finishes with lime touching lime or pink
touching pink, the filter is comparing faces with faces instead of
with target lists.

### Test 7: 9 cells

| Category | Layout | `.maxEdit` | Runs | Expected |
|---|---|---|---|---|
| `t_tri` | D | 30 | 3 | finishes, median 17 gt (~1 s), rarely up to ~190 gt |

**Why:** 9 cells can be split into 3 triominoes, but early random picks often leave a cell that can't
join any piece, so the algorithm has to undo rooms. In simulation, 5,000 runs all finished. Half
needed no edits at all, and the highest edit count was 18.

This one test fails under every filter or rotation bug the simulator tried: reading only slot 1 or
only the last slot (some runs), treating `-1` padding as a match, comparing face with face, reading
the neighbor's same-side targets, rotating targets the other way from faces, or swapping target up and
down.

### Layout D: three interior constraints (35 constraints)

Same as B, plus a constraint at **(1,1,0)** (7 east, 7 up).

```
y = 2: above the grid (top bound), 6 constraints, +14 blocks from start
        x=-1 x=0  x=1  x=2  x=3
  z=-1
  z=0        C    C    C
  z=1        C    C    C
  z=2

y = 1: grid layer 1, 12 constraints, +7 blocks from start
        x=-1 x=0  x=1  x=2  x=3
  z=-1       C    C    C
  z=0   C    .    C    .    C
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

### Test 8: stress, 12 cells

| Category | Layout | `.maxEdit` | Runs | Expected |
|---|---|---|---|---|
| `t_tri` | A (same as test 1) | 100 | 2 | finishes, median 86 gt (~4 s), p95 ~350 gt (~18 s) |

**Why:** the full grid can be split into 4 triominoes, but it is much harder than layout D. Runs often
build pieces that block each other and have to undo many rooms. This test checks that the algorithm
gets out of deep dead ends instead of just shallow ones. In simulation, 5,000 runs all finished. The
median peak edit count was 5, but 1 in 20 runs passed 23, and the highest was 74 (1,131 gt, ~57 s).
That's why `.maxEdit` is 100. An error here at a much lower edit count than that is suspicious, but
one error isn't proof of a bug: run it again.

---

## Not covered

- Room weights: all 0, so picks are uniform.
- More than 3 targets: 3 stands in for any number.
- The algorithm only ever checks one half of a match (the new room against the neighbor's targets).
  Every test room set is reciprocal, so a bug that checked the other half instead can't be seen.
- Constraints that split the grid into separate regions: the far side is never reached (a known issue).
