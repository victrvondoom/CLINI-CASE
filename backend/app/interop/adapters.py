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
        if code == "dissolved_arsenic":
            return {
                "system": fhir.OAH_CODE_SYSTEM,
                "code": "arsenic-dissolved",
                "display": "Arsenic dissolved",
                "status": "OAH_VERIFIED_PREFERRED",
                "source": (
                    f"https://github.com/hl7-eu/oah/tree/{fhir.OAH_COMMIT}/input/fsh"
                ),
                "verification_time": None,
                "external_mapping_verified": True,
                "value_set": fhir.OAH_INDICATORS_VALUE_SET,
                "ig_version": "0.1.0-ci-build",
                "ig_commit": fhir.OAH_COMMIT,
            }
        if code in ("total_arsenic", "inorganic_arsenic"):
            return {
                "system": None,
                "code": None,
                "display": fhir.ANALYTE_LABELS[code],
                "status": "LOCAL_CONCEPT_ONLY",
                "source": "CLINI-CASE internal concept; no matching code verified in pinned OAH IG",
                "verification_time": None,
                "external_mapping_verified": False,
                "value_set": fhir.OAH_INDICATORS_VALUE_SET,
                "ig_version": "0.1.0-ci-build",
                "ig_commit": fhir.OAH_COMMIT,
            }
        return {
            "system": None,
            "code": None,
            "display": code.replace("_", " "),
            "status": "UNRESOLVED",
            "source": None,
            "verification_time": None,
            "external_mapping_verified": False,
        }
