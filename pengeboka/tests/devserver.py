"""Lokal testserver med oppdiktede data.

Kjør: python3 pengeboka/tests/devserver.py [port] [databasesti] [--tom]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["PENGEBOKA_DEV"] = "1"
HER = Path(__file__).resolve().parent
sys.path.insert(0, str(HER.parent / "app"))
sys.path.insert(0, str(HER))

import eksempel  # noqa: E402
import main  # noqa: E402


def fyll(pb) -> None:
    data = eksempel.lag(pb.i_dag(), 4)
    for navn, typ, skjult, fn in [("Felleskonto", "felles", 0, eksempel.csv_dnb), ("Kredittkort", "kreditt", 0, eksempel.csv_enkel),
                                  ("Sparekonto", "sparing", 1, eksempel.csv_dnb), ("Brukskonto", "bruk", 0, eksempel.csv_dnb)]:
        k = pb.lagre_konto({"navn": navn, "type": typ, "skjult": skjult})
        nokkel = {"felles": "felles", "kreditt": "kreditt", "sparing": "sparing", "bruk": "privat"}[typ]
        pb.importer(fn(data[nokkel]), f"{navn}.csv", k["id"], None, "Test")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = int(args[0]) if args else 8099
    db = Path(args[1]) if len(args) > 1 else HER.parent / "data" / "dev.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    ny = not db.exists()
    srv = main.start(port, db)
    if ny and "--tom" not in sys.argv:
        fyll(main.PB)
    print(f"Pengeboka (utvikling) på http://127.0.0.1:{port}", flush=True)
    srv.serve_forever()
