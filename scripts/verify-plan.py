#!/usr/bin/env python3
"""Select reliability checks for a change and validate the checklist table.

The table in docs/RELIABILITY.md is the single source of truth. Trigger cells
contain backticked file globs and ~symbol tokens; this tool never edits them.
"""
import argparse
import fnmatch
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CHECKLIST = ROOT / "docs/RELIABILITY.md"
SCENARIOS = tuple(sorted((ROOT / "tests/reliability").glob("*.test.js")))
ROW = re.compile(r"^\|\s*(RC-\d{2})\s*\|")
TOKEN = re.compile(r"`([^`]+)`")
CASE = re.compile(r"\bHC-\d{2}\b")
SCENARIO = re.compile(r"test\(\s*['\"](HC-\d{2})")


class ChecklistError(ValueError):
    """The checklist is malformed or out of sync with its regression cases."""


def scenarios_text():
    return "\n".join(path.read_text() for path in SCENARIOS)


def parse(text):
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        if not ROW.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5:
            raise ChecklistError(f"line {number}: expected 5 columns, found {len(cells)}")
        rid, risk, trigger, verify, evidence = cells
        tokens = TOKEN.findall(trigger)
        rows.append({
            "id": rid,
            "risk": risk,
            "paths": [token for token in tokens if not token.startswith("~")],
            "symbols": [token[1:] for token in tokens if token.startswith("~")],
            "verify": verify,
            "evidence": evidence,
            "line": number,
        })
    if not rows:
        raise ChecklistError(f"no RC rows found in {CHECKLIST.name}")
    return rows


def validate(rows, scenarios):
    ids = [row["id"] for row in rows]
    duplicates = sorted({rid for rid in ids if ids.count(rid) > 1})
    if duplicates:
        raise ChecklistError("duplicate checklist ids: " + ", ".join(duplicates))
    for row in rows:
        if not row["paths"]:
            raise ChecklistError(f"{row['id']}: add at least one backticked path trigger")
        if not row["verify"]:
            raise ChecklistError(f"{row['id']}: add the invariant to verify")
        if not row["evidence"]:
            raise ChecklistError(f"{row['id']}: cite the regression or native evidence to check")
    cited = set(CASE.findall(" ".join(row["evidence"] for row in rows)))
    cases = set(SCENARIO.findall(scenarios))
    missing = sorted(cited - cases)
    unlisted = sorted(cases - cited)
    if missing:
        raise ChecklistError("checklist cites missing cases: " + ", ".join(missing))
    if unlisted:
        raise ChecklistError("regression cases absent from the checklist: " + ", ".join(unlisted))


def match(rows, files, sections):
    hits = []
    for row in rows:
        matched = [name for name in files
                   if any(fnmatch.fnmatchcase(name, pattern) for pattern in row["paths"])]
        if not matched:
            continue
        if row["symbols"]:
            text = "\n".join(line for name in matched for line in sections.get(name, []))
            if not any(symbol in text for symbol in row["symbols"]):
                continue
        hits.append(row)
    return hits


def parse_diff(text):
    sections, current, hunk = {}, None, False
    for line in text.splitlines():
        if line.startswith("diff --git "):
            current, hunk = None, False
        elif not hunk and line.startswith("--- "):
            old = line[4:].split("\t", 1)[0]
            current = None if old == "/dev/null" else (old[2:] if old.startswith("a/") else old)
        elif not hunk and line.startswith("+++ "):
            new = line[4:].split("\t", 1)[0]
            if new != "/dev/null":
                current = new[2:] if new.startswith("b/") else new
        elif line.startswith("@@"):
            hunk = True
        elif hunk and current and line[:1] in "+-":
            sections.setdefault(current, []).append(line)
    return sections


def file_sections(path):
    try:
        if not path.is_file() or path.stat().st_size >= 2_000_000:
            return None
        return ["+" + line for line in path.read_text().splitlines()]
    except (OSError, UnicodeDecodeError):
        return None


def git(*args):
    result = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if result.returncode:
        raise ChecklistError(result.stderr.strip() or "git failed")
    return result.stdout


def changed(revision):
    files = [name for name in git("diff", "--name-only", revision).splitlines() if name]
    untracked = [name for name in git("ls-files", "--others", "--exclude-standard").splitlines() if name]
    sections = parse_diff(git("diff", "-U0", revision))
    for name in untracked:
        content = file_sections(ROOT / name)
        if content is not None:
            sections[name] = content
    return files + untracked, sections


def report(rows):
    for row in rows:
        print(f"  {row['id']}  {row['risk']}")
        print(f"         {row['verify']}")
        print(f"         Evidence: {row['evidence']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate the table and its case links")
    parser.add_argument("--list", action="store_true", help="Print every checklist row")
    parser.add_argument("--diff", nargs="?", const="HEAD", metavar="REVISION",
                        help="Print rows matching changes against REVISION (default HEAD)")
    args = parser.parse_args()
    if not (args.check or args.list or args.diff):
        parser.error("choose --check, --list or --diff")
    try:
        rows = parse(CHECKLIST.read_text())
        validate(rows, scenarios_text())
        if args.check:
            print(f"Reliability checklist OK: {len(rows)} rows, cases linked")
        if args.list:
            report(rows)
        if args.diff is not None:
            files, sections = changed(args.diff)
            hits = match(rows, files, sections)
            if not hits:
                print(f"No reliability row matched {args.diff} ({len(files)} changed file(s)). "
                      "The coupled contracts in docs/FEATURE-DICTIONARY.md still apply.")
            else:
                print(f"{len(hits)} of {len(rows)} reliability rows match {args.diff} "
                      f"({len(files)} changed file(s)):")
                report(hits)
    except (ChecklistError, subprocess.CalledProcessError, OSError) as error:
        parser.exit(1, f"jira-peek: {error}\n")


if __name__ == "__main__":
    main()
