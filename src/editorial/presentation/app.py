"""
FastAPI composition root for the editorial service — "Archivo Desclasificado".

Kept minimal in Phase 1 (just the health route). Later phases register
routers here (approval gate in Phase 3, research trigger in Phase 4,
publish records in Phase 5, cases in Phase 6) without touching this module's
existing routes.
"""
from fastapi import FastAPI

from src.editorial.presentation.routers.approval import router as approval_router
from src.editorial.presentation.routers.research import router as research_router

app = FastAPI(title="Archivo Desclasificado — Editorial Service")
app.include_router(approval_router)
app.include_router(research_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
