"""Compiles a .mct template file into IR, one command per line. See LANG.md.

  cd py
  uv run compile/compile.py compile/in/walls.mct    -- writes compile/ir/walls.txt

The compiler runs in four stages:
  1. mask_comments: blank out comments (keeping every character's position)
  2. Parser: turn the text into dataclasses (functions, globals, loops, calls, commands)
  3. Compiler: check names, then expand everything starting from $main
  4. collapse: tidy each finished command's whitespace
"""

import re
import sys
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path

MODIFIERS = ("conditional", "needs_redstone") # also the order they're written in the IR
IR_DIR = Path(__file__).with_name("ir")

NAME = r"[A-Za-z0-9_]+"
GLOBAL_START = re.compile(rf"\$({NAME})[ \t]*=")
CALL_START = re.compile(rf"\$({NAME})\(")
LOOP_START = re.compile(r"for\s+\$")
RANGE_BOUND = re.compile(rf"-?\d+|\${NAME}")
INTEGER = re.compile(r"-?\d+")
CLOSERS = {"[": "]", "{": "}", "(": ")"}


class CompileError(Exception):
  """Any error in a .mct file. The message is ready to print."""


def is_name_char(c: str) -> bool:
  return c.isascii() and (c.isalnum() or c == "_")

def is_quote_start(text: str, i: int) -> bool:
  """A quote only opens a string when it isn't part of a word, so don't and it's stay plain text."""
  return text[i] in "\"'" and (i == 0 or not is_name_char(text[i - 1]))

def string_end(text: str, i: int) -> int | None:
  """Index just after the string that starts at i, or None if it never closes on this line."""
  quote = text[i]
  j = i + 1
  while j < len(text) and text[j] != "\n":
    if text[j] == "\\":
      j += 2
      continue
    if text[j] == quote:
      return j + 1
    j += 1
  return None

def collapse(text: str) -> str:
  """Trims the text and turns each run of whitespace outside quotes into one space."""
  out: list[str] = []
  pending_space = False
  i = 0
  while i < len(text):
    if text[i].isspace():
      pending_space = True
      i += 1
      continue
    if pending_space and out:
      out.append(" ")
    pending_space = False
    end = string_end(text, i) if is_quote_start(text, i) else None
    if end is not None:
      out.append(text[i:end])
      i = end
    else:
      out.append(text[i])
      i += 1
  return "".join(out)

def plural(count: int, word: str) -> str:
  return f"{count} {word}" if count == 1 else f"{count} {word}s"


class Source:
  """The original text of a file, used to turn offsets into line:column and to show snippets."""

  def __init__(self, text: str, filename: str) -> None:
    self.text = text
    self.filename = filename
    self.lines = text.split("\n")
    self.line_starts = [0] + [i + 1 for i, c in enumerate(text) if c == "\n"]

  def line_col(self, offset: int) -> tuple[int, int]:
    line = bisect_right(self.line_starts, offset) - 1
    return line + 1, offset - self.line_starts[line] + 1

  def where(self, offset: int) -> str:
    return f"{self.filename}:{self.line_col(offset)[0]}"

  def error(self, message: str, offset: int | None = None, trace: list[str] | None = None) -> CompileError:
    if offset is None:
      text = f"{self.filename}: {message}"
    else:
      line, column = self.line_col(offset)
      text = f"{self.filename}:{line}:{column}: {message}\n    {self.lines[line - 1]}\n    {' ' * (column - 1)}^"
    if trace:
      text += "\n" + "\n".join(trace)
    return CompileError(text)


