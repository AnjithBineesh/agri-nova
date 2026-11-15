"""Feature definitions, crop name mapping and weather-to-feature conversion for the ML models."""
import calendar
import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "ml_data"
ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"

CROP_DATA = DATA_DIR / "crop_recommendation.csv"
SOIL_DATA = DATA_DIR / "soil_nutrients_crop.csv"
YIELD_DATA = DATA_DIR / "india_rainfall_crop_yield_2014_2024.csv"
WEATHER_REFERENCE = DATA_DIR / "weather_daily_kochi_2020_2025.csv"


@dataclass(frozen=True)
class Feature:
    key: str
    label: str
    unit: str
    help: str


CROP_FEATURES = [
    Feature("N", "Nitrogen (N)", "soil test value", "Nitrogen value from your soil test"),
    Feature("P", "Phosphorus (P)", "soil test value", "Phosphorus value from your soil test"),
    Feature("K", "Potassium (K)", "soil test value", "Potassium value from your soil test"),
    Feature("temperature", "Average temperature", "°C", "Average air temperature during the growing season"),
    Feature("humidity", "Average humidity", "%", "Average relative humidity during the growing season"),
    Feature("ph", "Soil pH", "pH", "Soil pH from your soil test"),
    Feature("rainfall", "Rainfall", "mm per month", "Average monthly rainfall during the growing season"),
]

SOIL_FEATURES = [
    Feature("N", "Nitrogen (N)", "kg/ha", "Available nitrogen"),
    Feature("P", "Phosphorus (P)", "kg/ha", "Available phosphorus"),
    Feature("K", "Potassium (K)", "kg/ha", "Available potassium"),
    Feature("ph", "Soil pH", "pH", "Soil pH"),
    Feature("EC", "Electrical conductivity", "dS/m", "Salinity indicator"),
    Feature("S", "Sulphur (S)", "ppm", "Available sulphur"),
    Feature("Cu", "Copper (Cu)", "ppm", "Available copper"),
    Feature("Fe", "Iron (Fe)", "ppm", "Available iron"),
    Feature("Mn", "Manganese (Mn)", "ppm", "Available manganese"),
    Feature("Zn", "Zinc (Zn)", "ppm", "Available zinc"),
    Feature("B", "Boron (B)", "ppm", "Available boron"),
]

DISPLAY_NAMES = {
    "rice": "Rice", "maize": "Maize", "chickpea": "Chickpea", "kidneybeans": "Kidney beans",
    "pigeonpeas": "Pigeon pea", "mothbeans": "Moth bean", "mungbean": "Green gram (mung bean)",
    "blackgram": "Black gram", "lentil": "Lentil", "pomegranate": "Pomegranate", "banana": "Banana",
    "mango": "Mango", "grapes": "Grapes", "watermelon": "Watermelon", "muskmelon": "Muskmelon", "apple": "Apple",
    "orange": "Orange", "papaya": "Papaya", "coconut": "Coconut", "cotton": "Cotton", "jute": "Jute",
    "coffee": "Coffee", "mulberry": "Mulberry", "ragi": "Finger millet (ragi)", "potato": "Potato",
}

# ML label -> slug in the Agri Nova crop database (only crops present in both).
CROP_DB_SLUG = {
    "rice": "rice", "maize": "maize", "chickpea": "chickpea", "pigeonpeas": "pigeonpea", "mungbean": "green_gram",
    "blackgram": "black_gram", "lentil": "lentil", "cotton": "cotton", "ragi": "finger_millet", "potato": "potato",
}
SLUG_TO_LABEL = {v: k for k, v in CROP_DB_SLUG.items()}


def load_crop_data() -> pd.DataFrame:
    return pd.read_csv(CROP_DATA)


def load_soil_data() -> pd.DataFrame:
    df = pd.read_csv(SOIL_DATA, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    return df


def read_daily_weather_csv(path_or_text) -> pd.DataFrame:
    """Parse a daily weather CSV with a '-BEGIN HEADER- ... -END HEADER-' block and YEAR, DOY columns.

    Returns a frame with date, temperature (°C), humidity (%), rainfall (mm/day). Fill values (-999) become NaN.
    """
    text = Path(path_or_text).read_text() if isinstance(path_or_text, (str, Path)) and Path(str(path_or_text)).exists() \
        else str(path_or_text)
    lines = text.splitlines()
    start = lines.index("-END HEADER-") + 1 if "-END HEADER-" in lines else 0
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
    df = df.replace(-999, np.nan).replace(-999.0, np.nan)
    df["date"] = pd.to_datetime(df["YEAR"].astype(str) + "-01-01") + pd.to_timedelta(df["DOY"] - 1, unit="D")
    return pd.DataFrame({"date": df["date"], "temperature": df.get("T2M"), "humidity": df.get("RH2M"),
                         "rainfall": df.get("PRECTOTCORR")})


def monthly_climatology(daily: pd.DataFrame) -> pd.DataFrame:
    """Mean monthly temperature/humidity and mean monthly rainfall total across years (complete months only)."""
    d = daily.dropna(subset=["temperature"]).copy()
    d["y"], d["m"] = d["date"].dt.year, d["date"].dt.month
    g = d.groupby(["y", "m"])
    monthly = g.agg(temperature=("temperature", "mean"), humidity=("humidity", "mean"), rainfall=("rainfall", "sum"),
                    days=("temperature", "size")).reset_index()
    monthly = monthly[monthly.apply(lambda r: r["days"] >= calendar.monthrange(int(r["y"]), int(r["m"]))[1] - 1, axis=1)]
    return monthly.groupby("m")[["temperature", "humidity", "rainfall"]].mean()


def season_months(start: int, end: int) -> list[int]:
    n = (end - start) % 12 + 1
    return [((start - 1 + i) % 12) + 1 for i in range(n)]


def season_features(monthly_rows: list[dict], start: int, end: int) -> dict:
    """Season climate features in the units the crop model was trained with.

    monthly_rows: 12 dicts with t_mean, rh, precip_mm (Agri Nova climate profile format).
    """
    months = season_months(start, end)
    rows = [monthly_rows[m - 1] for m in months]
    temps = [r["t_mean"] for r in rows if r.get("t_mean") is not None]
    rhs = [r["rh"] for r in rows if r.get("rh") is not None]
    rains = [r["precip_mm"] for r in rows if r.get("precip_mm") is not None]
    return {
        "temperature": round(float(np.mean(temps)), 1) if temps else None,
        "humidity": round(float(np.mean(rhs)), 1) if rhs else None,
        "rainfall": round(float(np.mean(rains)), 1) if rains else None,
    }
