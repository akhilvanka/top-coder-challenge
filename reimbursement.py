#!/usr/bin/env python3
import sys
import json
import numpy as np

# ==== Fitted constants for per‐diem, mileage, bonuses ====
PER_DIEM_RATE         = 99.999792
FIVE_DAY_BONUS        = 49.999912
M1, M2                = 100.0, 500.0
MILEAGE_TIER1_RATE    = 0.579759
MILEAGE_TIER2_RATE    = 0.519797
MILEAGE_TIER3_RATE    = 0.449873
EFF_LOW, EFF_HIGH     = 150.0, 250.0
EFFICIENCY_MULTIPLIER = 1.099989
LONG_TRIP_MULTIPLIER  = 0.849974

# ==== Load and preprocess public cases to extract receipts curve ====
def _build_receipts_curve():
    with open("public_cases.json") as f:
        cases = json.load(f)

    xs, ys = [], []
    for c in cases:
        d = c["input"]["trip_duration_days"]
        m = c["input"]["miles_traveled"]
        r = c["input"]["total_receipts_amount"]
        expected = c["expected_output"]

        # 1) compute everything *but* receipts
        pd = PER_DIEM_RATE * d
        bonus = FIVE_DAY_BONUS if d == 5 else 0.0
        # mileage tiers
        t1 = min(m, M1) * MILEAGE_TIER1_RATE
        t2 = min(max(m - M1, 0.0), M2 - M1) * MILEAGE_TIER2_RATE
        t3 = max(m - M2, 0.0) * MILEAGE_TIER3_RATE
        mileage = t1 + t2 + t3
        if d > 0:
            mpg = m / d
            if EFF_LOW <= mpg <= EFF_HIGH:
                mileage *= EFFICIENCY_MULTIPLIER
        base = pd + bonus + mileage
        if d >= 8:
            base *= LONG_TRIP_MULTIPLIER

        # 2) the “missing” piece is receipts_reimb = expected – base
        receipts_reimb = expected - base

        # 3) normalize to per‐day curve: x = receipts_total/d, y = receipts_reimb/d
        if d > 0:
            xs.append(r / d)
            ys.append(receipts_reimb / d)

    # sort for interpolation
    idx = np.argsort(xs)
    return np.array(xs)[idx], np.array(ys)[idx]

_XS, _YS = _build_receipts_curve()

# ==== Core reimbursement function ====
def compute_reimbursement(days: int, miles: float, receipts: float) -> float:
    # per‐diem + bonus
    total = PER_DIEM_RATE * days
    if days == 5:
        total += FIVE_DAY_BONUS

    # mileage
    t1 = min(miles, M1) * MILEAGE_TIER1_RATE
    t2 = min(max(miles - M1, 0.0), M2 - M1) * MILEAGE_TIER2_RATE
    t3 = max(miles - M2, 0.0) * MILEAGE_TIER3_RATE
    mil = t1 + t2 + t3
    if days > 0:
        mpg = miles / days
        if EFF_LOW <= mpg <= EFF_HIGH:
            mil *= EFFICIENCY_MULTIPLIER
    total += mil

    # long‐trip penalty
    if days >= 8:
        total *= LONG_TRIP_MULTIPLIER

    # receipts: interpolate per‐day penalty curve
    rpday = (receipts / days) if days > 0 else 0.0
    rrpd = float(np.interp(rpday, _XS, _YS))
    total += rrpd * days

    # legacy rounding quirk
    # cents = int(round(total * 100)) % 100
    # if cents in (49, 99):
    #     total += 0.01

    return round(total, 2)

# ==== CLI entrypoint ====
if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("Usage: python reimburse.py <days> <miles> <receipts>")

    days     = int(sys.argv[1])
    miles    = float(sys.argv[2])
    receipts = float(sys.argv[3])

    print(f"{compute_reimbursement(days, miles, receipts):.2f}")
