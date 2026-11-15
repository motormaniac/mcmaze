"""Generates a command book based on book.yaml"""
"""Book Menu https://www.gamergeeks.net/apps/minecraft/give-command-generator/written-books"""

from dataclasses import dataclass
from pathlib import Path

import yaml

INPUT_FILE = "book.yaml"
PLAIN_TEXT_COLOR = "black"
COMMAND_COLOR = "blue"
# TARGET = "@p"
TARGET = "@a[scores={book=1}]" # for /trigger book


@dataclass
class Text:
  """A line of plain text."""
  text: str

@dataclass
class Command:
  """A clickable line that runs a command."""
  label: str
  command: str

type Line = Text | Command

@dataclass
class Page:
  lines: list[Line]
  heading: str | None = None

@dataclass
class Book:
  title: str
  author: str
  pages: list[Page]


def parse_line(raw: object) -> Line:
  """A line in the yaml is either plain text, or a single "label: command" mapping."""
  if isinstance(raw, str):
    return Text(raw)
  if isinstance(raw, dict) and len(raw) == 1:
    [(label, command)] = raw.items()
    return Command(str(label), str(command))
  raise ValueError(f"Each line must be plain text or a single 'label: command', got: {raw!r}")

def parse_page(raw: object) -> Page:
  if not isinstance(raw, dict):
    raise ValueError(f"Each page must be a mapping with a heading and lines, got: {raw!r}")
  heading = raw.get("heading")
  return Page(
    lines=[parse_line(line) for line in raw.get("lines") or []],
    heading=None if heading is None else str(heading),
  )

def load_book(path: Path) -> Book:
  with open(path, "r") as f:
    raw: object = yaml.safe_load(f)
  if not isinstance(raw, dict) or not isinstance(raw.get("pages"), list):
    raise ValueError(f"{path.name} must have a title, an author, and a list of pages")
  return Book(
    title=str(raw["title"]),
    author=str(raw["author"]),
    pages=[parse_page(page) for page in raw["pages"]],
  )


def text_component(line: Line) -> str:
  """Formats one line as a Minecraft text component."""
  match line:
    case Text(text):
      return f"{{text:\"{text}\\n\\n\",color:{PLAIN_TEXT_COLOR}}}"
    case Command(label, command):
      command = command.replace('"', '\\\"') # in all commands, replace " with \"
      return f"{{text:\"{label}\\n\\n\",color:{COMMAND_COLOR},click_event:{{action:run_command,command:\"{command}\"}}}}"

def page_text(page: Page) -> str:
  lines = ([Text(page.heading)] if page.heading is not None else []) + page.lines
  return ",".join(text_component(line) for line in lines)

def book_command(book: Book) -> str:
  pages_text = ",".join(f"[{page_text(page)}]" for page in book.pages)
  return f"give {TARGET} written_book[written_book_content={{pages:[{pages_text}],title:\"{book.title}\",author:\"{book.author}\"}}]"

def main() -> None:
  print(book_command(load_book(Path(__file__).with_name(INPUT_FILE))))

if __name__ == "__main__":
  main()
