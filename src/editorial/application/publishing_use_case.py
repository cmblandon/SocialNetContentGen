"""
PublishingUseCase — per specs/publishing/spec.md. Publishes an approved
PlatformVersion at its calendar-defined optimal time, or proposes one and
holds rather than publishing immediately when none is defined. Records
every outcome (success or failure) as a PublishRecord and in
calendario.md. Never retries automatically: publish() makes exactly one
attempt per call, and a failure leaves the PlatformVersion in a state
(FAILED) that approval_gate.run_if_approved will refuse to act on again
without a fresh, explicit approval.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.editorial.application.approval_gate import run_if_approved
from src.editorial.core.ports import ISocialPublisher
from src.editorial.infrastructure.persistence.models import (
    ApprovalStatus,
    PlatformName,
    PlatformVersion,
    PublishRecord,
)
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore

DEFAULT_PROPOSED_TIME = "12:00"


@dataclass
class PublishOutcome:
    published: bool
    external_post_id: Optional[str] = None
    error_message: Optional[str] = None
    proposed_time: Optional[str] = None


class PublishingUseCase:
    def __init__(self, publisher: ISocialPublisher, memory_store: ProjectMemoryStore):
        self._publisher = publisher
        self._memory_store = memory_store

    def publish(self, session: Session, platform_version_id: str) -> PublishOutcome:
        def _do_publish(platform_version: PlatformVersion) -> PublishOutcome:
            time_of_day = self._resolve_optimal_time_of_day(platform_version.platform)
            if time_of_day is None:
                return self._propose_time(platform_version)
            return self._publish_now(session, platform_version, time_of_day)

        return run_if_approved(session, platform_version_id, action=_do_publish)

    def _resolve_optimal_time_of_day(self, platform: PlatformName) -> Optional[str]:
        marker = f"optimal_time:{platform.value}="
        for line in self._memory_store.read_calendario().splitlines():
            stripped = line.strip()
            if stripped.startswith(marker):
                return stripped[len(marker):].strip()
        return None

    def _propose_time(self, platform_version: PlatformVersion) -> PublishOutcome:
        self._memory_store.append_calendario_entry(
            f"{date.today().isoformat()} | PROPOSED optimal_time:"
            f"{platform_version.platform.value}={DEFAULT_PROPOSED_TIME} | pending approval"
        )
        return PublishOutcome(published=False, proposed_time=DEFAULT_PROPOSED_TIME)

    def _publish_now(
        self, session: Session, platform_version: PlatformVersion, time_of_day: str
    ) -> PublishOutcome:
        scheduled_at = datetime.combine(
            date.today(), time.fromisoformat(time_of_day), tzinfo=timezone.utc
        )

        result = self._publisher.publish(
            platform=platform_version.platform.value,
            content=platform_version.content,
            scheduled_at=scheduled_at,
        )

        status = ApprovalStatus.PUBLISHED if result.success else ApprovalStatus.FAILED
        record = PublishRecord(
            platform_version=platform_version,
            scheduled_at=scheduled_at,
            published_at=datetime.now(timezone.utc) if result.success else None,
            external_post_id=result.external_post_id,
            status=status,
            error_message=result.error_message,
        )
        session.add(record)
        platform_version.status = status
        session.commit()

        self._memory_store.append_calendario_entry(
            f"{scheduled_at.isoformat()} | {platform_version.platform.value} | "
            f"chapter {platform_version.chapter_id} | post_id "
            f"{result.external_post_id or 'N/A'} | status {status.value}"
        )

        return PublishOutcome(
            published=result.success,
            external_post_id=result.external_post_id,
            error_message=result.error_message,
        )
