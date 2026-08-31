from __future__ import annotations
import math
from dataclasses import dataclass
from config.simulation_config import WiredConfig

@dataclass(frozen=True, slots=True)
class WiredTransfer:
    source_id: str
    destination_id: str
    requested_at: float
    started_at: float
    finishes_at: float
    queue_wait_s: float
    transmission_time_s: float
    propagation_delay_s: float
    rate_bps: float
    energy_j: float

class FullMeshWiredNetwork:
    def __init__(self, config: WiredConfig) -> None:
        self.config = config
        self._available_at: dict[tuple[str, str], float] = {}

    @property
    def rate_bps(self) -> float:
        snr_linear = 10.0 ** (self.config.snr_db / 10.0)
        return self.config.average_bandwidth_hz * math.log2(1.0 + snr_linear)

    def estimate_duration_s(self, data_size_bits: float) -> float:
        return data_size_bits / self.rate_bps + self.config.propagation_delay_s

    def reserve(
        self,
        *,
        source_id: str,
        destination_id: str,
        data_size_bits: float,
        now: float,
    ) -> WiredTransfer:
        if source_id == destination_id:
            raise ValueError("wired link endpoints must be different")
            
        key = (source_id, destination_id)
        started_at = max(now, self._available_at.get(key, now))
        transmission_time_s = data_size_bits / self.rate_bps
        finishes_at = started_at + transmission_time_s + self.config.propagation_delay_s
        self._available_at[key] = finishes_at
        
        return WiredTransfer(
            source_id=source_id,
            destination_id=destination_id,
            requested_at=now,
            started_at=started_at,
            finishes_at=finishes_at,
            queue_wait_s=started_at - now,
            transmission_time_s=transmission_time_s,
            propagation_delay_s=self.config.propagation_delay_s,
            rate_bps=self.rate_bps,
            energy_j=data_size_bits * self.config.energy_per_bit_j,
        )