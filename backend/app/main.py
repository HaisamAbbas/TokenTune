import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.projects import router as projects_router

app = FastAPI(title="AI Cost Optimizer")

# The Next.js dashboard (Phase 6) fetches this API directly from the browser
# via TanStack Query, so it needs CORS - not just server-to-server access.
# Defaults cover local dev (`next dev` on 3000) and the dashboard's own
# docker-compose port mapping; override/extend via DASHBOARD_ORIGINS (a
# comma-separated list) for other deployments.
_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
_origins = [
    origin.strip()
    for origin in os.environ.get("DASHBOARD_ORIGINS", _default_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
