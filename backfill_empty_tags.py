"""
Backfill empty fact_tags — 修复714条空标签
==========================================
复用 shadow_sand 已有的 _ENTITY_RE 管线，不建新提取器。

用法：
    python backfill_empty_tags.py

前提：确保没有其他进程持有 shadow_sand.db 的写锁。
如果报 "database is locked"，先停掉 Hermes Agent 再运行。
"""
import sqlite3
import os
import re
import sys

# Same regex as shadow_sand.py
_ENTITY_RE = re.compile(
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b|'
    r'"([^"]+)"|'
    r"'([^']+)'|"
    r'([\u4e00-\u9fff]{2,4})'
)

NB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DB = os.path.join(NB, "shadow_sand.db")
SANDGLASS = os.path.join(NB, "sandglass.txt")


def extract_tags(text: str) -> str:
    """Extract tags from text using _ENTITY_RE — same pipeline as shadow_index"""
    if not text:
        return ""
    entities = []
    for m in _ENTITY_RE.finditer(text):
        name = m.group(1) or m.group(2) or m.group(3) or m.group(4) or ""
        name = name.strip()
        if name and len(name) > 1:
            entities.append(name)
    seen = set()
    unique = []
    for e in entities:
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return ",".join(unique[:5])


def main():
    # Connect with WAL and long timeout
    db = sqlite3.connect(DB, timeout=60)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=60000")

    # Find all empty fact_tags
    empty_rows = db.execute(
        "SELECT line_num FROM fact_tags WHERE tags = '' OR tags IS NULL"
    ).fetchall()

    if not empty_rows:
        print("✅ No empty fact_tags found — nothing to backfill!")
        db.close()
        return

    print(f"Found {len(empty_rows)} empty fact_tags to backfill")

    # Read sandglass.txt
    with open(SANDGLASS, "r", encoding="utf-8") as f:
        sandglass_lines = f.readlines()

    updated = 0
    skipped = 0

    for line_num, in empty_rows:
        idx = line_num - 1
        if idx < 0 or idx >= len(sandglass_lines):
            skipped += 1
            continue

        raw_line = sandglass_lines[idx]
        parts = raw_line.split(" | ", 2)
        text = parts[2].strip() if len(parts) >= 3 else raw_line.strip()

        if not text:
            skipped += 1
            continue

        tags = extract_tags(text)
        if tags:
            db.execute(
                "UPDATE fact_tags SET tags = ? WHERE line_num = ?",
                (tags, line_num),
            )
            updated += 1
        else:
            skipped += 1

        if (updated + skipped) % 100 == 0:
            db.commit()
            print(
                f"  Progress: {updated + skipped}/{len(empty_rows)} "
                f"(updated={updated}, skipped={skipped})"
            )

    db.commit()

    remaining = db.execute(
        "SELECT COUNT(*) FROM fact_tags WHERE tags = '' OR tags IS NULL"
    ).fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM fact_tags").fetchone()[0]

    print(f"\n✅ Backfill complete!")
    print(f"   Updated: {updated}")
    print(f"   Skipped: {skipped} (no entities found or blank lines)")
    print(f"   Remaining empty: {remaining}/{total}")

    # Show samples
    print("\n--- Sample backfilled tags ---")
    for row in db.execute(
        "SELECT line_num, tags FROM fact_tags "
        "WHERE tags != '' AND category = 'exam_general' "
        "ORDER BY line_num LIMIT 5"
    ):
        print(f"  line={row[0]} tags={row[1][:80]}")

    db.close()


if __name__ == "__main__":
    main()
