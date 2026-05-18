from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime
import requests

app = FastAPI()

LOCATIONS = [
    # Hungary
    {"country": "HU", "city": "Budapest", "lat": 47.4979, "lon": 19.0402},
    {"country": "HU", "city": "Debrecen", "lat": 47.5316, "lon": 21.6273},
    {"country": "HU", "city": "Szeged", "lat": 46.2530, "lon": 20.1414},

    # Czech Republic
    {"country": "CZ", "city": "Prague", "lat": 50.0755, "lon": 14.4378},
    {"country": "CZ", "city": "Brno", "lat": 49.1951, "lon": 16.6068},
    {"country": "CZ", "city": "Ostrava", "lat": 49.8209, "lon": 18.2625},

    # Slovakia
    {"country": "SK", "city": "Bratislava", "lat": 48.1486, "lon": 17.1077},
    {"country": "SK", "city": "Košice", "lat": 48.7164, "lon": 21.2611},
    {"country": "SK", "city": "Prešov", "lat": 49.0018, "lon": 21.2393},

    # Slovenia
    {"country": "SI", "city": "Ljubljana", "lat": 46.0569, "lon": 14.5058},
    {"country": "SI", "city": "Maribor", "lat": 46.5547, "lon": 15.6459},
    {"country": "SI", "city": "Celje", "lat": 46.2397, "lon": 15.2677},

    # Romania
    {"country": "RO", "city": "Bucharest", "lat": 44.4268, "lon": 26.1025},
    {"country": "RO", "city": "Cluj-Napoca", "lat": 46.7712, "lon": 23.6236},
    {"country": "RO", "city": "Timișoara", "lat": 45.7489, "lon": 21.2087},

    # Bulgaria
    {"country": "BG", "city": "Sofia", "lat": 42.6977, "lon": 23.3219},
    {"country": "BG", "city": "Plovdiv", "lat": 42.1354, "lon": 24.7453},
    {"country": "BG", "city": "Varna", "lat": 43.2141, "lon": 27.9147},
]


class RiskRequest(BaseModel):
    countries: List[str]
    forecast_hours: int = 72
    min_alert_level: str = "moderate"


@app.get("/")
def root():
    return {"message": "CEE Respiratory Risk API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.head("/health")
def health_head():
    return


def max_value(values):
    nums = [v for v in values if isinstance(v, (int, float))]
    return max(nums) if nums else None


def min_value(values):
    nums = [v for v in values if isinstance(v, (int, float))]
    return min(nums) if nums else None


def fetch_forecast(lat: float, lon: float, hours: int) -> Dict[str, Any]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "precipitation,"
            "wind_gusts_10m"
        ),
        "forecast_days": 3,
        "timezone": "auto",
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    hourly = data.get("hourly", {})
    return {k: v[:hours] for k, v in hourly.items()}


def fetch_air_quality(lat: float, lon: float, hours: int) -> Dict[str, Any]:
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": (
            "pm10,"
            "pm2_5,"
            "nitrogen_dioxide,"
            "ozone,"
            "grass_pollen,"
            "birch_pollen,"
            "alder_pollen,"
            "mugwort_pollen,"
            "ragweed_pollen"
        ),
        "forecast_days": 3,
        "timezone": "auto",
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    hourly = data.get("hourly", {})
    return {k: v[:hours] for k, v in hourly.items()}


def current_season() -> str:
    month = datetime.utcnow().month

    if month in [3, 4]:
        return "early_tree_pollen"
    if month in [5, 6, 7]:
        return "grass_pollen"
    if month in [8, 9, 10]:
        return "ragweed_mugwort_pollen"
    if month in [11, 12, 1, 2]:
        return "winter_pollution"

    return "unknown"


