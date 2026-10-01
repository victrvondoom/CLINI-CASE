"""Narrow adapter contracts; existing governed services remain the implementation."""

from typing import Any, Protocol

from app.interop import adapter, service
from app.interop.models import Job
from app.onehealth import fhir
from app.onehealth.models import ExposureRecord


class SourceAdapter(Protocol):
    def discover(self, job: Job) -> None: ...


class ReceiverAdapter(Protocol):
    async def send(self, org: str, correlation: str, bundle: dict[str, Any]) -> dict[str, Any]: ...


class FHIRAdapter(Protocol):
    def generate(self, record: ExposureRecord) -> dict[str, Any]: ...


class TerminologyAdapter(Protocol):
    def resolve(self, code: str) -> dict[str, Any]: ...


class SyntheticLabAdapter:
    """JSON/CSV parsing; a synthetic label is enforced by the calling contract."""

    def discover(self, job: Job) -> None:
        service.discover(job)


class SyntheticClinicalReceiver:
    async def send(self, org: str, correlation: str, bundle: dict[str, Any]) -> dict[str, Any]:
        return await adapter.exchange(org, correlation, bundle)


class OAHFHIRAdapter:
    def generate(self, record: ExposureRecord) -> dict[str, Any]:
        return fhir.export(record)


class LocalArsenicTerminology:
    def resolve(self, code: str) -> dict[str, Any]:
        supported = code in {"total_arsenic", "inorganic_arsenic"}
        return {
            "system": fhir.SYSTEM if supported else None,
            "code": code,
            "display": code.replace("_", " "),
            "status": "LOCAL_CODE" if supported else "UNRESOLVED",
            "source": fhir.SYSTEM if supported else None,
            "verification_time": None,
            "external_mapping_verified": False,
        }
