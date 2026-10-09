# F1 tyre degradation analysis - Bahrain 2024 (complete file, Stages 1-4)
#
# Each "# %%" line starts a cell. Run cell by cell (Shift+Enter), or run the
# whole file once from top to bottom. Every chart is drawn in exactly ONE place.

# %% Cell 1: imports and cache setup
import os
import fastf1
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import linregress

os.makedirs("cache", exist_ok=True)
fastf1.Cache.enable_cache("cache")

# %% Cell 2: load one race
YEAR = 2024
RACE = "Bahrain"

session = fastf1.get_session(YEAR, RACE, "R")
session.load(telemetry=False, weather=False, messages=False)

print(session.event["EventName"])
print(session.event["EventDate"])

# %% Cell 3: look at the laps table
laps = session.laps

print("Rows, columns:", laps.shape)
print(laps.columns.tolist())

# %% Cell 4: one driver's race
driver_laps = laps.pick_drivers("VER")

cols = ["LapNumber", "LapTime", "Compound", "TyreLife", "Stint",
        "PitInTime", "PitOutTime"]
print(driver_laps[cols].head(15))

# ======================================================================
# STAGE 2: clean the laps
# ======================================================================

# %% Cell 5: convert lap time to seconds
laps = session.laps.copy()
laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()

print(laps[["Driver", "LapNumber", "LapTime", "LapTimeSec"]].head())
print("Laps with no time recorded:", laps["LapTimeSec"].isna().sum())

# %% Cell 6: apply the filters, one at a time, and count what each removes
print("Start:", len(laps))

clean = laps[laps["LapTimeSec"].notna()]
print("After removing laps with no time:", len(clean))

clean = clean[clean["PitInTime"].isna() & clean["PitOutTime"].isna()]
print("After removing pit in/out laps:", len(clean))

# TrackStatus "1" means green flag. Anything else (yellow flags, VSC,
# safety car) is stored as other digits.
clean = clean[clean["TrackStatus"] == "1"]
print("After keeping green-flag laps only:", len(clean))

clean = clean[clean["IsAccurate"]]
print("After keeping laps FastF1 marks accurate:", len(clean))

clean = clean[clean["LapNumber"] > 1]
print("After removing lap 1:", len(clean))

# %% Cell 7: remove slow outliers (107% of the driver's own median lap)
median_lap = clean.groupby("Driver")["LapTimeSec"].transform("median")
clean = clean[clean["LapTimeSec"] < 1.07 * median_lap].copy()

print("Clean laps left:", len(clean))
print()
print("Laps per compound:")
print(clean["Compound"].value_counts())

# %% Cell 8: one driver before and after cleaning
ver_all = laps[laps["Driver"] == "VER"]
ver_clean = clean[clean["Driver"] == "VER"]

plt.figure(figsize=(9, 5))
plt.scatter(ver_all["LapNumber"], ver_all["LapTimeSec"],
            color="lightgrey", label="All laps")
plt.scatter(ver_clean["LapNumber"], ver_clean["LapTimeSec"],
            color="tab:blue", label="Clean laps")
plt.ylim(ver_clean["LapTimeSec"].min() - 1, ver_clean["LapTimeSec"].max() + 5)
plt.xlabel("Lap number")
plt.ylabel("Lap time (s)")
plt.title("Verstappen, Bahrain 2024: all laps vs clean laps")
plt.legend()
plt.savefig("cleaning_check.png", dpi=150, bbox_inches="tight")
plt.show()

# ======================================================================
# STAGE 3: measure degradation
# ======================================================================

# %% Cell 9: degradation per driver, per stint
# Fit: lap time = a + b * TyreLife.  b is the seconds lost per lap of tyre age.
degradation = []

