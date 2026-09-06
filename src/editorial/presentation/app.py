"""
FastAPI composition root for the editorial service — "Archivo Desclasificado".

Kept minimal in Phase 1 (just the health route). Later phases register
routers here (approval gate in Phase 3, research trigger in Phase 4,
publish records in Phase 5, cases in Phase 6) without touching this module's
existing routes.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.editorial.presentation.routers.approval import router as approval_router
from src.editorial.presentation.routers.cases import router as cases_router
from src.editorial.presentation.routers.pending_chapters import (
    router as pending_chapters_router,
)
from src.editorial.presentation.routers.publish_records import (
    router as publish_records_router,
)
from src.editorial.presentation.routers.research import router as research_router
from src.editorial.presentation.routers.script_approval import (
    router as script_approval_router,
)
from src.editorial.presentation.routers.subtitles import router as subtitles_router

app = FastAPI(title="Archivo Desclasificado — Editorial Service")

# The admin panel (Phase 6) runs on a different origin/port (Next.js dev
# server, typically localhost:3000) and calls this API directly from the
# browser — without CORS, every request from it fails.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(approval_router)
app.include_router(research_router)
app.include_router(publish_records_router)
app.include_router(pending_chapters_router)
app.include_router(cases_router)
app.include_router(script_approval_router)
app.include_router(subtitles_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
