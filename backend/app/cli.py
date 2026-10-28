"""Operations CLI:  python -m app.cli <command>"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_migrate(_: argparse.Namespace) -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    command.upgrade(cfg, "head")
    print("database is at the latest migration")


def cmd_download(a: argparse.Namespace) -> None:
    from .ml import registry

    keys = a.only or list(registry.SPECS)
    for k in keys:
        spec = registry.get_spec(k)
        print(f"downloading {spec.repo_id}@{spec.revision[:10]} (~{spec.approx_disk_mb} MB) ...", flush=True)
        print("  ->", registry.download(spec))


def cmd_status(_: argparse.Namespace) -> None:
    from .ml import registry

    print(json.dumps(registry.status(), indent=2))


def _db():
    from .db import SessionLocal

    return SessionLocal()


def cmd_ingest_manifest(a: argparse.Namespace) -> None:
    from .rag import ingest

    with _db() as db:
        rep = ingest.ingest_manifest(db, Path(a.manifest), a.models)
    print(json.dumps(rep, indent=2, ensure_ascii=False))


def cmd_ingest_sci(a: argparse.Namespace) -> None:
    from .rag import ingest

    with _db() as db:
        rep = ingest.ingest_sci(db, a.year, a.limit, a.offset, a.models)
    for r in rep:
        print(r)
    print("summary:", {k: sum(1 for r in rep if r["action"] == k) for k in {r["action"] for r in rep}})


def cmd_embed(a: argparse.Namespace) -> None:
    from .rag import ingest

    with _db() as db:
        print("embedded", ingest.embed_missing(db, a.models), "chunk vectors")


def cmd_corpus(_: argparse.Namespace) -> None:
    from sqlalchemy import func, select

    from .models import LegalChunk, LegalSource

    with _db() as db:
        rows = db.execute(select(LegalSource.doc_type, LegalSource.is_synthetic, func.count(LegalSource.id)).group_by(LegalSource.doc_type, LegalSource.is_synthetic)).all()
        print("sources:", [tuple(r) for r in rows], "chunks:", db.scalar(select(func.count(LegalChunk.id))))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="nyaya")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate").set_defaults(fn=cmd_migrate)
    d = sub.add_parser("download-models")
    d.add_argument("--only", nargs="*", help="model keys: inlegalbert incaselawbert custominlawbert inlegaltrans local_llm")
    d.set_defaults(fn=cmd_download)
    sub.add_parser("model-status").set_defaults(fn=cmd_status)
    sub.add_parser("corpus").set_defaults(fn=cmd_corpus)
    m = sub.add_parser("ingest-manifest")
    m.add_argument("manifest")
    m.add_argument("--models", nargs="*", default=["inlegalbert", "incaselawbert", "custominlawbert"])
    m.set_defaults(fn=cmd_ingest_manifest)
    s = sub.add_parser("ingest-sci", help="English Supreme Court judgments from the public open dataset")
    s.add_argument("--year", type=int, required=True)
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--offset", type=int, default=0)
    s.add_argument("--models", nargs="*", default=["inlegalbert", "incaselawbert", "custominlawbert"])
    s.set_defaults(fn=cmd_ingest_sci)
    e = sub.add_parser("embed")
    e.add_argument("--models", nargs="*", default=["inlegalbert", "incaselawbert", "custominlawbert"])
    e.set_defaults(fn=cmd_embed)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main(sys.argv[1:])
