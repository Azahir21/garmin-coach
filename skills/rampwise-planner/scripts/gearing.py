#!/usr/bin/env python3
"""Gearing calculator: speed from cadence and gear, or the cadence a target speed needs.

Pure arithmetic: speed = cadence x (chainring teeth / cog teeth) x wheel circumference.
The wheel circumference is NOT measured: defaults are typical tyre-table values and are assumptions
(700x25c about 2105 mm). Give the real tyre size or a rolled-out circumference with --circ-mm.

  gearing.py --chainring 52 --cog 18 [--circ-mm 2105] [--target 25] [--cadences 60 70 80 90 100]
  gearing.py --chainring 50 --cog 11 --cog 28 --circ-mm 2105      # several cogs (range ends)
"""
import argparse


def kmh(cadence, chainring, cog, circ_mm):
    return cadence * (chainring / cog) * circ_mm / 1000.0 * 60.0 / 1000.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chainring", type=int, required=True)
    ap.add_argument("--cog", type=int, action="append", required=True)
    ap.add_argument("--circ-mm", type=float, default=2105.0, help="wheel circumference in mm (default 2105: assumed 700x25c)")
    ap.add_argument("--target", type=float, default=None, help="target speed km/h: print the cadence needed")
    ap.add_argument("--cadences", type=int, nargs="*", default=[60, 70, 80, 90, 100])
    a = ap.parse_args()
    print(f"ASSUMED wheel circumference {a.circ_mm:.0f} mm (check your tyre size). Chainring {a.chainring}T.")
    for cog in a.cog:
        ratio = a.chainring / cog
        dev = ratio * a.circ_mm / 1000.0
        print(f"\nCog {cog}T: ratio {ratio:.2f}, {dev:.2f} m per pedal turn")
        print("  cadence (rpm): " + "  ".join(f"{c:>5}" for c in a.cadences))
        print("  speed (km/h) : " + "  ".join(f"{kmh(c, a.chainring, cog, a.circ_mm):5.1f}" for c in a.cadences))
        if a.target:
            need = a.target * 1000.0 / 60.0 / dev          # metres per minute / metres per pedal turn
            print(f"  {a.target:g} km/h needs {need:.0f} rpm in this gear")


if __name__ == "__main__":
    main()
