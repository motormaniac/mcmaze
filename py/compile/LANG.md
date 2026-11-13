# Define the templating language

`compile.py` turns a `.mct` file into IR. `schem.py` turns the IR (or a `.mct` file directly) into a WorldEdit schematic. Sources go in `compile/in/`, IR goes to `compile/ir/` and schematics go to `compile/out/`.

    cd py
    uv run compile/compile.py compile/in/walls.mct
    -- writes compile/ir/walls.txt
    uv run compile/schem.py compile/in/walls.mct
    -- writes compile/out/walls.schem

One `.mct` file is one command chain, which becomes one schematic. Every command is a chain command block.

## General

Comments are defined using double dashes at the start of a line (leading whitespace is ok). Everything after them is ignored. Double dashes anywhere else are normal text.

    -- this is a comment
    say a--b;   -- this is NOT a comment, it's part of the command

Comment lines can go inside a multi-line command.

    execute
      -- only the pigs
      as @e[type=pig]
      run say hi;
    -- produces:
    execute as @e[type=pig] run say hi

Block comments start with exactly `--[` and end at the first `]--`, which can be anywhere. They don't nest. An unclosed `--[` is an error.

    --[
      This is a block comment.
      All text within here is ignored.
    ]--
    --[ one line ]-- say hi;

Code is separated by semicolons, and white space should not matter. Every command and global ends with `;`, including the last one in a body. Everything is case sensitive.

    kill @e;
    execute
      as @n
      run say hello;
    -- the above is equivalent to:
    execute as @n run say hello;

Semicolons and commas inside quotes, `[ ]` or `{ }` don't count, so NBT and strings never need escaping. `\"` and `\'` don't end a string. A string can't span a line break. A quote right after a letter or digit isn't a string, so `say don't;` works.

    data merge entity @n {UUID:[I;1,2,3,4]};
    say "wait; then (go)";

## Statements

Outside a function body, a file can only contain functions, globals, tables, comments and compiler comments. Inside a body, each statement is recognized by how it starts:

| Starts with | Statement |
|---|---|
| `--` / `--[` | comment |
| `#--` | compiler comment |
| `!` | command block modifier |
| `for $` | loop |
| `$name(` (no space) | function call |
| anything else | command, read until `;` |

`for`, `func` and `table` only count as whole words, so `function maze:build;` is a command.

## Variables

Variables start with `$` followed by letters, digits and `_`. The longest name always wins. Use `${name}` when text follows directly, and `$$` for a literal `$`. Variables are also replaced inside quotes. Using an undefined variable is an error.

    for $i in 0..1 (
      say Array${i}End costs $$5 "item $i";
    )
    -- produces:
    say Array0End costs $5 "item 0"
    say Array1End costs $5 "item 1"

Global variables are defined outside functions. Values are raw text, trimmed. Quotes are kept. A global can use other globals.

    $HELLO_WORLD = "hello world";
    $GREETING = $HELLO_WORLD from me;

    func $main () (
      say $GREETING;
    )
    -- produces:
    say "hello world" from me

## Tables
A table maps keys to values, like a dictionary. Tables are defined outside functions, in any order. Entries split on commas the same way as arguments. Each entry is `key: value`, split at the first `:`, so values like `minecraft:stone` work. Keys are letters, digits and `_`, or a negative integer. Values are raw text, trimmed, like a global's, and can use globals and other tables.

    table $blocks (
      0: minecraft:stone,
      1: $WOOL,
      north: "a, b"
    )

Look up a value with `$table[key]`. The key is templated first, so `$blocks[$i]` works. The `]` ends the lookup, so text can follow directly, and only the first `[...]` is a lookup.

    for $i in 0..1 (
      setblock ~ ~$i ~ $blocks[$i];
    )
    say $blocks[north]End;
    kill $TARGET[0][tag=x];
    -- produces (with $WOOL = minecraft:white_wool; and $TARGET[0] = @e):
    setblock ~ ~0 ~ minecraft:stone
    setblock ~ ~1 ~ minecraft:white_wool
    say "a, b"End
    kill @e[tag=x]

Rules:
- A `[` only starts a lookup after a table name. After any other variable it's plain text, so `$SEL[type=pig]` with `$SEL = @e;` gives `@e[type=pig]`.
- A table can't be used without a key: `$blocks` and `${blocks}` are errors. There's no braced form, since the `]` already ends the lookup.
- A missing key, a duplicate key, an empty table, and an entry without a `:` are errors.
- Lookups work anywhere a variable does: commands, arguments, list items, range bounds, compiler comments, globals and other table values.

## Functions
Functions are more like templates. When expanded, the argument values replace the references. Arguments and function names are defined using $.

    func $example_func ($arg1, $arg2) (
      kill $arg1;
      execute as $arg2 run say hello;
    )

Funcs are called inside a body using $syntax. Arguments split on commas outside quotes, brackets and parentheses, so selectors, NBT and strings work as-is. A trailing comma is allowed in arguments, parameters, loop lists and tables.

    $example_func(@e[type=pig,limit=1], bob);

    -- produces:
    kill @e[type=pig,limit=1]
    execute as bob run say hello

Rules:
- `func $main ()` is required, takes no arguments, and is the entry point. Only `$main` and what it calls produce output. Unused functions are fine.
- Functions must be declared outside a function body, in any order.
- Calling with the wrong number of arguments is an error.
- Recursion (direct or through other functions) is an error.
- A call can't be used inside a command: `say $f();` is an error.
- Scope is lexical. A body can only see its own parameters, its loop variables, globals and tables.
- No shadowing: a parameter or loop variable can't reuse the name of a global, a table, a parameter, or a loop variable it's nested in. Functions, globals and tables share names, so they can't match either.

        func $main () (
          for $i in 0..3 (
            $show();        -- error in $show: undefined variable $i
            $show_i($i);    -- ok
          )
        )

