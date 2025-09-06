import sqlite3, pathlib, re, sys
from collections import defaultdict

SQL_PATH = pathlib.Path("data/scddb/scddata.sql")
DB_PATH  = pathlib.Path("data/scddb/scddb.sqlite")

# Heuristics for table/column discovery
DANCE_LIKE_TABLES = re.compile(r"dance", re.I)
FORMATION_LIKE_TABLES = re.compile(r"formation", re.I)
MAP_LIKE_TABLES = re.compile(r"(map|link|join)", re.I)
CRIB_LIKE_TABLES = re.compile(r"crib", re.I)
MISC_TEXT_TABLES = re.compile(r"(note|description|comment|mobile|text)", re.I)

LIKELY_DANCE_NAME_COLS = {"name", "title"}
LIKELY_KIND_COLS = {"kind", "type", "rhythm", "meter", "time", "dance_type"}
LIKELY_SET_COLS = {"metaform", "set", "formation", "settype"}
LIKELY_BARS_COLS = {"length_bars", "bars", "barcount", "length"}
LIKELY_PROG_COLS = {"progression", "progress", "prog"}

def rebuild_db():
    # (Optional) drop & rebuild so your DB matches the .sql exactly.
    if DB_PATH.exists():
        DB_PATH.unlink()
    db = sqlite3.connect(DB_PATH)
    db.executescript(SQL_PATH.read_text(encoding="utf-8"))
    db.commit()
    db.close()

def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    return db

def list_tables(db):
    rows = db.execute("""
        SELECT name, type, sql
        FROM sqlite_master
        WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'
        ORDER BY type, name
    """).fetchall()
    return rows

def table_info(db, table):
    cols = db.execute(f"PRAGMA table_info({table})").fetchall()
    return cols

def count_rows(db, table):
    try:
        return db.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
    except Exception:
        return None

def pick_first_col(candidates, cols):
    names = {c["name"].lower() for c in cols}
    for group in (LIKELY_DANCE_NAME_COLS, LIKELY_KIND_COLS, LIKELY_SET_COLS, LIKELY_BARS_COLS, LIKELY_PROG_COLS):
        if candidates is group:
            pass
    for c in candidates:
        if c in names:
            return c
    return None

def find_candidate_tables(tables):
    dance_tbls, formation_tbls, map_tbls, crib_tbls, misc_text_tbls = [], [], [], [], []
    for t in tables:
        name = t["name"]
        if DANCE_LIKE_TABLES.search(name):     dance_tbls.append(name)
        if FORMATION_LIKE_TABLES.search(name): formation_tbls.append(name)
        if MAP_LIKE_TABLES.search(name):       map_tbls.append(name)
        if CRIB_LIKE_TABLES.search(name):      crib_tbls.append(name)
        if MISC_TEXT_TABLES.search(name):      misc_text_tbls.append(name)
    return dance_tbls, formation_tbls, map_tbls, crib_tbls, misc_text_tbls

def peek(db, table, limit=5):
    try:
        rows = db.execute(f"SELECT * FROM {table} LIMIT {limit}").fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        return [{"error": str(e)}]