for driver in clean["Driver"].unique():
    driver_laps = clean[clean["Driver"] == driver]
    for stint in driver_laps["Stint"].unique():
        stint_laps = driver_laps[driver_laps["Stint"] == stint]

        if len(stint_laps) < 3:      # need at least 3 laps to fit a line
            continue

        x = stint_laps["TyreLife"].values
        y = stint_laps["LapTimeSec"].values
        slope, intercept, r_value, p_value, std_err = linregress(x, y)

        degradation.append({
            "Driver": driver,
            "Stint": stint,
            "Compound": stint_laps["Compound"].iloc[0],
            "Degradation (s/lap)": slope,
            "R-squared": r_value ** 2,
            "Laps in stint": len(stint_laps),
        })

deg_df = pd.DataFrame(degradation)
print(deg_df.head(20))

# %% Cell 10: average degradation by compound
print("\nAverage degradation by compound:")
print(deg_df.groupby("Compound")["Degradation (s/lap)"].describe())

# ======================================================================
# STAGE 4: charts (each chart is drawn once and saved before it is shown)
# ======================================================================

# %% Cell 11: degradation rate per stint, by compound
np.random.seed(42)                       # same jitter every run
colors = {"SOFT": "tab:red", "HARD": "tab:blue"}

plt.figure(figsize=(7, 5))
for i, compound in enumerate(["SOFT", "HARD"]):
    vals = deg_df[deg_df["Compound"] == compound]["Degradation (s/lap)"]
    x = np.random.normal(i, 0.05, size=len(vals))   # jitter so dots don't overlap
    plt.scatter(x, vals, color=colors[compound], alpha=0.6)
    plt.hlines(vals.mean(), i - 0.25, i + 0.25, color="black", linewidth=2)

plt.xticks([0, 1], ["SOFT", "HARD"])
plt.axhline(0, color="grey", linewidth=0.8)
plt.ylabel("Degradation (s lost per lap of tyre age)")
plt.title("Bahrain 2024: tyre degradation per stint (black bar = mean)")
plt.savefig("degradation_per_stint.png", dpi=150, bbox_inches="tight")
plt.show()

# %% Cell 12: lap time vs tyre age, one fitted line per compound
# Centre every stint on its own mean lap time: keeps the slope, removes the
# difference in pace between drivers and stints.
clean["LapDelta"] = clean["LapTimeSec"] - clean.groupby(["Driver", "Stint"])["LapTimeSec"].transform("mean")

plt.figure(figsize=(9, 5))
for compound in ["SOFT", "HARD"]:
    d = clean[clean["Compound"] == compound]
    plt.scatter(d["TyreLife"], d["LapDelta"], color=colors[compound],
                alpha=0.25, label=compound)
    slope, intercept = np.polyfit(d["TyreLife"], d["LapDelta"], 1)
    xs = np.linspace(d["TyreLife"].min(), d["TyreLife"].max(), 50)
    plt.plot(xs, slope * xs + intercept, color=colors[compound], linewidth=2.5)
    print(f"{compound}: {slope:.4f} s/lap")

plt.xlabel("Tyre age (laps)")
plt.ylabel("Lap time vs stint average (s)")
plt.title("Bahrain 2024: lap time vs tyre age")
plt.legend()
plt.savefig("lap_time_vs_tyre_age.png", dpi=150, bbox_inches="tight")
plt.show()

# %% Cell 13: how much does the fuel assumption change the answer?
# The car gets lighter every lap, so lap times fall even if the tyres wear.
# Adding back (fuel_effect * LapNumber) removes that benefit.
for fuel_effect in [0.0, 0.03, 0.05]:      # seconds gained per lap from fuel burn
    print(f"\nAssumed fuel effect: {fuel_effect} s/lap")
    adj = clean.copy()
    adj["Adj"] = adj["LapTimeSec"] + fuel_effect * adj["LapNumber"]
    adj["AdjDelta"] = adj["Adj"] - adj.groupby(["Driver", "Stint"])["Adj"].transform("mean")
    for compound in ["SOFT", "HARD"]:
        d = adj[adj["Compound"] == compound]
        slope, _ = np.polyfit(d["TyreLife"], d["AdjDelta"], 1)
        print(f"  {compound}: {slope:.4f} s/lap")