## Loops

For loops use similar templating. Loops can be nested and can contain calls.

    -- ranges are inclusive on both ends (different than python)
    for $i in 0..5 (
      data get storage test Array[$i];
    )

    -- produces:
    data get storage test Array[0]
    data get storage test Array[1]
    data get storage test Array[2]
    data get storage test Array[3]
    data get storage test Array[4]
    data get storage test Array[5]

Bounds can be negative or variables (they must be whole numbers). If the start is bigger, it counts down.

    for $i in $SIZE..-1 (
      say $i;
    )
    -- with $SIZE = 1; produces:
    say 1
    say 0
    say -1

Allow for for loops to iterate through an array of terms. Items split the same way as arguments.

    for $x in (cat, dog, @e[type=rabbit,limit=1]) (
      say $x;
    )

    -- produces:
    say cat
    say dog
    say @e[type=rabbit,limit=1]

## Command Block Modifiers

Every command is an unconditional, always active chain command block by default. A `!` line changes the command directly after it. It ends at the newline and can use `conditional`, `needs_redstone`, or both in any order. The IR always writes them as `!conditional, needs_redstone`. It can't go before a call or loop, so put it inside the body instead.

    execute if entity @e[tag=!fail];
    !conditional
    say placed;
    !conditional, needs_redstone
    say also placed;
    !conditional
    $talk(cat);   -- error: ! can't go before a call

## Compiler Comments
Compiler comments start with `#--`. They can go anywhere, are templated, and are kept in the IR. `schem.py` writes each one on a sign above the command below it. They show up in the IR in the same order relative to the commands. Top-level ones are ordered around `func $main`: the ones above it come before its commands, and the ones below come after.

    #-- start
    func $main () (
      say hi;
      #-- middle
      say bye;
    )
    #-- end
    -- produces:
    #-- start
    say hi
    #-- middle
    say bye
    #-- end

    func $main () (
      for $i in 0..1 (
        #-- This is iteration $i
        say $i;
      )
    )
    -- produces:
    #-- This is iteration 0
    say 0
    #-- This is iteration 1
    say 1

## Compiler IR
The compiler outputs IR with every template resolved. The format is defined in [IR](#ir-intermediate-representation) below.

    #-- This is a compiler comment
    func $talk ($x) (
      execute as $x
        run say "My name is $x";
    )

    func $main () (
      for $i in (cat, dog, bunny) (
        $talk($i);
      )
    )

    -- produces:
    #-- This is a compiler comment
    execute as cat run say "My name is cat"
    execute as dog run say "My name is dog"
    execute as bunny run say "My name is bunny"

## Errors
The compiler stops at the first error. Errors show the file, line and column, and errors during expansion show how it got there. An empty `$main` is an error. There are no warnings.

    walls.mct:4:16: undefined variable $nmae
        execute as $nmae run say hi;
                   ^
      in $talk($x = dog)   called at walls.mct:12
      in for $i = dog      at walls.mct:11
      in $main             at walls.mct:10

## Tests
`compile/tests/pass/` holds pairs like `loops.mct` and `loops.txt` (the expected IR). `compile/tests/fail/` holds pairs like `recursion_direct.mct` and `recursion_direct.err` (the expected first line of the error, plus an optional trace). Run them with `uv run pytest` from `py/`.

# IR (Intermediate Representation)

The IR is what `compile.py` writes to `compile/ir/<name>.txt` and what `schem.py` reads. It's one command chain, written as plain text with one item per line. It isn't meant to be written by hand, so it's whitespace sensitive.

## Lines
Every line is one of three kinds, decided by how it starts:

| Starts with | Line | Meaning |
|---|---|---|
| `#--` | compiler comment | free text, shown on a sign above the next command |
| `!` | modifier | changes the command on the next line |
| anything else | command | one chain command block |

    ir       = { line "\n" } ;
    line     = comment | modifier | command ;
    comment  = "#--" text ;
    modifier = "!conditional" | "!needs_redstone" | "!conditional, needs_redstone" ;
    command  = text that doesn't start with "#--" or "!" ;

## Commands
- Each command line is one chain command block. The first command is the start of the chain, and the rest follow in order.
- A command is unconditional and always active unless a modifier line comes right before it.
- Commands have every template resolved, no `;`, no leading or trailing spaces, and single spaces between words outside quotes. Text inside quotes is exactly as written.
- A literal `$` is just a `$` (it was written as `$$` in the `.mct` file).

## Modifiers
- Only the three forms above are valid, always in that order and spelling.
- A modifier line is always followed directly by a command line, and it only applies to that command.

## Guarantees
`compile.py` always writes IR that follows these rules, so `schem.py` can reject anything else as invalid IR:
- At least one command.
- No blank lines. The file uses `\n` line endings and ends with a newline.
- Compiler comments stay in the same order relative to the commands.

Example:

    #-- place the walls
    execute if entity @e[tag=!fail]
    !conditional
    place template maze:walls ~ ~ ~
    !conditional, needs_redstone
    say "placed walls"

| Line | Command block |
|---|---|
| `#-- place the walls` | none |
| `execute if entity @e[tag=!fail]` | chain, unconditional, always active |
| `place template maze:walls ~ ~ ~` | chain, conditional, always active |
| `say "placed walls"` | chain, conditional, needs redstone |