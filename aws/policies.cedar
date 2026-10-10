// AWS Cedar Policy Specifications for AquiPulse Groundwater Intelligence
// Defines fine-grained authorization for DISCOM Grid Operators, Hydrologists, Panchayat Leaders, and Farmers.

// 1. DISCOM Grid Operators can monitor feeder load, roster power, and trigger emergency shutdown on acute cone stress
permit (
    principal in AquiPulse::Role::"DISCOM_Operator",
    action in [
        AquiPulse::Action::"ViewTelemetry",
        AquiPulse::Action::"RosterFeederPower",
        AquiPulse::Action::"TriggerEmergencyShutdown"
    ],
    resource is AquiPulse::Feeder
);

// 2. DISCOM Operators are strictly forbidden from modifying physical aquifer parameters (only certified hydrologists can)
forbid (
    principal in AquiPulse::Role::"DISCOM_Operator",
    action in [
        AquiPulse::Action::"ModifyAquiferBoundary",
        AquiPulse::Action::"OverrideHydraulicPermeability"
    ],
    resource is AquiPulse::Aquifer
);

// 3. State Groundwater Hydrologists can view 2D PDE mesh, calibrate boundaries, and run adjoint / ES-MDA solvers
permit (
    principal in AquiPulse::Role::"Hydrogeologist",
    action in [
        AquiPulse::Action::"ViewAquiferMesh",
        AquiPulse::Action::"ModifyAquiferBoundary",
        AquiPulse::Action::"RunAdjointSolve",
        AquiPulse::Action::"RunEsMdaAssimilation"
    ],
    resource is AquiPulse::Aquifer
);

// 4. Village Panchayat Council Leaders can view village-aggregated water balance and verified conservation ledger
permit (
    principal in AquiPulse::Role::"Panchayat_Leader",
    action in [
        AquiPulse::Action::"ViewVillageLedger",
        AquiPulse::Action::"VerifyCommunalBalance"
    ],
    resource is AquiPulse::Village
);

// 5. Farmers can view their own well state, claim earned hydraulic bonuses, and submit active learning bucket audits
permit (
    principal is AquiPulse::Farmer,
    action in [
        AquiPulse::Action::"ViewOwnWellState",
        AquiPulse::Action::"ClaimEarnedBonus",
        AquiPulse::Action::"SubmitBucketAudit"
    ],
    resource is AquiPulse::Pump
)
when {
    resource.owner == principal.id
};

// 6. Farmers are strictly forbidden from triggering feeder grid shutdowns or editing regional prices
forbid (
    principal is AquiPulse::Farmer,
    action in [
        AquiPulse::Action::"RosterFeederPower",
        AquiPulse::Action::"TriggerEmergencyShutdown",
        AquiPulse::Action::"EditExternalityPrice"
    ],
    resource
);
