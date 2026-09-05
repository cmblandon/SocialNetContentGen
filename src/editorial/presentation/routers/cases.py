"""
GET /cases, PATCH /cases/{id} — the content-admin-panel Covered Cases
view's backend (specs/content-admin-panel/spec.md: "search, browse, and
manually edit the covered-cases history").
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.editorial.application.cases_use_case import CasesUseCase, CaseNotFoundError
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore
from src.editorial.presentation.dependencies import get_memory_store

router = APIRouter(tags=["cases"])


class CaseResponse(BaseModel):
    id: str
    date: str
    identifier: str
    outcome: str
    reason: str


class UpdateCaseRequest(BaseModel):
    reason: str


def get_cases_use_case(
    memory_store: ProjectMemoryStore = Depends(get_memory_store),
) -> CasesUseCase:
    return CasesUseCase(memory_store=memory_store)


@router.get("/cases", response_model=list[CaseResponse])
def list_cases(
    q: Optional[str] = None,
    cases_use_case: CasesUseCase = Depends(get_cases_use_case),
) -> list[CaseResponse]:
    cases = cases_use_case.search_cases(q) if q else cases_use_case.list_cases()
    return [CaseResponse(**case.__dict__) for case in cases]


@router.patch("/cases/{case_id}", response_model=CaseResponse)
def update_case(
    case_id: str,
    request: UpdateCaseRequest,
    cases_use_case: CasesUseCase = Depends(get_cases_use_case),
) -> CaseResponse:
    try:
        updated = cases_use_case.update_case_reason(case_id, request.reason)
    except CaseNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return CaseResponse(**updated.__dict__)
