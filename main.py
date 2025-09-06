import sqlite3, pathlib

def main():
    db = sqlite3.connect("data/scddb/scddb.sqlite")
    db.executescript(pathlib.Path("data/scddb/scddata.sql").read_text())
    db.commit()


if __name__ == "__main__":
    main()
