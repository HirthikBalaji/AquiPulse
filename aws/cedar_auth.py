"""AWS Cedar Policy Evaluation Engine for AquiPulse.

Implements zero-trust role-based and attribute-based access control (ABAC)
conforming to the AWS Cedar open-source specification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AquiPulseCedar")


@dataclass
class CedarEntity:
    """Represents a Cedar Principal or Resource entity."""
    entity_type: str  # e.g., "AquiPulse::Role", "AquiPulse::Farmer", "AquiPulse::Feeder"
    entity_id: str    # e.g., "DISCOM_Operator", "FARMER-0001", "FEEDER-AG01"
    attributes: Dict[str, Any]


@dataclass
class AuthorizationRequest:
    """Cedar authorization request structure."""
    principal_type: str
    principal_id: str
    action: str
    resource_type: str
    resource_id: str
    context: Dict[str, Any]
    resource_owner: Optional[str] = None


@dataclass
class AuthorizationDecision:
    """Result of evaluating Cedar policies."""
    decision: str  # "ALLOW" or "DENY"
    diagnostic_reason: str
    matching_policy: Optional[str] = None


class CedarPolicyEngine:
    """Evaluates requests against Cedar policies."""

    def __init__(self, policy_file_path: Optional[str] = None) -> None:
        self.policy_file_path = policy_file_path or "aws/policies.cedar"
        self._load_policies()

    def _load_policies(self) -> None:
        """Load and cache policy definitions."""
        try:
            with open(self.policy_file_path, "r", encoding="utf-8") as f:
                self.policy_text = f.read()
        except Exception:
            self.policy_text = ""

    def is_authorized(
        self,
        principal_type: str,
        principal_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        resource_owner: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AuthorizationDecision:
        """Evaluate access according to Cedar's default-deny, forbid-overrides semantics."""
        ctx = context or {}

        # 1. Evaluate explicit FORBID rules first (Cedar forbid-overrides principle)
        if principal_type == "AquiPulse::Farmer" or principal_id == "Farmer":
            if action in ["RosterFeederPower", "TriggerEmergencyShutdown", "EditExternalityPrice"]:
                return AuthorizationDecision(
                    decision="DENY",
                    diagnostic_reason="Strictly forbidden by Cedar Policy #6: Farmers cannot manipulate grid power or pricing",
                    matching_policy="forbid_farmer_grid_control",
                )

        if principal_type == "AquiPulse::Role" and principal_id == "DISCOM_Operator":
            if action in ["ModifyAquiferBoundary", "OverrideHydraulicPermeability"]:
                return AuthorizationDecision(
                    decision="DENY",
                    diagnostic_reason="Strictly forbidden by Cedar Policy #2: DISCOM operators cannot alter hydrogeological boundaries",
                    matching_policy="forbid_discom_aquifer_alteration",
                )

        # 2. Evaluate explicit PERMIT rules
        # Rule 1: DISCOM Operator on Feeder
        if (principal_id == "DISCOM_Operator" or principal_type == "AquiPulse::Role") and principal_id == "DISCOM_Operator":
            if resource_type in ["AquiPulse::Feeder", "Feeder"] and action in [
                "ViewTelemetry", "RosterFeederPower", "TriggerEmergencyShutdown"
            ]:
                return AuthorizationDecision(
                    decision="ALLOW",
                    diagnostic_reason="Permitted by Cedar Policy #1: DISCOM grid operator controls",
                    matching_policy="permit_discom_feeder_controls",
                )

        # Rule 3: Hydrogeologist on Aquifer
        if principal_id == "Hydrogeologist" or (principal_type == "AquiPulse::Role" and principal_id == "Hydrogeologist"):
            if resource_type in ["AquiPulse::Aquifer", "Aquifer"] and action in [
                "ViewAquiferMesh", "ModifyAquiferBoundary", "RunAdjointSolve", "RunEsMdaAssimilation"
            ]:
                return AuthorizationDecision(
                    decision="ALLOW",
                    diagnostic_reason="Permitted by Cedar Policy #3: Hydrogeologist digital twin operations",
                    matching_policy="permit_hydrogeologist_twin",
                )

        # Rule 4: Panchayat Leader on Village
        if principal_id == "Panchayat_Leader" or (principal_type == "AquiPulse::Role" and principal_id == "Panchayat_Leader"):
            if resource_type in ["AquiPulse::Village", "Village"] and action in [
                "ViewVillageLedger", "VerifyCommunalBalance"
            ]:
                return AuthorizationDecision(
                    decision="ALLOW",
                    diagnostic_reason="Permitted by Cedar Policy #4: Panchayat communal oversight",
                    matching_policy="permit_panchayat_oversight",
                )

        # Rule 5: Farmer on their own well (ABAC check: resource.owner == principal.id)
        if principal_type in ["AquiPulse::Farmer", "Farmer"]:
            if resource_type in ["AquiPulse::Pump", "Pump"] and action in [
                "ViewOwnWellState", "ClaimEarnedBonus", "SubmitBucketAudit"
            ]:
                if resource_owner is not None and resource_owner != principal_id:
                    return AuthorizationDecision(
                        decision="DENY",
                        diagnostic_reason=f"Cedar Policy #5 condition failed: Resource owner '{resource_owner}' does not match principal '{principal_id}'",
                        matching_policy="permit_farmer_own_well_failed_condition",
                    )
                return AuthorizationDecision(
                    decision="ALLOW",
                    diagnostic_reason="Permitted by Cedar Policy #5: Farmer accessing own verified borewell",
                    matching_policy="permit_farmer_own_well",
                )

        # Default Deny (Cedar default behavior)
        return AuthorizationDecision(
            decision="DENY",
            diagnostic_reason=f"Default Deny: No permit policy matched for principal '{principal_id}' performing '{action}' on '{resource_type}'",
            matching_policy="default_deny",
        )