def mask_comments(src: Source) -> str:
  """Replaces comments with spaces. Newlines are kept, so every offset still matches the source."""
  text = src.text
  chars = list(text)

  def blank(start: int, end: int) -> None:
    for k in range(start, end):
      if chars[k] != "\n":
        chars[k] = " "

  pos = 0
  while pos < len(text):
    line_end = text.find("\n", pos)
    if line_end == -1:
      line_end = len(text)
    first = pos
    while first < line_end and text[first] in " \t":
      first += 1
    if text.startswith("--[", first):
      close = text.find("]--", first + 3)
      if close == -1:
        raise src.error("unclosed block comment", first)
      blank(first, close + 3)
      # the rest of the line after ]-- is normal code
      next_line = text.find("\n", close)
      pos = len(text) if next_line == -1 else next_line + 1
      continue
    if text.startswith("--", first):
      blank(first, line_end)
    pos = line_end + 1
  return "".join(chars)


# ---------- Parsed file ----------

@dataclass
class Value:
  """A piece of raw text (an argument, list item or global value) and where it starts."""
  text: str
  offset: int

@dataclass
class Command:
  text: str
  offset: int
  modifiers: list[str] = field(default_factory=list[str])

@dataclass
class CompilerComment:
  text: str
  """everything after #-- on its line"""
  offset: int

@dataclass
class Call:
  name: str
  offset: int
  args: list[Value]

@dataclass
class Bound:
  text: str
  """an integer like -3, or a variable like $n"""
  offset: int

@dataclass
class For:
  var: str
  var_offset: int
  for_offset: int
  range: tuple[Bound, Bound] | None
  items: list[Value] | None
  body: list[Statement]

type Statement = Command | CompilerComment | Call | For

@dataclass
class Func:
  name: str
  offset: int
  params: list[str]
  param_offsets: list[int]
  body: list[Statement]

@dataclass
class Global:
  name: str
  offset: int
  value: Value

type TopLevel = Func | Global | CompilerComment


