"""Verify the integrity stamp on an AtlasLens CSV export.

Usage:
    python -m atlaslens.cli.verify_export export.csv
"""

import argparse
import csv
import hashlib
import re
import sys


def verify(path: str) -> bool:
    with open(path, newline="") as f:
        content = f.read()

    match = re.search(
        r"# Integrity: count=(\d+) sha256=([0-9a-f]+) "
        r"generated_at=(\S+)",
        content,
    )
    if not match:
        print("No integrity stamp found.")
        return False

    expected_count = int(match.group(1))
    expected_hash = match.group(2)
    generated_at = match.group(3)

    lines_before_stamp = content.split("\n# Integrity:")[0]
    reader = csv.DictReader(lines_before_stamp.splitlines())
    hasher = hashlib.sha256()
    actual_count = 0
    for row in reader:
        event_id = row.get("id", "")
        hasher.update(event_id.encode())
        actual_count += 1

    actual_hash = hasher.hexdigest()

    ok = True
    if actual_count != expected_count:
        print(
            f"FAIL: count mismatch — "
            f"expected {expected_count}, got {actual_count}"
        )
        ok = False
    if actual_hash != expected_hash:
        print(
            f"FAIL: SHA-256 mismatch — "
            f"expected {expected_hash}, got {actual_hash}"
        )
        ok = False

    if ok:
        print(
            f"OK: {actual_count} records, "
            f"hash matches, generated {generated_at}"
        )
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify AtlasLens export integrity"
    )
    parser.add_argument("file", help="Path to the CSV export")
    args = parser.parse_args()

    if not verify(args.file):
        sys.exit(1)


if __name__ == "__main__":
    main()
