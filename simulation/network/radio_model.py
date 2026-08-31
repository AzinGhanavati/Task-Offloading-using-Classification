from __future__ import annotations
import math
import random
from dataclasses import dataclass
from config.simulation_config import RadioConfig
from .energy_model import dbm_to_watt, eptask_transmission_energy_j, watt_to_dbm
from .path_loss import rato_path_loss_db, rato_traffic_noise_dbm

@dataclass(frozen=True, slots=True)
class WirelessLinkEstimate:
    valid: bool
    distance_m: float
    transmit_power_dbm: float
    transmit_power_w: float
    path_loss_db: float
    received_power_dbm: float
    snr_db: float
    snr_linear: float
    ber: float
    packet_loss_rate: float
    rate_bps: float

@dataclass(frozen=True, slots=True)
class WirelessTransmission:
    estimate: WirelessLinkEstimate
    success: bool
    attempts: int
    duration_s: float
    energy_j: float

class RadioModel:
    def __init__(self, config: RadioConfig, *, seed: int = 42) -> None:
        self.config = config
        self.rng = random.Random(seed)

    def distance_scaled_transmit_power_w(
        self, distance_m: float, coverage_radius_m: float
    ) -> float:
        max_w = dbm_to_watt(self.config.maximum_tx_power_dbm)
        min_w = dbm_to_watt(self.config.minimum_tx_power_dbm)
        fraction = min(1.0, max(0.0, distance_m / coverage_radius_m))
        return min(max_w, max(min_w, fraction * max_w))

    def estimate(
        self,
        *,
        distance_m: float,
        coverage_radius_m: float,
        interference_w: float = 0.0,
    ) -> WirelessLinkEstimate:
        if coverage_radius_m <= 0:
            raise ValueError("coverage radius must be positive")
            
        valid = distance_m <= coverage_radius_m
        tx_w = self.distance_scaled_transmit_power_w(distance_m, coverage_radius_m)
        tx_dbm = watt_to_dbm(tx_w)
        
        path_loss_db = rato_path_loss_db(
            distance_m,
            self.config.carrier_frequency_hz,
            environment=self.config.environment,
            noisy=self.config.noisy_environment,
            rain_attenuation_db=self.config.rain_attenuation_db,
        )
        
        received_dbm = (
            tx_dbm
            - path_loss_db
            + self.config.tx_antenna_gain_dbi
            + self.config.rx_antenna_gain_dbi
        )
        
        signal_w = dbm_to_watt(received_dbm)
        noise_dbm = rato_traffic_noise_dbm(
            self.config.traffic_level, self.config.noise_profile
        )
        
        noise_and_interference_w = dbm_to_watt(noise_dbm) + max(0.0, interference_w)
        snr_linear = signal_w / max(noise_and_interference_w, 1.0e-30)
        snr_db = 10.0 * math.log10(max(snr_linear, 1.0e-30))
        
        ber = 0.5 * math.erfc(math.sqrt(2.0 * snr_linear))
        if ber <= 0.0:
            plr = 0.0
        elif ber >= 1.0:
            plr = 1.0
        else:
            plr = -math.expm1(self.config.packet_size_bits * math.log1p(-ber))
            
        rate_bps = (
            self.config.bandwidth_share
            * self.config.bandwidth_hz
            * math.log2(1.0 + snr_linear)
            if valid
            else 0.0
        )
        
        return WirelessLinkEstimate(
            valid=valid,
            distance_m=float(distance_m),
            transmit_power_dbm=tx_dbm,
            transmit_power_w=tx_w,
            path_loss_db=path_loss_db,
            received_power_dbm=received_dbm,
            snr_db=snr_db,
            snr_linear=snr_linear,
            ber=ber,
            packet_loss_rate=min(1.0, max(0.0, plr)),
            rate_bps=rate_bps,
        )

    def transmit(
        self,
        *,
        data_size_bits: float,
        distance_m: float,
        coverage_radius_m: float,
        interference_w: float = 0.0,
    ) -> WirelessTransmission:
        estimate = self.estimate(
            distance_m=distance_m,
            coverage_radius_m=coverage_radius_m,
            interference_w=interference_w,
        )
        
        if not estimate.valid or estimate.rate_bps <= 0.0:
            return WirelessTransmission(estimate, False, 0, 0.0, 0.0)
            
        one_attempt_s = data_size_bits / estimate.rate_bps
        attempts = 0
        success = False
        total_duration_s = 0.0
        
        for attempt in range(self.config.max_retries + 1):
            attempts += 1
            total_duration_s += one_attempt_s
            if self.rng.random() >= estimate.packet_loss_rate:
                success = True
                break
            if attempt < self.config.max_retries:
                total_duration_s += self.config.retry_timeout_s
                
        tx_airtime_s = attempts * one_attempt_s
        energy_j = eptask_transmission_energy_j(
            transmit_power_w=estimate.transmit_power_w,
            duration_s=tx_airtime_s,
        )
        
        return WirelessTransmission(
            estimate=estimate,
            success=success,
            attempts=attempts,
            duration_s=total_duration_s,
            energy_j=energy_j,
        )