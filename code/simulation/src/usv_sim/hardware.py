"""Assumption-based projection of predictor workload onto candidate USV processors.

This is a sensitivity model, not a measurement. Clock and memory figures are nominal
datasheet values; cycles per counted operation and power are stated ranges that the
authors must check before quoting. Projected energy is time multiplied by nominal
active power and is reported only to compare orders of magnitude between predictors.
It is not vessel energy, battery life, or a measured joule value.
"""
from __future__ import annotations

PROFILES = [
    {"id": "m4f", "name": "Cortex-M4F MCU (STM32F407 class)", "clock_hz": 168e6, "ram_bytes": 192*1024,
     "binary64_cycles": (20, 100), "transcendental_cycles": (200, 1000), "compare_cycles": (1, 2),
     "active_power_w": (0.10, 0.15),
     "basis": "ST STM32F407 datasheet: 168 MHz, 192 KiB SRAM, single-precision FPU only, so binary64 "
              "is software-emulated (assumed 20-100 cycles/op). Power: assumed run-mode range."},
    {"id": "m7", "name": "Cortex-M7 MCU (STM32H743 class)", "clock_hz": 480e6, "ram_bytes": 1024*1024,
     "binary64_cycles": (1, 4), "transcendental_cycles": (40, 150), "compare_cycles": (1, 2),
     "active_power_w": (0.2, 0.5),
     "basis": "ST STM32H743 datasheet: 480 MHz, about 1 MiB RAM, double-precision FPU. "
              "Cycle and power ranges are assumptions."},
    {"id": "a72", "name": "Raspberry Pi 4 (Cortex-A72, 1.5 GHz)", "clock_hz": 1.5e9, "ram_bytes": 4*1024**3,
     "binary64_cycles": (0.5, 2), "transcendental_cycles": (20, 80), "compare_cycles": (0.5, 1),
     "active_power_w": (3.4, 3.4),
     "basis": "Board power 3.4 W reported by Niu, Tarapore and Zauner (arXiv:2012.02907) for a Pi 4 workload; "
              "scalar cycle ranges are assumptions."},
    {"id": "nano", "name": "Jetson Nano CPU (Cortex-A57, 10 W mode)", "clock_hz": 1.43e9, "ram_bytes": 4*1024**3,
     "binary64_cycles": (0.5, 2), "transcendental_cycles": (20, 80), "compare_cycles": (0.5, 1),
     "active_power_w": (10.0, 10.0),
     "basis": "10 W board mode as reported in arXiv:2012.02907; the GPU is unused by these scalar predictors."},
]


def project(work_per_decision: dict, memory_bytes: int, exchange_s: float, profile: dict):
    """Latency, duty cycle, memory fit and an order-of-magnitude energy range per decision."""
    a=work_per_decision["arithmetic"]; t=work_per_decision["transcendental"]; k=work_per_decision["comparisons"]
    cycles=[a*profile["binary64_cycles"][i]+t*profile["transcendental_cycles"][i]+k*profile["compare_cycles"][i]
            for i in (0,1)]
    seconds=[x/profile["clock_hz"] for x in cycles]
    energy=[seconds[0]*profile["active_power_w"][0],seconds[1]*profile["active_power_w"][1]]
    return {"profile":profile["id"],"cycles_low":cycles[0],"cycles_high":cycles[1],
            "latency_us_low":seconds[0]*1e6,"latency_us_high":seconds[1]*1e6,
            "duty_cycle_percent_high":100*seconds[1]/exchange_s,
            "memory_fraction_percent":100*memory_bytes/profile["ram_bytes"],
            "projected_energy_uj_low":energy[0]*1e6,"projected_energy_uj_high":energy[1]*1e6}
