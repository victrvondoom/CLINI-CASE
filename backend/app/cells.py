"""Cell-based architecture — blast-radius isolation for multi-tenant scale.

The single-Aurora-primary architecture peaks at ~50K cases/day. Beyond that,
"all tenants share one DB + one K8s namespace" makes a single bad query, a
single 0-day, or a single noisy tenant a global incident. **Cells** carve
the fleet into independent shards.

The cell pattern (well-known at AWS, Slack, Stripe):
  • A cell is a self-contained deployment unit:
    one Aurora cluster, one K8s namespace, one set of workers,
    one Bedrock IAM role.
  • Each tenant is pinned to ONE cell.
  • A cell's blast radius is bounded — at most N tenants are affected by any
    one cell's outage.
  • New cells are added horizontally as tenant count grows.
  • The router (this module) maps `organization_id → cell_id` consistently.

Today (round-11): cell 0 is the only deployed cell. The lookup table is hard-
coded; future versions will read from a `cells` table or AWS Cloud Map.
The runtime injects `X-ClinCase-Cell-Id` on every response so a customer's
SRE can correlate cross-cell traffic.

Pairs with: ops/architecture/CELL_BASED_ARCHITECTURE.md
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Cell:
    cell_id: str
    region: str
    aurora_cluster_arn: str
    k8s_namespace: str
    bedrock_iam_role_arn: str
    capacity_tenants: int     # soft cap


# ---------------------------------------------------------------------------
# Today's deployed cells. As the fleet grows, this becomes a DB table or
# AWS Cloud Map service registry.
# ---------------------------------------------------------------------------

_CELLS: dict[str, Cell] = {
    "cell-0-apac-1": Cell(
        cell_id="cell-0-apac-1",
        region="ap-south-1",
        aurora_cluster_arn="arn:aws:rds:ap-south-1:000000000000:cluster:clincase-cell0",
        k8s_namespace="clincase",
        bedrock_iam_role_arn="arn:aws:iam::000000000000:role/ClinCaseBedrockCell0",
        capacity_tenants=200,
    ),
    "cell-1-us-1": Cell(
        cell_id="cell-1-us-1",
        region="us-east-1",
        aurora_cluster_arn="arn:aws:rds:us-east-1:000000000000:cluster:clincase-cell1",
        k8s_namespace="clincase-cell1",
        bedrock_iam_role_arn="arn:aws:iam::000000000000:role/ClinCaseBedrockCell1",
        capacity_tenants=200,
    ),
    "cell-2-eu-1": Cell(
        cell_id="cell-2-eu-1",
        region="eu-west-1",
        aurora_cluster_arn="arn:aws:rds:eu-west-1:000000000000:cluster:clincase-cell2",
        k8s_namespace="clincase-cell2",
        bedrock_iam_role_arn="arn:aws:iam::000000000000:role/ClinCaseBedrockCell2",
        capacity_tenants=200,
    ),
}


# ---------------------------------------------------------------------------
# Tenant → cell pinning
# ---------------------------------------------------------------------------
# Today (round-11) the pinning is computed via stable hash of the org_id —
# the same algorithm AWS Identity uses for region pinning. When a tenant is
# onboarded with a specific data_region (per the residency module), they're
# pinned to a cell IN that region.
#
# Once `cells.tenant_to_cell` table lands, this function becomes a 1-row
# DB lookup and the explicit pin overrides hash-based selection.


def _hash_pin(organization_id: str, eligible: list[str]) -> str:
    """Stable consistent-hash pin: an org_id always lands on the same cell
    until cells are added/removed. We use SHA-256 truncated to 16 bytes."""
    digest = hashlib.sha256(organization_id.encode("utf-8")).digest()
    n = int.from_bytes(digest[:8], "big")
    return eligible[n % len(eligible)]


def cell_for_organization(*, organization_id: str, data_region: str | None = None) -> Cell:
    """Resolve the cell that owns this tenant's data + workers.

    Algorithm:
      1. If data_region is provided, restrict to cells in that region.
      2. Hash-pin the org_id across the eligible cells.
      3. If no cells in that region, fall back to all cells.
    """
    if data_region:
        eligible = [cid for cid, c in _CELLS.items() if c.region == data_region]
        if not eligible:
            eligible = list(_CELLS.keys())
    else:
        eligible = list(_CELLS.keys())
    pinned = _hash_pin(organization_id, eligible)
    return _CELLS[pinned]


def list_cells() -> list[Cell]:
    return list(_CELLS.values())


def get_cell(cell_id: str) -> Cell | None:
    return _CELLS.get(cell_id)


# ---------------------------------------------------------------------------
# Router-side helpers — used by middleware and /capabilities endpoint
# ---------------------------------------------------------------------------


def cell_snapshot() -> dict:
    """Snapshot for /capabilities + /architecture/layers."""
    return {
        "deployed_cells": [
            {
                "cell_id": c.cell_id,
                "region": c.region,
                "k8s_namespace": c.k8s_namespace,
                "capacity_tenants": c.capacity_tenants,
            }
            for c in _CELLS.values()
        ],
        "router_algorithm": "consistent-hash by organization_id, restricted by data_region",
        "blast_radius_max_tenants_per_cell": max(c.capacity_tenants for c in _CELLS.values()),
    }