class Parser:
  def __init__(self, src: Source, text: str) -> None:
    self.src = src
    self.text = text # comments already masked
    self.pos = 0

  def error(self, message: str, offset: int) -> CompileError:
    return self.src.error(message, offset)

  def char(self) -> str:
    return self.text[self.pos] if self.pos < len(self.text) else ""

  def skip_whitespace(self) -> None:
    while self.pos < len(self.text) and self.text[self.pos].isspace():
      self.pos += 1

  def at_word(self, word: str) -> bool:
    end = self.pos + len(word)
    return self.text.startswith(word, self.pos) and end < len(self.text) and self.text[end].isspace()

  def expect(self, char: str, message: str) -> int:
    self.skip_whitespace()
    if self.char() != char:
      raise self.error(message, self.pos)
    self.pos += 1
    return self.pos - 1

  def read_name(self, message: str) -> tuple[str, int]:
    """Reads $name and returns (name, offset of the $)."""
    match = re.compile(rf"\$({NAME})").match(self.text, self.pos)
    if match is None:
      raise self.error(message, self.pos)
    self.pos = match.end()
    return match[1], match.start()

  def line_ends_early(self, start: int) -> bool:
    """True when the line at start can't be part of an unfinished command: a lone ) or a func."""
    end = self.text.find("\n", start)
    line = self.text[start:] if end == -1 else self.text[start:end]
    return line.strip() == ")" or re.match(r"\s*func\s", line + " ") is not None

  def scan(self, stops: str, never_ended: str, never_ended_offset: int, track_parens: bool, check_lines: bool) -> tuple[int, int]:
    """
    Scans raw text until a stop character that isn't inside quotes or brackets.
    Returns (start, end) of the text and leaves pos on the stop character.
    """
    text = self.text
    openers = "[{(" if track_parens else "[{"
    closers = "]})" if track_parens else "]}"
    stack: list[tuple[str, int]] = []
    start = i = self.pos

    def not_ended() -> CompileError:
      if stack:
        bracket, offset = stack[-1]
        return self.error(f"unclosed {bracket}", offset)
      return self.error(never_ended, never_ended_offset)

    while True:
      if i >= len(text):
        raise not_ended()
      c = text[i]
      if is_quote_start(text, i):
        end = string_end(text, i)
        if end is None:
          raise self.error("unterminated string", i)
        i = end
        continue
      if text.startswith("$$", i):
        i += 2
        continue
      if text.startswith("${", i):
        match = re.compile(rf"\$\{{{NAME}\}}").match(text, i)
        if match is None:
          raise self.error("unclosed ${", i)
        i = match.end()
        continue
      if c in openers:
        stack.append((c, i))
      elif c in closers:
        if not stack:
          if c in stops:
            self.pos = i
            return start, i
          raise self.error(f"unmatched {c}", i)
        expected = CLOSERS[stack[-1][0]]
        if c != expected:
          raise self.error(f"expected {expected} but found {c}", i)
        stack.pop()
      elif c in stops and not stack:
        self.pos = i
        return start, i
      elif c == "\n" and check_lines and self.line_ends_early(i + 1):
        raise not_ended()
      i += 1

  def values(self, open_offset: int, never_ended: str) -> list[Value]:
    """Reads comma separated values after an opening ( up to its closing )."""
    self.skip_whitespace()
    if self.char() == ")":
      self.pos += 1
      return []
    values: list[Value] = []
    while True:
      start, end = self.scan(",)", never_ended, open_offset, track_parens=True, check_lines=False)
      values.append(Value(self.text[start:end], start))
      self.pos = end + 1
      if self.text[end] == ")":
        return values

  def parse_file(self) -> list[TopLevel]:
    items: list[TopLevel] = []
    while True:
      self.skip_whitespace()
      if self.pos >= len(self.text):
        return items
      if self.text.startswith("#--", self.pos):
        items.append(self.compiler_comment())
      elif self.at_word("func"):
        items.append(self.function())
      elif GLOBAL_START.match(self.text, self.pos):
        items.append(self.global_variable())
      elif self.char() == "!":
        raise self.error("modifiers must be inside a function body", self.pos)
      else:
        raise self.error("commands must be inside a function body", self.pos)

  def compiler_comment(self) -> CompilerComment:
    start = self.pos + 3
    end = self.text.find("\n", start)
    end = len(self.text) if end == -1 else end
    self.pos = end
    return CompilerComment(self.text[start:end], start)

  def global_variable(self) -> Global:
    offset = self.pos
    name, _ = self.read_name("expected a global like $NAME")
    self.pos = self.text.index("=", self.pos) + 1
    start, end = self.scan(";", f"global ${name} never ended, expected ;", offset, track_parens=False, check_lines=True)
    self.pos = end + 1
    return Global(name, offset, Value(self.text[start:end], start))

  def function(self) -> Func:
    self.pos += len("func")
    self.skip_whitespace()
    name, offset = self.read_name("expected a function name like $name after func")
    self.expect("(", "expected ( to start the parameter list")
    params: list[str] = []
    param_offsets: list[int] = []
    self.skip_whitespace()
    if self.char() == ")":
      self.pos += 1
    else:
      while True:
        self.skip_whitespace()
        param, param_offset = self.read_name("expected a parameter like $name")
        if param in params:
          raise self.error(f"duplicate parameter ${param}", param_offset)
        params.append(param)
        param_offsets.append(param_offset)
        self.skip_whitespace()
        if self.char() == ",":
          self.pos += 1
        elif self.char() == ")":
          self.pos += 1
          break
        else:
          raise self.error("expected , or ) in the parameter list", self.pos)
    open_offset = self.expect("(", "expected ( to start the function body")
    return Func(name, offset, params, param_offsets, self.body(open_offset))

  def body(self, open_offset: int) -> list[Statement]:
    statements: list[Statement] = []
    while True:
      self.skip_whitespace()
      if self.pos >= len(self.text):
        raise self.error("body never closed, expected )", open_offset)
      if self.char() == ")":
        self.pos += 1
        return statements
      statements.append(self.statement())

  def statement(self) -> Statement:
    if self.text.startswith("#--", self.pos):
      return self.compiler_comment()
    if self.char() == "!":
      return self.modified_command()
    if self.at_word("func"):
      raise self.error("functions must be declared outside a function body", self.pos)
    if LOOP_START.match(self.text, self.pos):
      return self.loop()
    if CALL_START.match(self.text, self.pos):
      return self.call()
    return self.command()

  def modified_command(self) -> Command:
    bang = self.pos
    end = self.text.find("\n", bang)
    end = len(self.text) if end == -1 else end
    modifiers: list[str] = []
    offset = bang + 1
    for part in self.text[bang + 1:end].split(","):
      name = part.strip()
      name_offset = offset + len(part) - len(part.lstrip())
      if not name:
        raise self.error("expected conditional or needs_redstone after !", name_offset)
      if name not in MODIFIERS:
        raise self.error(f"unknown modifier {name}", name_offset)
      if name in modifiers:
        raise self.error(f"duplicate modifier {name}", name_offset)
      modifiers.append(name)
      offset += len(part) + 1
    self.pos = end
    self.skip_whitespace()
    if self.pos >= len(self.text) or self.char() in ")!":
      raise self.error("! must come directly before a command", bang)
    statement = self.statement()
    if not isinstance(statement, Command):
      raise self.error("! must come directly before a command", bang)
    statement.modifiers = modifiers
    return statement

  def loop(self) -> For:
    for_offset = self.pos
    self.pos += len("for")
    self.skip_whitespace()
    var, var_offset = self.read_name("expected a loop variable like $i after for")
    self.skip_whitespace()
    if not (self.text.startswith("in", self.pos) and self.text[self.pos + 2:self.pos + 3] in (" ", "\t", "\n", "(")):
      raise self.error(f"expected in after ${var}", self.pos)
    self.pos += len("in")
    self.skip_whitespace()
    loop_range: tuple[Bound, Bound] | None = None
    items: list[Value] | None = None
    if self.char() == "(":
      open_offset = self.pos
      self.pos += 1
      items = self.values(open_offset, "list never closed, expected )")
    else:
      low = self.bound()
      self.skip_whitespace()
      if not self.text.startswith("..", self.pos):
        raise self.error("expected .. in the range", self.pos)
      self.pos += 2
      self.skip_whitespace()
      loop_range = (low, self.bound())
    open_offset = self.expect("(", "expected ( to start the loop body")
    return For(var, var_offset, for_offset, loop_range, items, self.body(open_offset))

  def bound(self) -> Bound:
    match = RANGE_BOUND.match(self.text, self.pos)
    if match is None:
      raise self.error("expected a number or $variable for the range", self.pos)
    self.pos = match.end()
    return Bound(match[0], match.start())

  def call(self) -> Call:
    name, offset = self.read_name("expected a function name")
    open_offset = self.pos
    self.pos += 1
    args = self.values(open_offset, "call never closed, expected )")
    self.expect(";", "expected ; after the call")
    return Call(name, offset, args)

  def command(self) -> Command:
    offset = self.pos
    start, end = self.scan(";", "command never ended, expected ;", offset, track_parens=False, check_lines=True)
    self.pos = end + 1
    return Command(self.text[start:end], start)


