from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import errors
from .config import get_settings
from .security import limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
                               "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
}


def create_app() -> FastAPI:
    s = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        from pathlib import Path

        from alembic.config import Config

        from alembic import command

        if s.env != "test":  # tests build their own schema through the same migrations
            cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
            command.upgrade(cfg, "head")
        yield

    app = FastAPI(title="Nyaya Bharatha API", version="2.0.0", lifespan=lifespan,
                  docs_url=None if s.is_prod else "/api/docs", redoc_url=None, openapi_url=None if s.is_prod else "/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-Requested-With"])
    errors.install(app)

    @app.middleware("http")
    async def guard(request: Request, call_next):  # noqa: ANN202
        path = request.url.path
        ip = request.client.host if request.client else "unknown"
        if path.startswith("/api/"):
            bucket, limit = ("auth", s.auth_rate_limit_per_minute) if path.startswith("/api/auth/") and request.method == "POST" else ("api", s.rate_limit_per_minute)
            if not limiter.allow(ip, bucket, limit):
                return errors.err(429, "rate_limited", "Too many requests. Please wait a minute and try again.")
            if request.method in ("POST", "PUT", "DELETE", "PATCH"):
                origin = request.headers.get("origin")
                host_ok = origin is None or origin in s.cors_origins or origin.split("://", 1)[-1] == request.headers.get("host")
                if not host_ok or request.headers.get("x-requested-with") != "nyaya":
                    return errors.err(403, "csrf", "Cross-site request blocked.")
            cl = request.headers.get("content-length")
            if cl and cl.isdigit() and int(cl) > (s.max_upload_mb + 1) * 1024 * 1024:
                return errors.err(413, "too_large", f"Request exceeds the {s.max_upload_mb} MB limit.")
        resp = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            resp.headers.setdefault(k, v)
        if s.cookie_secure:
            resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    from .routers import aid, auth, cases, chat, documents, drafts, library, system

    for r in (system, auth, chat, library, documents, drafts, cases, aid):
        app.include_router(r.router, prefix="/api")

    dist = s.frontend_dist
    if s.serve_frontend and (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa(full_path: str):  # noqa: ANN202
            if full_path.startswith("api/"):
                return JSONResponse({"error": {"code": "not_found", "message": "Unknown API route"}}, status_code=404)
            f = (dist / full_path).resolve()
            if full_path and f.is_file() and dist.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
