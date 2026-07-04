"""Generates a command book based on a given csv file"""
"""Book Menu https://www.gamergeeks.net/apps/minecraft/give-command-generator/written-books"""

from pathlib import Path

FILE_NAME = "book_command.txt"
BOOK_NAME = "Command Book"
AUTHOR = "gatortiger12"
PLAIN_TEXT_COLOR = "black"
COMMAND_COLOR = "blue"
# TARGET = "@p"
TARGET = "@a[scores={book=1}]" # for /trigger book
DELIMITER = "|"
PAGE_DELIMITER = "||"

content = ""

with open(Path(__file__).with_name(FILE_NAME), "r") as f:
  pages = []
  current_page = []
  for line in f:
    # ignore comments
    if line.strip().startswith("--"):
      continue
    if line.strip() == PAGE_DELIMITER:
      pages.append(",".join(current_page))
      current_page = []
      continue
    words = line.strip().split(DELIMITER)
    if len(words) < 2:
      text = f"{{text:\"{line.strip()}\\n\\n\",color:{PLAIN_TEXT_COLOR}}}"
      current_page.append(text)
      continue
    command_text = words[0]
    command = words[1].replace('"', '\\\"') # in all commands, replace " with \"
    text = f"{{text:\"{command_text}\\n\\n\",color:{COMMAND_COLOR},click_event:{{action:run_command,command:\"{command}\"}}}}"
    current_page.append(text)
  if len(current_page) > 0:
    pages.append(",".join(current_page))
  pages_text = ",".join([f"[{page}]" for page in pages])
  book_text = f"give {TARGET} written_book[written_book_content={{pages:[{pages_text}],title:\"{BOOK_NAME}\",author:\"{AUTHOR}\"}}]"
  print(book_text)
