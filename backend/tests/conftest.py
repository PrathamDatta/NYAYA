from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.mkdtemp(prefix="nyaya-test-")
os.environ.update({"NYAYA_ENV": "test", "NYAYA_DATA_DIR": _TMP, "NYAYA_DATABASE_URL": "", "NYAYA_INCLUDE_SYNTHETIC_CORPUS": "true",
                   "NYAYA_SERVE_FRONTEND": "false", "NYAYA_RATE_LIMIT_PER_MINUTE": "100000", "NYAYA_AUTH_RATE_LIMIT_PER_MINUTE": "100000",
                   "NYAYA_MODEL_DIR": os.environ.get("NYAYA_TEST_MODEL_DIR", str(Path(__file__).resolve().parents[2] / "data" / "models"))})

from fastapi.testclient import TestClient  # noqa: E402

from app import runtime  # noqa: E402
from app.ml.registry import SPECS, is_downloaded  # noqa: E402

H = {"X-Requested-With": "nyaya"}

SYNTH_ACT = """THE SYNTHETIC CONSUMER REFUND ACT, 2099 (TEST FIXTURE - NOT REAL LAW)

1. Short title.- This Act may be called the Synthetic Consumer Refund Act, 2099 and extends to the whole of India.

2. Definitions.- In this Act, "seller" means a person who sells goods to a consumer and "defect" means any fault in the goods supplied to the consumer under a sale.

3. Refund of price.- Where goods supplied by a seller are defective, the consumer may demand a refund of the price paid within thirty days of delivery, and the seller shall refund the price within fifteen days of the demand.

4. Complaint to the Tribunal.- A consumer whose demand for refund is not met may file a complaint before the Synthetic Tribunal within two years from the date of the demand.

5. Exceptions.- Nothing in section 3 applies to goods purchased for resale or for a commercial purpose by the consumer.
"""

SYNTH_LEASE = """THE SYNTHETIC LEASE DEPOSIT ACT, 2099 (TEST FIXTURE - NOT REAL LAW)

1. Short title.- This Act may be called the Synthetic Lease Deposit Act, 2099.

2. Return of deposit.- A lessor shall return the security deposit to the lessee within thirty days of the lessee vacating the premises and handing over possession, after deducting only proved arrears of rent.

3. Notice of vacation.- A lessee who intends to vacate the premises shall give the lessor written notice of one month, unless the lease deed provides otherwise.

4. Remedy.- A lessee whose deposit is not returned may apply to the Rent Tribunal for an order directing the lessor to return the deposit with interest.
"""


@pytest.fixture(scope="session")
def models_present() -> bool:
    return all(is_downloaded(SPECS[k]) for k in ("inlegalbert", "incaselawbert", "custominlawbert"))


@pytest.fixture(scope="session", autouse=True)
def _schema():
    from alembic.config import Config

    from alembic import command

    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(scope="session")
def corpus(_schema):
    from app.db import SessionLocal
    from app.rag.ingest import add_source

    db = SessionLocal()
    for ident, title, text in (("SYN-1", "Synthetic Consumer Refund Act, 2099", SYNTH_ACT), ("SYN-2", "Synthetic Lease Deposit Act, 2099", SYNTH_LEASE)):
        add_source(db, {"doc_type": "statute", "title": title, "identifier": ident, "authority": "Test", "status": "in_force",
                        "source_url": f"https://example.invalid/{ident}", "is_synthetic": True, "effective_from": "2099-01-01" if False else None}, [text])
    db.close()
    yield


@pytest.fixture(autouse=True)
def _bm25_default(monkeypatch):
    monkeypatch.setattr(runtime, "RETRIEVAL_COMPONENTS", ["bm25"])
    from app.security import limiter

    limiter.reset()


@pytest.fixture()
def client(corpus):
    from app.main import create_app

    with TestClient(create_app(), base_url="http://testserver") as c:
        c.headers.update(H)
        yield c


_n = iter(range(10_000))


@pytest.fixture()
def user(client):
    email = f"user{next(_n)}@example.com"
    r = client.post("/api/auth/register", json={"email": email, "password": "correct-horse-battery", "display_name": "T"})
    assert r.status_code == 201, r.text
    return {"email": email, "password": "correct-horse-battery"}


def new_client(corpus):
    from app.main import create_app

    c = TestClient(create_app(), base_url="http://testserver")
    c.headers.update(H)
    return c
