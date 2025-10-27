# sim/models/energy.py
from dataclasses import dataclass

@dataclass
class EnergyStats:
    move_wh: float = 0.0
    tx_wh: float = 0.0
    comp_wh: float = 0.0
    idle_wh: float = 0.0

    @property
    def total(self) -> float:
        return self.move_wh + self.tx_wh + self.comp_wh + self.idle_wh

def propulsion_energy_wh(distance_m: float, k_propulsion_wh_per_m: float) -> float:
    return max(0.0, distance_m) * max(0.0, k_propulsion_wh_per_m)

def tx_energy_wh(megabytes: float, k_tx_wh_per_mb: float) -> float:
    return max(0.0, megabytes) * max(0.0, k_tx_wh_per_mb)

def comp_energy_wh(cycles: float, efficiency_cycles_per_wh: float) -> float:
    if efficiency_cycles_per_wh <= 0:
        return 0.0
    return max(0.0, cycles) / efficiency_cycles_per_wh

def idle_energy_wh(power_w: float, duration_s: float) -> float:
    # Wh = W * s / 3600
    return max(0.0, power_w) * max(0.0, duration_s) / 3600.0