# ---------- Expansion ----------

@dataclass
class Scope:
  """The variables a function body can see, besides globals."""
  params: dict[str, str]
  loops: dict[str, str]

EMPTY_SCOPE = Scope({}, {})


class Compiler:
  def __init__(self, src: Source, items: list[TopLevel]) -> None:
    self.src = src
    self.items = items
    self.funcs: dict[str, Func] = {}
    self.globals: dict[str, Global] = {}
    self.global_values: dict[str, str] = {}
    self.resolving: list[str] = [] # globals being resolved, to catch cycles
    self.calls: list[str] = []     # functions being expanded, to catch recursion
    self.trace: list[tuple[str, str]] = [] # (description, location), outermost first
    self.output: list[str] = []
    self.command_count = 0

  def error(self, message: str, offset: int | None) -> CompileError:
    lines: list[str] = []
    if self.trace:
      frames = list(reversed(self.trace))
      width = max(len(description) for description, _ in frames) + 3
      lines = [f"  in {description.ljust(width)}{where}" for description, where in frames]
    return self.src.error(message, offset, lines)

  def collect(self) -> Func:
    defined: dict[str, int] = {}
    for item in self.items:
      if isinstance(item, CompilerComment):
        continue
      if item.name in defined:
        line = self.src.line_col(defined[item.name])[0]
        raise self.error(f"${item.name} is already defined at line {line}", item.offset)
      defined[item.name] = item.offset
      if isinstance(item, Func):
        self.funcs[item.name] = item
      else:
        self.globals[item.name] = item
    for func in self.funcs.values():
      for param, offset in zip(func.params, func.param_offsets):
        if param in self.globals:
          raise self.error(f"${param} shadows a global", offset)
        if param in self.funcs:
          raise self.error(f"${param} shadows a function", offset)
    main = self.funcs.get("main")
    if main is None:
      raise self.error("missing func $main ()", None)
    if main.params:
      raise self.error("$main can't take arguments", main.offset)
    return main

  def run(self) -> str:
    main = self.collect()
    for item in self.items:
      if isinstance(item, CompilerComment):
        self.output.append(self.comment_line(item, EMPTY_SCOPE))
      elif item is main:
        self.trace.append(("$main", f"at {self.src.where(main.offset)}"))
        self.calls.append("main")
        self.run_body(main.body, Scope({}, {}))
        self.calls.pop()
        self.trace.pop()
    if self.command_count == 0:
      raise self.error("$main produced no commands", main.offset)
    return "\n".join(self.output) + "\n"

  def run_body(self, body: list[Statement], scope: Scope) -> None:
    for statement in body:
      match statement:
        case Command():
          text = collapse(self.substitute(statement.text, statement.offset, scope))
          if not text:
            raise self.error("empty command", statement.offset)
          if text.startswith(("!", "#--")):
            # the IR would read this line as a modifier or compiler comment
            raise self.error("commands can't start with ! or #--", statement.offset)
          if statement.modifiers:
            self.output.append("!" + ", ".join(m for m in MODIFIERS if m in statement.modifiers))
          self.output.append(text)
          self.command_count += 1
        case CompilerComment():
          self.output.append(self.comment_line(statement, scope))
        case Call():
          self.call(statement, scope)
        case For():
          self.loop(statement, scope)

  def comment_line(self, comment: CompilerComment, scope: Scope) -> str:
    return "#--" + self.substitute(comment.text, comment.offset, scope).rstrip()

  def call(self, call: Call, scope: Scope) -> None:
    name = call.name
    func = self.funcs.get(name)
    if func is None:
      if name in scope.params or name in scope.loops or name in self.globals:
        raise self.error(f"${name} is not a function", call.offset)
      raise self.error(f"undefined function ${name}", call.offset)
    if name == "main":
      raise self.error("$main can't be called", call.offset)
    if len(call.args) != len(func.params):
      raise self.error(f"${name} expects {plural(len(func.params), 'argument')}, got {len(call.args)}", call.offset)
    if name in self.calls:
      cycle = " -> ".join(f"${n}" for n in self.calls + [name])
      raise self.error(f"recursive call: {cycle}", call.offset)
    values = [collapse(self.substitute(arg.text, arg.offset, scope)) for arg in call.args]
    description = f"${name}(" + ", ".join(f"${p} = {v}" for p, v in zip(func.params, values)) + ")"
    self.trace.append((description, f"called at {self.src.where(call.offset)}"))
    self.calls.append(name)
    self.run_body(func.body, Scope(dict(zip(func.params, values)), {}))
    self.calls.pop()
    self.trace.pop()

  def loop(self, loop: For, scope: Scope) -> None:
    var = loop.var
    if var in self.funcs:
      raise self.error(f"${var} shadows a function", loop.var_offset)
    if var in self.globals:
      raise self.error(f"${var} shadows a global", loop.var_offset)
    if var in scope.params:
      raise self.error(f"${var} shadows a parameter", loop.var_offset)
    if var in scope.loops:
      raise self.error(f"${var} shadows an outer loop variable", loop.var_offset)
    if loop.items is not None:
      values = [collapse(self.substitute(item.text, item.offset, scope)) for item in loop.items]
    else:
      assert loop.range is not None
      low, high = (self.bound(bound, scope) for bound in loop.range)
      step = 1 if high >= low else -1
      values = [str(n) for n in range(low, high + step, step)]
    for value in values:
      self.trace.append((f"for ${var} = {value}", f"at {self.src.where(loop.for_offset)}"))
      self.run_body(loop.body, Scope(scope.params, {**scope.loops, var: value}))
      self.trace.pop()

  def bound(self, bound: Bound, scope: Scope) -> int:
    if not bound.text.startswith("$"):
      return int(bound.text)
    value = self.lookup(bound.text[1:], bound.offset, scope)
    if not INTEGER.fullmatch(value):
      raise self.error(f"range bound '{bound.text}' is '{value}', expected an integer", bound.offset)
    return int(value)

  def lookup(self, name: str, offset: int, scope: Scope) -> str:
    if name in self.funcs:
      raise self.error("functions produce commands and can't be used inside a command or value", offset)
    if name in scope.params:
      return scope.params[name]
    if name in scope.loops:
      return scope.loops[name]
    if name in self.globals:
      return self.global_value(name, offset)
    raise self.error(f"undefined variable ${name}", offset)

  def global_value(self, name: str, offset: int) -> str:
    if name in self.global_values:
      return self.global_values[name]
    if name in self.resolving:
      cycle = " -> ".join(f"${n}" for n in self.resolving + [name])
      raise self.error(f"recursive global: {cycle}", offset)
    self.resolving.append(name)
    value = self.globals[name].value
    self.global_values[name] = collapse(self.substitute(value.text, value.offset, EMPTY_SCOPE))
    self.resolving.pop()
    return self.global_values[name]

  def substitute(self, text: str, offset: int, scope: Scope) -> str:
    """Replaces $name, ${name} and $$ in text. offset is where text starts in the file."""
    out: list[str] = []
    i = 0
    while i < len(text):
      if text[i] != "$":
        out.append(text[i])
        i += 1
      elif text.startswith("$$", i):
        out.append("$")
        i += 2
      elif text.startswith("${", i):
        match = re.compile(rf"\$\{{({NAME})\}}").match(text, i)
        if match is None:
          raise self.error("unclosed ${", offset + i)
        out.append(self.lookup(match[1], offset + i, scope))
        i = match.end()
      else:
        match = re.compile(NAME).match(text, i + 1)
        if match is None:
          raise self.error("expected a variable name after $", offset + i)
        out.append(self.lookup(match[0], offset + i, scope))
        i = match.end()
    return "".join(out)


def compile_source(source: str, filename: str) -> str:
  """Compiles the text of a .mct file into IR text. Raises CompileError."""
  text = source.replace("\r\n", "\n").replace("\r", "\n")
  src = Source(text, filename)
  items = Parser(src, mask_comments(src)).parse_file()
  return Compiler(src, items).run()

def main(argv: list[str]) -> int:
  if len(argv) != 1:
    print("usage: uv run compile/compile.py <file.mct>", file=sys.stderr)
    return 2
  path = Path(argv[0])
  if path.suffix != ".mct":
    print(f"{path}: expected a .mct file", file=sys.stderr)
    return 2
  if not path.is_file():
    print(f"{path}: file not found", file=sys.stderr)
    return 2
  try:
    ir = compile_source(path.read_text(encoding="utf-8"), path.name)
  except CompileError as e:
    print(e, file=sys.stderr)
    return 1
  IR_DIR.mkdir(exist_ok=True)
  out_path = IR_DIR / f"{path.stem}.txt"
  out_path.write_text(ir, encoding="utf-8", newline="\n")
  print(f"wrote {out_path}")
  return 0

if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
