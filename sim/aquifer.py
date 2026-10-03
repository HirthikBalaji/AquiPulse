"""AquiPulse 2D Unconfined Groundwater Aquifer Simulator.

Implements:
- 2D heterogeneous log-K field via Gaussian Random Field (GRF) + discrete fracture channels
- Spatially variable specific yield S_y field
- Bedrock elevation b(x, y) and surface topography z_surf(x, y)
- Nonlinear transmissivity T(h) = K * max(0.1, h - b)
- Monsoon seasonal recharge R(x, y, t)
- Peaceman / Cooper-Jacob well-block near-well local drawdown correction
- High-precision 2D finite-volume flow solver (float64) with strict mass balance conservation
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np


@dataclass
class AquiferConfig:
    """Aquifer grid and hydrogeological parameters."""

    nx: int = 30  # Grid cells along X
    ny: int = 30  # Grid cells along Y
    dx: float = 200.0  # Cell size in meters (200m -> 6km x 6km basin)
    dy: float = 200.0  # Cell size in meters
    mean_log_k: float = (
        -4.5
    )  # Mean log10(K) in m/s (~3.16e-5 m/s, typical fractured granite/basalt)
    std_log_k: float = 0.6  # Heterogeneity standard deviation
    corr_len_x: float = 1200.0  # Spatial correlation length in meters
    corr_len_y: float = 1200.0
    mean_sy: float = 0.025  # Mean specific yield (2.5% for hard-rock Deccan/Peninsular)
    std_sy: float = 0.005
    bedrock_mean: float = 10.0  # Datum meters
    surface_mean: float = 110.0  # Surface topography meters
    initial_depth: float = 35.0  # Initial depth to water (m below surface)
    monsoon_annual_mm: float = 750.0  # Annual rainfall in mm
    recharge_factor: float = 0.12  # Fraction of rainfall that recharges aquifer (12%)
    num_fractures: int = 3  # High-transmissivity discrete fracture zones


class Aquifer2D:
    """2D heterogeneous unconfined aquifer with finite volume solver."""

    def __init__(self, config: AquiferConfig, rng: Optional[np.random.Generator] = None) -> None:
        self.config = config
        self.rng = rng if rng is not None else np.random.default_rng(42)

        self.nx = config.nx
        self.ny = config.ny
        self.dx = config.dx
        self.dy = config.dy
        self.cell_area = config.dx * config.dy

        # Coordinates
        self.x = (np.arange(self.nx) + 0.5) * self.dx
        self.y = (np.arange(self.ny) + 0.5) * self.dy
        self.X, self.Y = np.meshgrid(self.x, self.y)

        # Generate topography and bedrock
        self.z_surf = self._generate_topography()
        self.bedrock = self._generate_bedrock()

        # Generate heterogeneous fields
        self.log_k, self.k = self._generate_hydraulic_conductivity()
        self.sy = self._generate_specific_yield()

        # Initial water head (m above datum)
        self.h = np.maximum(self.bedrock + 5.0, self.z_surf - config.initial_depth).astype(
            np.float64
        )

        # Well-block equivalent radius for local drawdown (Peaceman 1983)
        # r_eq = 0.208 * dx for square cells
        self.r_eq = 0.208 * math.sqrt(self.dx * self.dy)
        self.default_rw = 0.10  # 10 cm borewell casing radius

        # Mass balance tracking (in m^3)
        self.total_recharge_vol = 0.0
        self.total_pumped_vol = 0.0
        self.total_boundary_flux_vol = 0.0
        self.initial_storage = float(np.sum(self.sy * (self.h - self.bedrock) * self.cell_area))

    def _generate_topography(self) -> np.ndarray:
        """Gentle regional topographic slope from NW to SE with local undulations."""
        # Regional gradient ~ 0.2% slope
        slope_x = -0.0015 * (self.X - self.X.mean())
        slope_y = -0.0010 * (self.Y - self.Y.mean())
        # Local undulations via smooth Gaussian field
        nx, ny = self.nx, self.ny
        kx = np.fft.fftfreq(nx, d=self.dx)
        ky = np.fft.fftfreq(ny, d=self.dy)
        KX, KY = np.meshgrid(kx, ky)
        k_rad = np.sqrt(KX**2 + KY**2)
        power_spectrum = np.exp(-0.5 * (k_rad * 1500.0) ** 2)
        white_noise = self.rng.standard_normal((ny, nx))
        noise_fft = np.fft.fft2(white_noise) * power_spectrum
        smooth_topo = np.real(np.fft.ifft2(noise_fft))
        smooth_topo = 4.0 * (smooth_topo / (np.std(smooth_topo) + 1e-6))
        return self.config.surface_mean + slope_x + slope_y + smooth_topo

    def _generate_bedrock(self) -> np.ndarray:
        """Weathered bedrock elevation profile."""
        return self.config.bedrock_mean + 0.05 * (self.z_surf - self.config.surface_mean)

    def _generate_hydraulic_conductivity(self) -> Tuple[np.ndarray, np.ndarray]:
        """Generate 2D log-Gaussian random field + discrete fracture lineaments."""
        nx, ny = self.nx, self.ny
        # 2D spectral Gaussian Random Field
        kx = np.fft.fftfreq(nx, d=self.dx)
        ky = np.fft.fftfreq(ny, d=self.dy)
        KX, KY = np.meshgrid(kx, ky)
        k_rad = np.sqrt((KX * self.config.corr_len_x) ** 2 + (KY * self.config.corr_len_y) ** 2)
        psd = (1.0 + k_rad**2) ** (-1.8)  # Matérn-like power law

        white_noise = self.rng.standard_normal((ny, nx))
        noise_fft = np.fft.fft2(white_noise) * np.sqrt(psd)
        grf = np.real(np.fft.ifft2(noise_fft))
        grf = (grf - np.mean(grf)) / (np.std(grf) + 1e-6)

        log_k = self.config.mean_log_k + self.config.std_log_k * grf

        # Add discrete fracture lineaments (10x to 30x permeability boost along lines)
        for _ in range(self.config.num_fractures):
            # Line defined by point (x0, y0) and angle theta
            x0 = self.rng.uniform(0.1 * self.nx * self.dx, 0.9 * self.nx * self.dx)
            y0 = self.rng.uniform(0.1 * self.ny * self.dy, 0.9 * self.ny * self.dy)
            theta = self.rng.uniform(0, math.pi)
            width = self.rng.uniform(150.0, 350.0)
            boost = self.rng.uniform(0.8, 1.4)  # in log10 space (~6x to 25x K)

            # Distance of each cell from the fracture line
            dist = np.abs((self.X - x0) * math.sin(theta) - (self.Y - y0) * math.cos(theta))
            fracture_mask = np.exp(-0.5 * (dist / width) ** 2)
            log_k += boost * fracture_mask

        # Clip log10(K) to realistic bounds [-6.5, -2.5] m/s
        log_k = np.clip(log_k, -6.5, -2.5)
        k = 10.0**log_k
        return log_k, k

    def _generate_specific_yield(self) -> np.ndarray:
        """Spatially varying specific yield Sy (0.01 to 0.05)."""
        nx, ny = self.nx, self.ny
        white_noise = self.rng.standard_normal((ny, nx))
        # Correlation with log-K: higher K weathering zones usually have slightly higher Sy
        sy = (
            self.config.mean_sy
            + 0.003 * (self.log_k - self.config.mean_log_k)
            + 0.002 * white_noise
        )
        return np.clip(sy, 0.008, 0.08)

    def get_transmissivity(self, h: Optional[np.ndarray] = None) -> np.ndarray:
        """Compute transmissivity field T = K * saturated_thickness."""
        if h is None:
            h = self.h
        saturated_thickness = np.maximum(0.2, h - self.bedrock)
        return self.k * saturated_thickness

    def get_seasonal_recharge_rate(self, day_of_year: float) -> np.ndarray:
        """Recharge rate in m/s as a function of season.

        Indian monsoon typically runs day 160 to 270 (June - September).
        Winter/summer recharge is negligible.
        """
        # Daily rainfall pattern
        if 160.0 <= day_of_year <= 270.0:
            # Monsoon window: bell curve peak around day 215 (early August)
            monsoon_frac = math.sin(math.pi * (day_of_year - 160.0) / 110.0) ** 2
            # Total annual monsoon recharge depth in meters
            total_recharge_depth = (
                self.config.monsoon_annual_mm / 1000.0
            ) * self.config.recharge_factor
            # Average daily recharge during monsoon
            daily_m = (total_recharge_depth / 55.0) * monsoon_frac
            rate_m_per_s = daily_m / 86400.0
        elif 280.0 <= day_of_year <= 310.0:
            # Post-monsoon light showers (NE monsoon in southern areas)
            daily_m = 0.0005 * math.sin(math.pi * (day_of_year - 280.0) / 30.0)
            rate_m_per_s = daily_m / 86400.0
        else:
            rate_m_per_s = 1e-10  # Near zero background recharge

        # Spatial recharge variation based on topography and soil
        spatial_recharge = rate_m_per_s * (
            1.0 + 0.15 * (self.z_surf - self.config.surface_mean) / 10.0
        )
        return np.maximum(0.0, spatial_recharge)

    def locate_cell(self, x_coord: float, y_coord: float) -> Tuple[int, int]:
        """Convert physical coordinates (meters) to grid indices (ix, iy)."""
        ix = int(np.clip(math.floor(x_coord / self.dx), 0, self.nx - 1))
        iy = int(np.clip(math.floor(y_coord / self.dy), 0, self.ny - 1))
        return ix, iy

    def step(
        self,
        dt_seconds: float,
        pumping_rates_m3_s: Dict[Tuple[int, int], float],
        day_of_year: float = 200.0,
    ) -> float:
        """Advance the 2D unconfined groundwater flow model by dt_seconds.

        Uses harmonic averaging for intercell transmissivities and an alternating
        direction or finite-volume flux divergence with adaptive sub-stepping
        for unconditional numerical stability and exact mass conservation.

        Returns maximum head change |dh| across domain.
        """
        # Sub-step if dt exceeds CFL diffusion limit: dt <= 0.5 * S_y * dx^2 / (4 * T_max)
        t_field = self.get_transmissivity()
        t_max = float(np.max(t_field))
        sy_min = float(np.min(self.sy))
        max_stable_dt = 0.45 * sy_min * (min(self.dx, self.dy) ** 2) / (4.0 * max(1e-5, t_max))
        n_substeps = max(1, int(math.ceil(dt_seconds / max(1.0, max_stable_dt))))
        sub_dt = dt_seconds / n_substeps

        recharge_rate = self.get_seasonal_recharge_rate(day_of_year)
        max_dh_total = 0.0

        for _ in range(n_substeps):
            h_curr = self.h
            t_curr = self.get_transmissivity(h_curr)

            # Harmonic mean transmissivities at cell faces
            # X-direction faces (size: ny, nx-1)
            t_east = (
                2.0
                * t_curr[:, :-1]
                * t_curr[:, 1:]
                / np.maximum(1e-12, t_curr[:, :-1] + t_curr[:, 1:])
            )
            flux_x = -t_east * (h_curr[:, 1:] - h_curr[:, :-1]) / self.dx  # m^2/s

            # Y-direction faces (size: ny-1, nx)
            t_north = (
                2.0
                * t_curr[:-1, :]
                * t_curr[1:, :]
                / np.maximum(1e-12, t_curr[:-1, :] + t_curr[1:, :])
            )
            flux_y = -t_north * (h_curr[1:, :] - h_curr[:-1, :]) / self.dy  # m^2/s

            # Net lateral flux divergence per cell: (Qin - Qout) / (dx*dy)
            div_flux = np.zeros_like(h_curr)
            # Internal cells X flux
            div_flux[:, 1:-1] += (flux_x[:, :-1] - flux_x[:, 1:]) / self.dx
            # Boundary cells X flux (No-flow boundary conditions at outer edge)
            div_flux[:, 0] += -flux_x[:, 0] / self.dx
            div_flux[:, -1] += flux_x[:, -1] / self.dx

            # Internal cells Y flux
            div_flux[1:-1, :] += (flux_y[:-1, :] - flux_y[1:, :]) / self.dy
            # Boundary cells Y flux (No-flow boundary)
            div_flux[0, :] += -flux_y[0, :] / self.dy
            div_flux[-1, :] += flux_y[-1, :] / self.dy

            # Source / sink terms: recharge and pumping
            q_source = recharge_rate.copy()  # m/s
            substep_pumped = 0.0

            for (ix, iy), q_m3_s in pumping_rates_m3_s.items():
                if 0 <= ix < self.nx and 0 <= iy < self.ny:
                    # Extraction reduces head
                    q_flux = q_m3_s / self.cell_area  # m/s
                    q_source[iy, ix] -= q_flux
                    substep_pumped += q_m3_s * sub_dt

            # dh = (div_flux + q_source) * dt / S_y
            dh = (div_flux + q_source) * (sub_dt / self.sy)
            self.h = self.h + dh
            max_dh_total = max(max_dh_total, float(np.max(np.abs(dh))))

            # Track mass balances
            substep_recharge = float(np.sum(recharge_rate * self.cell_area * sub_dt))
            self.total_recharge_vol += substep_recharge
            self.total_pumped_vol += substep_pumped

        return max_dh_total

    def compute_local_well_head(
        self,
        ix: int,
        iy: int,
        q_lps: float,
        well_radius_m: float = 0.10,
        c_turbulent_loss: float = 0.002,
    ) -> Tuple[float, float, float]:
        """Compute the dynamic head and static head at an active well inside grid cell (ix, iy).

        Accounting for:
        1. Cell-average regional water level: h_cell
        2. Peaceman local radial convergence drawdown:
           s_laminar = Q / (2 * pi * T) * ln(r_eq / r_w)
        3. Jacob turbulent well loss:
           s_turbulent = C * Q^2
        4. Static water depth Z_s = z_surf - h_cell
        5. Total dynamic lift: H_d = (z_surf - h_cell) + s_laminar + s_turbulent

        Returns (z_static_m, dynamic_drawdown_m, total_lift_m).
        """
        h_cell = float(self.h[iy, ix])
        z_surf_cell = float(self.z_surf[iy, ix])
        z_static_m = max(1.0, z_surf_cell - h_cell)

        if q_lps <= 0.0:
            return z_static_m, 0.0, z_static_m

        t_cell = float(self.get_transmissivity()[iy, ix])
        q_m3_s = q_lps / 1000.0

        # Peaceman log factor
        r_eq = self.r_eq
        rw = max(0.02, well_radius_m)
        log_ratio = max(0.5, math.log(r_eq / rw))

        s_laminar = (q_m3_s / (2.0 * math.pi * max(1e-6, t_cell))) * log_ratio
        s_turbulent = c_turbulent_loss * (q_lps**2)
        dynamic_drawdown = s_laminar + s_turbulent
        total_lift = z_static_m + dynamic_drawdown

        return z_static_m, dynamic_drawdown, total_lift

    def verify_mass_balance(self) -> Tuple[float, float, float]:
        """Check conservation of mass across simulation history.

        Returns (delta_storage_m3, net_inflow_m3, relative_error).
        """
        current_storage = float(np.sum(self.sy * (self.h - self.bedrock) * self.cell_area))
        delta_storage = current_storage - self.initial_storage
        net_inflow = self.total_recharge_vol - self.total_pumped_vol + self.total_boundary_flux_vol
        abs_err = abs(delta_storage - net_inflow)
        rel_err = abs_err / max(1.0, abs(delta_storage) + abs(net_inflow) + self.initial_storage)
        return delta_storage, net_inflow, rel_err
