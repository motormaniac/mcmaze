"""Runs every example in tests/pass and tests/fail through the compiler.

pass/<name>.mct must compile to exactly pass/<name>.txt.
fail/<name>.mct must raise CompileError, and fail/<name>.err holds the expected error:
  - the first line must match exactly
  - any other lines are the expected expansion trace (spacing is ignored)
Errors with a line and column must also show that source line with a caret under the column.
"""

import re
from pathlib import Path

import pytest

from compile import CompileError, compile_source

TESTS = Path(__file__).parent
PASS = sorted((TESTS / "pass").glob("*.mct"))
FAIL = sorted((TESTS / "fail").glob("*.mct"))


def squash(line: str) -> str:
  return " ".join(line.split())


@pytest.mark.parametrize("source", PASS, ids=lambda p: p.stem)
def test_pass(source: Path) -> None:
  expected = source.with_suffix(".txt").read_text()
  assert compile_source(source.read_text(), source.name) == expected


@pytest.mark.parametrize("source", FAIL, ids=lambda p: p.stem)
def test_fail(source: Path) -> None:
  expected = source.with_suffix(".err").read_text().splitlines()
  with pytest.raises(CompileError) as info:
    compile_source(source.read_text(), source.name)
  actual = str(info.value).splitlines()

  assert actual[0] == expected[0]

  location = re.match(rf"{re.escape(source.name)}:(\d+):(\d+): ", actual[0])
  if location:
    line, column = int(location[1]), int(location[2])
    source_line = source.read_text().splitlines()[line - 1]
    assert actual[1] == "    " + source_line
    assert actual[2] == " " * (4 + column - 1) + "^"

  expected_trace = [squash(line) for line in expected[1:]]
  if expected_trace:
    actual_trace = [squash(line) for line in actual if line.startswith("  in ")]
    assert actual_trace == expected_trace


def test_windows_line_endings() -> None:
  source = "func $main () (\r\n  execute\r\n    as @n\r\n    run say hi;\r\n)\r\n"
  assert compile_source(source, "crlf.mct") == "execute as @n run say hi\n"


def test_error_without_location_has_no_snippet() -> None:
  with pytest.raises(CompileError) as info:
    compile_source("-- empty file\n", "empty.mct")
  assert str(info.value) == "empty.mct: missing func $main ()"
