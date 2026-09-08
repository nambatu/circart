#!/usr/bin/env python3
"""
Repair mojibake in artline.json.

Text that was written as UTF-8 and then read back as cp1252/Latin-1 comes out
as "Duerer" -> "DÃ¼rer". This walks every string in the file and reverses that
round-trip wherever it cleanly applies, leaving everything else untouched.

cp1252 is tried before latin-1 because Windows reads with cp1252, which maps
bytes 0x80-0x9F to characters latin-1 has no room for (0x89 -> per-mille,
0x99 -> trademark). Those are exactly the cases latin-1 alone cannot repair.

    python fix_encoding.py www/artline.json www-mobile/artline.json
"""
import json
import sys

MARKERS = ("Ã", "Â", "â€")


def unmangle(s):
    """Reverse UTF-8-read-as-cp1252/latin-1, repeatedly, but only when safe."""
    for _ in range(3):
        if not any(m in s for m in MARKERS):
            break
        candidate = None
        for codec in ("cp1252", "latin-1"):
            try:
                candidate = s.encode(codec).decode("utf-8")
                break
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue   # not double-encoded through this codec
        if candidate is None or candidate == s:
            break
        s = candidate
    return s


def walk(node, changes):
    if isinstance(node, str):
        fixed = unmangle(node)
        if fixed != node:
            changes.append((node[:70], fixed[:70]))
        return fixed
    if isinstance(node, list):
        return [walk(v, changes) for v in node]
    if isinstance(node, dict):
        return {k: walk(v, changes) for k, v in node.items()}
    return node


def main(paths):
    for path in paths:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        changes = []
        data = walk(data, changes)

        if not changes:
            print(f"{path}: already clean")
            continue

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"{path}: repaired {len(changes)} strings")
        for before, after in changes[:8]:
            print(f"    {before}  ->  {after}")
        if len(changes) > 8:
            print(f"    ... and {len(changes) - 8} more")


if __name__ == "__main__":
    args = sys.argv[1:] or ["www/artline.json", "www-mobile/artline.json"]
    main(args)