def calculate_pollen_score(air: Dict[str, Any]) -> Dict[str, Any]:
    season = current_season()

    pollen_metrics = {
        "grass_pollen": max_value(air.get("grass_pollen", [])),
        "birch_pollen": max_value(air.get("birch_pollen", [])),
        "alder_pollen": max_value(air.get("alder_pollen", [])),
        "mugwort_pollen": max_value(air.get("mugwort_pollen", [])),
        "ragweed_pollen": max_value(air.get("ragweed_pollen", [])),
    }

    active_values = [
        value for value in pollen_metrics.values()
        if isinstance(value, (int, float))
    ]

    max_any_pollen = max(active_values) if active_values else None

    score = 0
    drivers = []

    if season == "early_tree_pollen":
        if pollen_metrics["birch_pollen"] is not None and pollen_metrics["birch_pollen"] >= 50:
            score += 3
            drivers.append("birch pollen")
        if pollen_metrics["alder_pollen"] is not None and pollen_metrics["alder_pollen"] >= 50:
            score += 2
            drivers.append("alder pollen")

    elif season == "grass_pollen":
        if pollen_metrics["grass_pollen"] is not None and pollen_metrics["grass_pollen"] >= 30:
            score += 3
            drivers.append("grass pollen")
        if pollen_metrics["birch_pollen"] is not None and pollen_metrics["birch_pollen"] >= 70:
            score += 1
            drivers.append("residual tree pollen")

    elif season == "ragweed_mugwort_pollen":
        if pollen_metrics["ragweed_pollen"] is not None and pollen_metrics["ragweed_pollen"] >= 20:
            score += 4
            drivers.append("ragweed pollen")
        if pollen_metrics["mugwort_pollen"] is not None and pollen_metrics["mugwort_pollen"] >= 20:
            score += 3
            drivers.append("mugwort pollen")
        if pollen_metrics["grass_pollen"] is not None and pollen_metrics["grass_pollen"] >= 40:
            score += 1
            drivers.append("late grass pollen")

    else:
        if max_any_pollen is not None and max_any_pollen >= 80:
            score += 1
            drivers.append("out-of-season pollen signal")

    return {
        "score": score,
        "drivers": drivers,
        "season": season,
        "metrics": pollen_metrics,
        "max_any_pollen": max_any_pollen,
    }


def calculate_risk(forecast: Dict[str, Any], air: Dict[str, Any]) -> Dict[str, Any]:
    max_temp = max_value(forecast.get("temperature_2m", []))
    min_temp = min_value(forecast.get("temperature_2m", []))
    max_humidity = max_value(forecast.get("relative_humidity_2m", []))
    max_precip = max_value(forecast.get("precipitation", []))
    max_gust = max_value(forecast.get("wind_gusts_10m", []))

    max_pm25 = max_value(air.get("pm2_5", []))
    max_pm10 = max_value(air.get("pm10", []))
    max_no2 = max_value(air.get("nitrogen_dioxide", []))
    max_ozone = max_value(air.get("ozone", []))

    pollen = calculate_pollen_score(air)

    score = 0
    drivers = []

    # Air quality
    if max_pm25 is not None and max_pm25 >= 25:
        score += 3
        drivers.append("PM2.5")
    if max_pm10 is not None and max_pm10 >= 50:
        score += 2
        drivers.append("PM10")
    if max_no2 is not None and max_no2 >= 40:
        score += 2
        drivers.append("NO2")
    if max_ozone is not None and max_ozone >= 120:
        score += 2
        drivers.append("ozone")

    # Seasonally weighted pollen
    score += pollen["score"]
    drivers.extend(pollen["drivers"])

    # Weather stress
    if max_temp is not None and max_temp >= 32:
        score += 2
        drivers.append("heat")
    if min_temp is not None and min_temp <= 0:
        score += 2
        drivers.append("cold")

    humidity_flag = False
    if max_humidity is not None and max_humidity >= 85:
        humidity_flag = True

    if max_precip is not None and max_precip >= 10:
        score += 1
        drivers.append("heavy rain / storm conditions")

    if max_gust is not None and max_gust >= 60:
        score += 1
        drivers.append("strong wind")

    # Synergies
    if "heat" in drivers and "ozone" in drivers:
        score += 3
        drivers.append("heat + ozone synergy")

    if "PM2.5" in drivers and "ozone" in drivers:
        score += 3
        drivers.append("PM + ozone synergy")

    pollen_driver_present = any(
        "pollen" in driver for driver in drivers
    )

    if pollen_driver_present and "heavy rain / storm conditions" in drivers:
        score += 3
        drivers.append("pollen + storm synergy")

    if humidity_flag and len(drivers) >= 2:
        score += 1
        drivers.append("humidity (secondary)")

    core_drivers = [
        driver for driver in drivers
        if "humidity" not in driver
    ]

    if score >= 9:
        level = "critical"
    elif score >= 6:
        level = "high"
    elif score >= 4:
        level = "moderate"
    else:
        level = "low"

    # Prevent single-factor alerts below high severity
    if len(core_drivers) < 2 and score < 6:
        level = "low"

    return {
        "score": score,
        "risk_level": level,
        "drivers": drivers,
        "metrics": {
            "max_temperature_c": max_temp,
            "min_temperature_c": min_temp,
            "max_humidity_percent": max_humidity,
            "max_precipitation_mm": max_precip,
            "max_wind_gusts_kmh": max_gust,
            "max_pm2_5": max_pm25,
            "max_pm10": max_pm10,
            "max_no2": max_no2,
            "max_ozone": max_ozone,
            "pollen_season": pollen["season"],
            "max_any_pollen": pollen["max_any_pollen"],
            "pollen_detail": pollen["metrics"],
        },
    }


