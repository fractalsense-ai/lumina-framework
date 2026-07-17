"""Provider-neutral contracts for scoped institutional retrieval."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalFilter:
    """Hard and optional metadata filters applied before vector scoring."""

    organization_id: str | None = None
    site_id: str | None = None
    actor_id: str | None = None
    device_id: str | None = None
    module_key: str | None = None
    provider: str | None = None
    external_record_type: str | None = None
    external_record_id: str | None = None
    institutional_only: bool = False

    def validate(self) -> None:
        """Reject incomplete filters for institutional-memory searches."""
        if self.institutional_only and not self.organization_id:
            raise ValueError("institutional retrieval requires organization_id")
        if self.institutional_only and not self.site_id:
            raise ValueError("institutional retrieval requires site_id")

    def as_metadata(self) -> dict[str, str | None]:
        """Return the chunk metadata keys controlled by this filter."""
        return {
            "organization_id": self.organization_id,
            "site_id": self.site_id,
            "actor_id": self.actor_id,
            "device_id": self.device_id,
            "module_key": self.module_key,
            "provider": self.provider,
            "external_record_type": self.external_record_type,
            "external_record_id": self.external_record_id,
        }
