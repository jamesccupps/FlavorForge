"""Print one version's CHANGELOG section as GitHub release notes.

    python tools/release_notes.py v3.4.0 > notes.md

Used by .github/workflows/release.yml. Exits non-zero if the version has no
section, so a tag pushed before its changelog entry fails the release instead
of publishing empty notes.

The CHANGELOG is hard-wrapped at about 78 columns. GitHub renders a single
newline in release notes as a line break, so continuation lines are joined
back onto their paragraph or list item; headings, list items and blank lines
are kept as they are.
"""
import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def section(text: str, version: str) -> str:
    """The body under `## [version]`, up to the next `## ` heading."""
    version = version.lstrip("v")
    head = re.search(r"^## \[" + re.escape(version) + r"\][^\n]*\n", text, re.M)
    if not head:
        raise KeyError(version)
    rest = text[head.end():]
    nxt = re.search(r"^## ", rest, re.M)
    return (rest[:nxt.start()] if nxt else rest).strip()


def unwrap(body: str) -> str:
    out = []
    for line in body.split("\n"):
        starts_block = (not line.strip() or line.startswith(("- ", "#", ">"))
                        or re.match(r"\d+\. ", line))
        if out and out[-1].strip() and not out[-1].startswith("#") and not starts_block:
            out[-1] = out[-1].rstrip() + " " + line.strip()
        else:
            out.append(line)
    return "\n".join(out)


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: release_notes.py <version or tag>", file=sys.stderr)
        return 2
    try:
        body = section(CHANGELOG.read_text(encoding="utf-8"), argv[1])
    except KeyError:
        print(f"CHANGELOG.md has no section for {argv[1]}", file=sys.stderr)
        return 1
    sys.stdout.reconfigure(encoding="utf-8")
    print(unwrap(body))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
