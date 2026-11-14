"""Packages this folder as a .vsix that `code --install-extension` accepts. No dependencies.

  uv run compile/vscode/package_vsix.py
  code --install-extension compile/vscode/mct-syntax.vsix
"""

import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).parent
FILES = ["package.json", "language-configuration.json", "README.md", "syntaxes/mct.tmLanguage.json"]


def manifest(package: dict[str, str]) -> str:
  return f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id="{package['name']}" Version="{package['version']}" Publisher="{package['publisher']}" />
    <DisplayName>{escape(package['displayName'])}</DisplayName>
    <Description xml:space="preserve">{escape(package['description'])}</Description>
    <Categories>Programming Languages</Categories>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{package['engines']['vscode']}" />
    </Properties>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code" />
  </Installation>
  <Dependencies />
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
  </Assets>
</PackageManifest>
"""


CONTENT_TYPES = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension=".json" ContentType="application/json" />
  <Default Extension=".md" ContentType="text/markdown" />
  <Default Extension=".vsixmanifest" ContentType="text/xml" />
</Types>
"""


def main() -> None:
  package = json.loads((HERE / "package.json").read_text(encoding="utf-8"))
  for name in FILES:
    if name.endswith(".json"):
      json.loads((HERE / name).read_text(encoding="utf-8")) # fail early on a JSON typo
  out = HERE / f"{package['name']}.vsix"
  with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as vsix:
    vsix.writestr("[Content_Types].xml", CONTENT_TYPES)
    vsix.writestr("extension.vsixmanifest", manifest(package))
    for name in FILES:
      vsix.write(HERE / name, f"extension/{name}")
  print(f"wrote {out}")


if __name__ == "__main__":
  main()
