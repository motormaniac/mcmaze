# Define the templating language

## General

Comments are defined using double dashes.

    -- this is a comment

Block comments are defined with --[ ]--

    --[
      This is a block comment.
      All text within here is ignored.
    ]--

Code is separated by semicolons, and white space should not matter. By the way, assume that everything is case sensitive (I know which stuff is or isn't, but I don't expect the parser to know.)

    kill @e;
    execute
      as @n
      run say hello;
    -- the above is equivalent to:
    execute as @n run say hello;

Global variables\
Template variables can be defined the same way most languages define them ex: variable1, camelCase, snake_case

    $HELLO_WORLD = "hello world"

    func $main () (
      say $HELLO_WORLD
    )

## Functions and Loops
Functions are more like templates. When parsed, the argument value definitions replace the references. Arguments and function names are defined using $.

    func $example_func ($arg1, $arg2) (
      kill $arg1;
      execute as $arg2 run say hello;
    )

Funcs are called using $syntax

    $example_func(1, bob)

    -- produces:
    kill 1;
    execute as bob run say hello;

Functions must always be declared outside a function body

## Loops

For loops use similar templating.

     -- ranges are inclusive on both ends (different than python)
    for $i in 0..5 (
      data get storage test Array[$i];
    )

    -- produces:
    data get storage test Array[0];
    data get storage test Array[1];
    data get storage test Array[2];
    data get storage test Array[3];
    data get storage test Array[4];
    data get storage test Array[5];

Allow for for loops to iterate through an array of terms:

    for $x in (cat, dog, rabbit) (
      say $x;
    )

    -- produces:
    say cat;
    say dog;
    say rabbit;

## Compiler Flags

    #COMPILER_FLAG

    func $func1 () (

    )
    #-- This is a compiler comment, so this comment will persist in the IR.

## Compiler IR
- The compiler should output a format that resolves all templates.
- The form should only contain commands and compiler flags
- each command line / compiler flag is separated by newlines (semicolons are removed)

Example:

    #BREAK
    #-- This is a compiler comment
    func $talk ($x) (
      execute as $x
        run say "My name is $x"
    )

    func $main () (
      for $i in (cat, dog, bunny) (
        $talk($i);
      )
    )

    -- produces:
    #BREAK
    #-- This is a compiler comment
    execute as cat run say "My name is cat"
    execute as dog run say "My name is dog"
    execute as bunny run say "My name is bunny"