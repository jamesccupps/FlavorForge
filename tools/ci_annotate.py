"""Turn failed tests in a pytest JUnit XML report into GitHub annotations.

    python tools/ci_annotate.py junit.xml

Run by CI after a failed test step. A job's log needs a GitHub sign-in to
read; its annotations do not -- they show on the run page and through the
public API -- so each failure becomes one, with the test's name and the end
of its traceback. Prints nothing when there are no failures.
"""
import sys
import xml.etree.ElementTree as ET


def _escape(text: str) -> str:
    # GitHub workflow-command escaping for the message part.
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def annotations(xml_text: str, tail_lines: int = 12):
    root = ET.fromstring(xml_text)
    for case in root.iter("testcase"):
        for kind in ("failure", "error"):
            node = case.find(kind)
            if node is None:
                continue
            name = f"{case.get('classname', '')}::{case.get('name', '')}"
            detail = (node.text or node.get("message") or "").strip().splitlines()
            body = "\n".join(detail[-tail_lines:])
            yield f"::error title={kind}: {name}::{_escape(body)}"


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: ci_annotate.py <junit.xml>", file=sys.stderr)
        return 2
    try:
        text = open(argv[1], encoding="utf-8").read()
    except OSError as exc:
        print(f"::error title=no test report::{exc}")
        return 0
    for line in annotations(text):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
