# MCT syntax highlighting

A TextMate grammar for `.mct` files (the language in [../LANG.md](../LANG.md)), as a local VS Code extension.

## Install

Build the package, install it, then run **Developer: Reload Window** in any open VS Code window.

    uv run tools/mct/vscode/package_vsix.py
    code --install-extension tools/mct/vscode/mct-syntax.vsix

After editing the grammar, run the same two commands again and reload. To remove it, run `code --uninstall-extension local.mct-syntax`.

## Limits

The grammar works line by line, so a few things are approximate:
- Any `$name[` gets the same colors whether or not `$name` is a table.
- The first word of every line in a command is colored as a command name, including continuation lines like `as @e`.
- `;` inside NBT (`[I;1,2]`) is colored like a command terminator.

Command text uses the same scopes as the mcfunction grammar (`keyword.control.flow`, `support.class` for selectors, `entity.name.function` for resource locations), so it matches `.mcfunction` files in most themes.
