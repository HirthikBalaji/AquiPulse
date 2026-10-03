"""AquiPulse Farmer Behavior, Crop Irrigation Demand, and Solar VFD Models.

Simulates:
- Crop calendars (Kharif, Rabi, Summer) with daily crop water demand (ET_c)
- Soil moisture deficit and irrigation switching decisions
- Grid pump operation constrained by DISCOM supply rosters
- Solar pump operation with natural daytime solar VFD frequency sweeps (30 - 50 Hz)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Literal, Optional, Tuple

import numpy as np


@dataclass
class CropProfile:
    """Agronomic parameters for crop water demand."""

    crop_name: str
    season: Literal["kharif", "rabi", "summer"]
    sowing_day: int
    harvest_day: int
    kc_init: float
    kc_mid: float
    kc_late: float
    depletion_trigger_mm: float  # mm of soil moisture deficit triggering irrigation
    target_irrigation_mm: float  # mm applied per irrigation event


# Standard crops in Indian semi-arid groundwater-dependent regions
CROP_CATALOG: Dict[str, CropProfile] = {
    "cotton": CropProfile("cotton", "kharif", 165, 300, 0.45, 1.15, 0.65, 35.0, 50.0),
    "paddy": CropProfile("paddy", "kharif", 170, 290, 1.05, 1.30, 0.95, 20.0, 60.0),
    "soybean": CropProfile("soybean", "kharif", 175, 275, 0.40, 1.05, 0.50, 30.0, 45.0),
    "wheat": CropProfile("wheat", "rabi", 315, 80, 0.40, 1.15, 0.45, 40.0, 55.0),
    "mustard": CropProfile("mustard", "rabi", 305, 65, 0.35, 1.00, 0.40, 35.0, 45.0),
    "gram": CropProfile("gram", "rabi", 310, 75, 0.35, 0.95, 0.35, 30.0, 40.0),
    "summer_vegetables": CropProfile(
        "summer_vegetables", "summer", 85, 155, 0.50, 1.05, 0.70, 25.0, 35.0
    ),
}


class FarmerAgent:
    """Simulates farmer irrigation decisions for a single well and parcel."""

    def __init__(
        self,
        farmer_id: str,
        pump_id: str,
        crop: CropProfile,
        parcel_area_ha: float = 2.0,
        is_solar: bool = False,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        self.farmer_id = farmer_id
        self.pump_id = pump_id
        self.crop = crop
        self.parcel_area_ha = parcel_area_ha
        self.parcel_area_m2 = parcel_area_ha * 10_000.0
        self.is_solar = is_solar
        self.rng = rng if rng is not None else np.random.default_rng(202)

        # Soil moisture balance state
        self.soil_deficit_mm = float(self.rng.uniform(10.0, crop.depletion_trigger_mm * 0.8))
        self.pump_is_on = False
        self.current_event_seconds = 0.0
        self.target_event_duration_s = 4.0 * 3600.0  # 4 hours default

    def get_crop_coefficient_kc(self, day_of_year: float) -> float:
        """Calculate FAO-56 dual crop coefficient Kc on the given day."""
        sow = self.crop.sowing_day
        harvest = self.crop.harvest_day

        # Check if in season (handling year wrap-around for Rabi)
        if sow < harvest:
            in_season = sow <= day_of_year <= harvest
            rel_day = float(day_of_year - sow)
            total_days = float(harvest - sow)
        else:
            in_season = (day_of_year >= sow) or (day_of_year <= harvest)
            rel_day = float((day_of_year - sow) if day_of_year >= sow else (day_of_year + 365.0 - sow))
            total_days = float(harvest + 365.0 - sow)

        if not in_season or total_days <= 0:
            return 0.15  # Bare soil evaporation

        frac = rel_day / total_days
        if frac < 0.20:
            return self.crop.kc_init
        elif frac < 0.65:
            return self.crop.kc_mid
        else:
            return self.crop.kc_late

    def get_solar_irradiance(self, time_seconds: float) -> float:
        """Compute solar irradiance (W/m^2) with diurnal curve and intermittent clouds."""
        hour = (time_seconds / 3600.0) % 24.0
        sunrise = 6.0
        sunset = 18.2

        if hour < sunrise or hour > sunset:
            return 0.0

        # Clear sky bell curve, peak 980 W/m^2 around 12:00
        solar_zenith_fraction = math.sin(math.pi * (hour - sunrise) / (sunset - sunrise))
        g_clear = 980.0 * (solar_zenith_fraction**1.1)

        # Cloud transient factor (occasional cloud passing)
        cloud_factor = 1.0
        if 10.0 <= hour <= 15.0:
            cloud_noise = math.sin(time_seconds / 900.0) * math.cos(time_seconds / 250.0)
            if cloud_noise > 0.6:
                cloud_factor = 0.45 + 0.35 * (1.0 - cloud_noise)

        return float(max(0.0, g_clear * cloud_factor))

    def get_solar_vfd_frequency(self, solar_g: float) -> float:
        """Compute solar VFD drive output frequency (Hz).

        Sweeps continuously from 30 Hz at G=250 W/m^2 to 50 Hz at G=800+ W/m^2.
        """
        if solar_g < 180.0:
            return 0.0  # Drive shuts off below minimum DC bus threshold

        freq = 30.0 + 20.0 * ((solar_g - 180.0) / (850.0 - 180.0))
        return float(np.clip(freq, 28.0, 52.0))

    def update_irrigation_decision(
        self,
        dt_seconds: float,
        time_seconds: float,
        power_available: bool,
        rainfall_mm_hr: float = 0.0,
    ) -> Tuple[bool, float]:
        """Update farmer's irrigation decision and return (pump_should_run, vfd_frequency).

        Returns:
            pump_should_run: bool
            operating_frequency_hz: float (50 Hz for grid, dynamic for solar)
        """
        day_of_year = (time_seconds / 86400.0) % 365.0
        kc = self.get_crop_coefficient_kc(day_of_year)
        # Reference ET0: ~4.5 mm/day = 4.5 / 86400 mm/s
        et0_mm_s = 4.8 / 86400.0
        etc_mm = kc * et0_mm_s * dt_seconds

        # Daily water balance on the parcel
        rain_mm = (rainfall_mm_hr / 3600.0) * dt_seconds
        self.soil_deficit_mm += etc_mm - rain_mm
        self.soil_deficit_mm = max(0.0, self.soil_deficit_mm)

        if self.is_solar:
            # Solar pump operation
            solar_g = self.get_solar_irradiance(time_seconds)
            vfd_freq = self.get_solar_vfd_frequency(solar_g)

            # Solar pumps run automatically when sunlight is adequate and irrigation is beneficial
            if vfd_freq >= 30.0 and self.soil_deficit_mm > 8.0:
                self.pump_is_on = True
                self.current_event_seconds += dt_seconds
                return True, vfd_freq
            else:
                self.pump_is_on = False
                self.current_event_seconds = 0.0
                return False, 0.0
        else:
            # Grid pump operation
            if not power_available:
                self.pump_is_on = False
                self.current_event_seconds = 0.0
                return False, 0.0

            if self.pump_is_on:
                self.current_event_seconds += dt_seconds
                # Check if irrigation cycle is complete
                if (
                    self.current_event_seconds >= self.target_event_duration_s
                    or self.soil_deficit_mm <= 5.0
                ):
                    self.pump_is_on = False
                    self.current_event_seconds = 0.0
                    return False, 0.0
                return True, 50.0
            else:
                # Decide whether to turn ON
                if self.soil_deficit_mm >= self.crop.depletion_trigger_mm:
                    self.pump_is_on = True
                    self.current_event_seconds = 0.0
                    # Set target duration: 3 to 6 hours
                    self.target_event_duration_s = float(self.rng.uniform(3.0, 5.5)) * 3600.0
                    return True, 50.0

            return False, 0.0