def main():
    if not SQL_PATH.exists():
        print(f"Missing {SQL_PATH}. Put the downloaded scddata.sql there.", file=sys.stderr)
        sys.exit(1)

    print("Rebuilding scddb.sqlite from scddata.sql (once you’re happy, comment this out)...")
    rebuild_db()

    db = connect()

    print("\n=== Tables & views ===")
    tables = list_tables(db)
    for t in tables:
        n = count_rows(db, t["name"])
        print(f"- {t['type'].upper():4} {t['name']} ({n} rows)" if n is not None else f"- {t['type'].upper():4} {t['name']}")

    dance_tbls, formation_tbls, map_tbls, crib_tbls, misc_text_tbls = find_candidate_tables(tables)

    print("\nCandidates:")
    print("  dances:     ", dance_tbls)
    print("  formations: ", formation_tbls)
    print("  mappings:   ", map_tbls)
    print("  cribs:      ", crib_tbls)
    print("  misc-text:  ", misc_text_tbls)

    # Print columns for likely tables
    def print_cols(label, names):
        for name in names:
            cols = table_info(db, name)
            col_list = [f"{c['name']} ({c['type']})" for c in cols]
            print(f"\n[{label}] {name} columns:")
            print("  " + ", ".join(col_list))
            # show sample rows
            sample = peek(db, name, 3)
            print("  sample:", sample)

    print_cols("dance", dance_tbls)
    print_cols("formation", formation_tbls)
    print_cols("map", map_tbls)
    print_cols("crib", crib_tbls)

    # If we can guess columns, try a few sanity queries
    print("\n=== Sanity queries (best-effort) ===")
    # Pick a dance table
    dance_tbl = dance_tbls[0] if dance_tbls else None
    if dance_tbl:
        dcols = table_info(db, dance_tbl)
        dcolnames = [c["name"].lower() for c in dcols]
        name_col = (LIKELY_DANCE_NAME_COLS & set(dcolnames)) or {"name"} & set(dcolnames)
        name_col = next(iter(name_col)) if name_col else dcolnames[0]
        id_col = "id" if "id" in dcolnames else dcolnames[0]

        # Try to find kind/rhythm
        kind_col = next((c for c in LIKELY_KIND_COLS if c in dcolnames), None)
        set_col  = next((c for c in LIKELY_SET_COLS if c in dcolnames), None)
        bars_col = next((c for c in LIKELY_BARS_COLS if c in dcolnames), None)
        prog_col = next((c for c in LIKELY_PROG_COLS if c in dcolnames), None)

        # Count dances total
        tot = db.execute(f"SELECT COUNT(*) n FROM {dance_tbl}").fetchone()["n"]
        print(f"- Total dances in {dance_tbl}: {tot}")

        # Count by kind if available
        if kind_col:
            rows = db.execute(f"""
                SELECT {kind_col} AS kind, COUNT(*) n
                FROM {dance_tbl}
                GROUP BY {kind_col}
                ORDER BY n DESC
                LIMIT 10
            """).fetchall()
            print(f"- Top kinds ({kind_col}):", [dict(r) for r in rows])

        # Peek a few dances with useful fields
        sel_cols = [id_col, name_col] + [c for c in [kind_col, set_col, bars_col, prog_col] if c]
        sel_cols_sql = ", ".join(sel_cols)
        try:
            rows = db.execute(f"""
                SELECT {sel_cols_sql}
                FROM {dance_tbl}
                ORDER BY {name_col} COLLATE NOCASE
                LIMIT 10
            """).fetchall()
            print("- Sample dances:", [dict(r) for r in rows])
        except Exception as e:
            print(f"- Couldn’t select sample dances: {e}")

        # Try joining formations if a mapping table exists
        if formation_tbls and map_tbls:
            form_tbl = formation_tbls[0]
            form_cols = [c["name"].lower() for c in table_info(db, form_tbl)]
            form_id = "id" if "id" in form_cols else form_cols[0]
            form_name = "name" if "name" in form_cols else form_cols[1] if len(form_cols) > 1 else form_cols[0]

            # pick a plausible map table with both dance_id and formation_id
            candidate_map = None
            for m in map_tbls:
                mcols = [c["name"].lower() for c in table_info(db, m)]
                if any("dance" in c for c in mcols) and any("formation" in c for c in mcols):
                    candidate_map = m
                    break

            if candidate_map:
                mcols = [c["name"].lower() for c in table_info(db, candidate_map)]
                dance_fk = next((c for c in mcols if "dance" in c), None)
                form_fk  = next((c for c in mcols if "formation" in c), None)
                try:
                    rows = db.execute(f"""
                        SELECT d.{id_col} AS dance_id, d.{name_col} AS dance_name,
                               f.{form_name} AS formation
                        FROM {dance_tbl} d
                        JOIN {candidate_map} m ON m.{dance_fk} = d.{id_col}
                        JOIN {form_tbl} f ON f.{form_id} = m.{form_fk}
                        LIMIT 10
                    """).fetchall()
                    print("- Sample dance → formation join:", [dict(r) for r in rows])
                except Exception as e:
                    print(f"- Join failed: {e}")

    # Try to locate a metadata table if present
    try:
        meta = db.execute("SELECT name FROM sqlite_master WHERE name LIKE '%metadata%'").fetchall()
        if meta:
            mname = meta[0]["name"]
            print(f"\n- Found metadata table: {mname}")
            print("  Sample:", [dict(r) for r in db.execute(f"SELECT * FROM {mname} LIMIT 5")])
    except Exception:
        pass

    db.close()

if __name__ == "__main__":
    main()

