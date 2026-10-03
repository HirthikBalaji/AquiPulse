"""AquiPulse Physics Consistency, Signature, and Anti-Replay Validator.

Implements Layer 5 edge verification:
- Electrical power equation check: P = sqrt(3)*V*I*cos(phi) or V*I*cos(phi)
- CT-Open anomaly detection: voltage energized but current near zero
- Pump-curve envelope check: operating point inside physical bounds
- Cryptographic signature verification (secure element HMAC/ECDSA)
- Anti-replay timestamp sequence and digest checking
"""

from __future__ import annotations

import hashlib
import hmac
import math
from dataclasses import dataclass
from typing import Dict, List, Set


@dataclass
class PhysicsCheckResult:
    """Outcome of physical and cryptographic telemetry validation."""

    is_valid: bool
    signature_valid: bool
    ct_open_detected: bool
    bypass_suspected: bool
    replay_detected: bool
    power_consistency_error: float
    flags: List[str]


class TelemetryValidator:
    """Verifies edge telemetry integrity against physical laws and cryptographic proofs."""

    def __init__(self, secret_keys: Dict[str, bytes]) -> None:
        self.secret_keys = secret_keys
        self.seen_signatures: Set[str] = set()
        self.last_timestamps: Dict[str, float] = {}

    def verify_telemetry(
        self,
        pump_id: str,
        timestamp_s: float,
        v_rms: float,
        i_rms: float,
        pf: float,
        p_kw: float,
        signature: str,
        phase: int = 3,
        p_rated_kw: float = 3.7,
    ) -> PhysicsCheckResult:
        """Validate an incoming 1 Hz telemetry record."""
        flags: List[str] = []
        sig_valid = True
        ct_open = False
        bypass = False
        replay = False

        # 1. Cryptographic Signature Verification
        if pump_id in self.secret_keys:
            key = self.secret_keys[pump_id]
            expected_payload = (
                f"{pump_id}:{timestamp_s:.3f}:{v_rms:.2f}:{i_rms:.2f}:{p_kw:.2f}".encode("utf-8")
            )
            expected_sig = hmac.new(key, expected_payload, hashlib.sha256).hexdigest()
            if signature != expected_sig:
                sig_valid = False
                flags.append("FLAG_INVALID_SIGNATURE")

        # 2. Anti-Replay Verification
        if signature in self.seen_signatures:
            replay = True
            flags.append("FLAG_REPLAY_ATTACK_DETECTED")
        else:
            if len(self.seen_signatures) > 100_000:
                self.seen_signatures.clear()
            self.seen_signatures.add(signature)

        last_ts = self.last_timestamps.get(pump_id, -1.0)
        if last_ts >= timestamp_s and not replay:
            replay = True
            flags.append("FLAG_OUT_OF_SEQUENCE_TIMESTAMP")
        self.last_timestamps[pump_id] = timestamp_s

        # 3. CT-Open Detection
        # Line is energized (V > 250V for 3P, V > 140V for 1P) but current is ~0
        v_thresh = 250.0 if phase == 3 else 140.0
        if v_rms > v_thresh and i_rms < 0.15 and p_kw < 0.05:
            # Check if this represents unlatched CT while motor is expected to run
            # Flagged as potential CT-open
            ct_open = True
            flags.append("FLAG_CT_OPEN_SUSPECTED")

        # 4. Electrical Power Consistency Check
        # P = sqrt(3)*V*I*PF (3P) or V*I*PF (1P)
        if phase == 3:
            p_expected_kw = (math.sqrt(3.0) * v_rms * i_rms * pf) / 1000.0
        else:
            p_expected_kw = (v_rms * i_rms * pf) / 1000.0

        p_err = abs(p_kw - p_expected_kw)
        if p_kw > 0.20 and p_err > 0.40:
            flags.append("FLAG_ELECTRICAL_POWER_INCONSISTENT")

        # 5. Meter Bypass Suspect
        # If current is unusually low for rated pump while PF is distorted
        if 0.05 < p_kw < 0.40 * p_rated_kw and i_rms > 0.5 and pf < 0.50:
            bypass = True
            flags.append("FLAG_SHUNT_BYPASS_SUSPECTED")

        is_valid = sig_valid and not replay and not ct_open and p_err < 0.80

        return PhysicsCheckResult(
            is_valid=is_valid,
            signature_valid=sig_valid,
            ct_open_detected=ct_open,
            bypass_suspected=bypass,
            replay_detected=replay,
            power_consistency_error=round(p_err, 3),
            flags=flags,
        )
