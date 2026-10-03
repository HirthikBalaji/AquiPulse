"""AquiPulse Immutable Settlement Ledger.

Append-only, cryptographically hashed ledger storing verified extraction reductions,
externality valuations, and DISCOM/carbon-credit payout settlements.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import List, Optional


@dataclass
class SettlementEntry:
    """A verified financial settlement record."""

    entry_id: str
    pump_id: str
    farmer_id: str
    period: str
    avoided_m3: float
    unit_price_inr: float
    bonus_inr: float
    guardrail_ok: bool
    flags: List[str]
    timestamp: float


@dataclass
class LedgerBlock:
    """Block in the append-only settlement chain."""

    block_index: int
    timestamp: float
    entries: List[SettlementEntry]
    prev_hash: str
    block_hash: str


class SettlementLedger:
    """Tamper-evident settlement ledger for DISCOMs, carbon buyers, and water authorities."""

    def __init__(self) -> None:
        self.chain: List[LedgerBlock] = []
        self._pending_entries: List[SettlementEntry] = []
        # Create Genesis Block
        self._create_genesis_block()

    def _create_genesis_block(self) -> None:
        genesis = LedgerBlock(
            block_index=0,
            timestamp=1700000000.0,
            entries=[],
            prev_hash="0" * 64,
            block_hash="GENESIS_AQUIPULSE_SETTLEMENT_LEDGER_V1",
        )
        self.chain.append(genesis)

    def add_entry(self, entry: SettlementEntry) -> None:
        """Add an entry to the pending settlement pool."""
        self._pending_entries.append(entry)

    def commit_block(self) -> Optional[LedgerBlock]:
        """Commit pending entries into a cryptographically signed immutable block."""
        if not self._pending_entries:
            return None

        prev_block = self.chain[-1]
        now = time.time()
        idx = len(self.chain)

        # Hash payload
        payload_dict = {
            "index": idx,
            "timestamp": now,
            "prev_hash": prev_block.block_hash,
            "entries": [asdict(e) for e in self._pending_entries],
        }
        payload_bytes = json.dumps(payload_dict, sort_keys=True).encode("utf-8")
        block_hash = hashlib.sha256(payload_bytes).hexdigest()

        block = LedgerBlock(
            block_index=idx,
            timestamp=now,
            entries=list(self._pending_entries),
            prev_hash=prev_block.block_hash,
            block_hash=block_hash,
        )

        self.chain.append(block)
        self._pending_entries.clear()
        return block

    def verify_integrity(self) -> bool:
        """Verify the full cryptographic integrity of the ledger chain."""
        if len(self.chain) <= 1:
            return True

        for i in range(1, len(self.chain)):
            curr = self.chain[i]
            prev = self.chain[i - 1]

            if curr.prev_hash != prev.block_hash:
                return False

            payload_dict = {
                "index": curr.block_index,
                "timestamp": curr.timestamp,
                "prev_hash": curr.prev_hash,
                "entries": [asdict(e) for e in curr.entries],
            }
            recomputed = hashlib.sha256(
                json.dumps(payload_dict, sort_keys=True).encode("utf-8")
            ).hexdigest()
            if recomputed != curr.block_hash:
                return False

        return True
