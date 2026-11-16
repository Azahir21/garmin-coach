#!/usr/bin/env python3
"""Speed <-> power on flat ground for a road cyclist (steady state, no wind, no drafting).

Model form: P_crank = (0.5*rho*CdA*v^3 + Crr*m*g*v + m*g*grade*v) / drivetrain_efficiency.
Martin et al. 1998 (J Appl Biomech 14:276, PMID 28121252) validated this kind of model against a power
meter (R2 = 0.97, standard error 2.7 W). Debraux 2011 (PMID 21936289): aerodynamic drag is mainly the product of
frontal area and drag coefficient (CdA) and dominates resistance at high speed on level ground.

THE PARAMETER VALUES BELOW ARE ASSUMPTIONS, NOT MEASUREMENTS OF THIS ATHLETE (no power meter, CdA never measured):
rho 1.2 kg/m3, Crr 0.005, drivetrain 0.975, mass = rider weight from athlete.json + an assumed 10 kg for bike and kit (bike weights are not stated). Change them with the flags; show the spread.
A bike with knobby tyres and an upright position likely has a higher Crr and CdA than these road defaults; no verified values, so pass your own.
The point is the shape: power grows with the cube of speed for the air-drag part, so a higher speed needs far more
than 25 % more power. Real numbers need a power meter or a measured CdA.

  cycling_power.py --from 20 --to 25 [--mass 75] [--cda 0.40] [--crr 0.005] [--grade 0]
  cycling_power.py --watts 120 [--cda ..]          speed that this power holds
"""
import argparse
import json
from pathlib import Path

G = 9.80665


def default_mass():
    """Rider weight from the athlete file + 10 kg bike and kit (assumption); 75 kg if the file has no weight."""
    try:
        d = json.loads((Path(__import__("os").environ.get("RAMPWISE_DATA") or __import__("os").environ.get("GARMIN_COACH_DATA") or (Path.home() / "garmin-coach-data" if (Path.home() / "garmin-coach-data").exists() and not (Path.home() / "rampwise-data").exists() else Path.home() / "rampwise-data")) / "athlete.json").read_text(encoding="utf-8"))
        return float(d["profile"]["weight_kg"]) + 10.0
    except Exception:
        return 75.0


def power(v_ms, cda, crr, mass, rho, eff, grade):
    return (0.5 * rho * cda * v_ms ** 3 + crr * mass * G * v_ms + mass * G * grade * v_ms) / eff


def speed_for(watts, cda, crr, mass, rho, eff, grade):
    lo, hi = 0.1, 30.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if power(mid, cda, crr, mass, rho, eff, grade) < watts:
            lo = mid
        else:
            hi = mid
    return lo


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="v0", type=float, help="start speed km/h")
    ap.add_argument("--to", dest="v1", type=float, help="target speed km/h")
    ap.add_argument("--watts", type=float)
    ap.add_argument("--mass", type=float, default=default_mass(), help="rider + bike + kit in kg (default: athlete weight + 10)")
    ap.add_argument("--cda", type=float, default=None, help="default: show 0.32 / 0.40 / 0.50")
    ap.add_argument("--crr", type=float, default=0.005)
    ap.add_argument("--rho", type=float, default=1.2)
    ap.add_argument("--eff", type=float, default=0.975)
    ap.add_argument("--grade", type=float, default=0.0, help="slope as a fraction, 0.01 = 1 %%")
    a = ap.parse_args()
    cdas = [a.cda] if a.cda else [0.32, 0.40, 0.50]
    print(f"ASSUMED parameters: mass {a.mass} kg, Crr {a.crr}, rho {a.rho}, drivetrain {a.eff}, grade {a.grade * 100:.1f} %, no wind, no drafting")
    if a.watts:
        for c in cdas:
            v = speed_for(a.watts, c, a.crr, a.mass, a.rho, a.eff, a.grade) * 3.6
            print(f"  CdA {c:.2f}: {a.watts:.0f} W holds {v:.1f} km/h")
    if a.v0 and a.v1:
        print(f"{'CdA':>5} {'W at %.0f' % a.v0:>9} {'W at %.0f' % a.v1:>9} {'ratio':>6}   aero share at target")
        for c in cdas:
            p0 = power(a.v0 / 3.6, c, a.crr, a.mass, a.rho, a.eff, a.grade)
            p1 = power(a.v1 / 3.6, c, a.crr, a.mass, a.rho, a.eff, a.grade)
            aero = 0.5 * a.rho * c * (a.v1 / 3.6) ** 3 / a.eff
            print(f"{c:5.2f} {p0:8.0f}W {p1:8.0f}W {p1 / p0:5.2f}x   {100 * aero / p1:.0f} %")
        print(f"Speed ratio {a.v1 / a.v0:.2f}x; the air-drag part alone scales with the cube = {(a.v1 / a.v0) ** 3:.2f}x.")
    print("Model form: Martin 1998 (validated); parameter values: assumptions. Position (CdA), wind and drafting change the answer a lot.")


if __name__ == "__main__":
    main()