def level_rank(level: str) -> int:
    return {
        "low": 0,
        "moderate": 1,
        "high": 2,
        "critical": 3,
        "error": -1,
    }.get(level, 1)


@app.post("/risk-check")
def risk_check(request: RiskRequest):
    alerts = []

    selected_locations = [
        loc for loc in LOCATIONS
        if loc["country"] in request.countries
    ]

    for loc in selected_locations:
        try:
            forecast = fetch_forecast(
                loc["lat"],
                loc["lon"],
                request.forecast_hours,
            )
            air = fetch_air_quality(
                loc["lat"],
                loc["lon"],
                request.forecast_hours,
            )

            risk = calculate_risk(forecast, air)

            if level_rank(risk["risk_level"]) >= level_rank(request.min_alert_level):
                alerts.append(
                    {
                        "country": loc["country"],
                        "city": loc["city"],
                        "risk_level": risk["risk_level"],
                        "score": risk["score"],
                        "drivers": risk["drivers"],
                        "metrics": risk["metrics"],
                        "respiratory_relevance": (
                            "Environmental conditions may increase respiratory "
                            "burden and exacerbation risk in asthma and COPD populations."
                        ),
                        "recommended_action": (
                            "Monitor local respiratory risk signals, consider "
                            "non-promotional HCP/patient awareness messaging where "
                            "appropriate, and follow official weather and public "
                            "health warnings."
                        ),
                    }
                )

        except Exception as e:
            alerts.append(
                {
                    "country": loc["country"],
                    "city": loc["city"],
                    "risk_level": "error",
                    "drivers": ["data retrieval failed"],
                    "error": str(e),
                }
            )

    return {
        "status": "success",
        "generated_at": datetime.utcnow().isoformat(),
        "locations_checked": len(selected_locations),
        "summary": (
            f"{len(alerts)} alert(s) at or above "
            f"{request.min_alert_level} detected across "
            f"{len(selected_locations)} checked locations."
        ),
        "alerts": alerts,
        "data_sources": [
            "Open-Meteo Forecast API",
            "Open-Meteo Air Quality API",
        ],
        "limitations": (
            "This is an automated screening tool and not medical advice. "
            "It does not include individual patient data or official national "
            "health alert systems."
        ),
    }
