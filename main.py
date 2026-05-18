from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime
import os
import requests

app = FastAPI()

LOCATIONS = [
    {"country": "HU", "city": "Budapest", "lat": 47.4979, "lon": 19.0402},
    {"country": "HU", "city": "Debrecen", "lat": 47.5316, "lon": 21.6273},
    {"country": "HU", "city": "Szeged", "lat": 46.2530, "lon": 20.1414},
    {"country": "CZ", "city": "Prague", "lat": 50.0755, "lon": 14.4378},
    {"country": "CZ", "city": "Brno", "lat": 49.1951, "lon": 16.6068},
    {"country": "CZ", "city": "Ostrava", "lat": 49.8209, "lon": 18.2625},
    {"country": "SK", "city": "Bratislava", "lat": 48.1486, "lon": 17.1077},
    {"country": "SK", "city": "Košice", "lat": 48.7164, "lon": 21.2611},
    {"country": "SK", "city": "Prešov", "lat": 49.0018, "lon": 21.2393},
    {"country": "SI", "city": "Ljubljana", "lat": 46.0569, "lon": 14.5058},
    {"country": "SI", "city": "Maribor", "lat": 46.5547, "lon": 15.6459},
    {"country": "SI", "city": "Celje", "lat": 46.2397, "lon": 15.2677},
    {"country": "RO", "city": "Bucharest", "lat": 44.4268, "lon": 26.1025},
    {"country": "RO", "city": "Cluj-Napoca", "lat": 46.7712, "lon": 23.6236},
    {"country": "RO", "city": "Timișoara", "lat": 45.7489, "lon": 21.2087},
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
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_gusts_10m",
            "forecast_days": 3,
            "timezone": "auto",
        },
        timeout=20,
    )
    response.raise_for_status()
    hourly = response.json().get("hourly", {})
    return {k: v[:hours] for k, v in hourly.items()}

def fetch_air_quality(lat: float, lon: float, hours: int) -> Dict[str, Any]:
    response = requests.get(
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "pm10,pm2_5,nitrogen_dioxide,ozone,grass_pollen,birch_pollen,alder_pollen,mugwort_pollen,ragweed_pollen",
            "forecast_days": 3,
            "timezone": "auto",
        },
        timeout=20,
    )
    response.raise_for_status()
    hourly = response.json().get("hourly", {})
    return {k: v[:hours] for k, v in hourly.items()}

def current_season() -> str:
    month = datetime.utcnow().month
    if month in [3, 4]:
        return "early_tree_pollen"
    if month in [5, 6, 7]:
        return "grass_pollen"
    if month in [8, 9, 10]:
        return "ragweed_mugwort_pollen"
    return "winter_pollution"

def calculate_pollen_score(air: Dict[str, Any]) -> Dict[str, Any]:
    season = current_season()
    pollen_metrics = {
        "grass_pollen": max_value(air.get("grass_pollen", [])),
        "birch_pollen": max_value(air.get("birch_pollen", [])),
        "alder_pollen": max_value(air.get("alder_pollen", [])),
        "mugwort_pollen": max_value(air.get("mugwort_pollen", [])),
        "ragweed_pollen": max_value(air.get("ragweed_pollen", [])),
    }

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

    elif season == "ragweed_mugwort_pollen":
        if pollen_metrics["ragweed_pollen"] is not None and pollen_metrics["ragweed_pollen"] >= 20:
            score += 4
            drivers.append("ragweed pollen")
        if pollen_metrics["mugwort_pollen"] is not None and pollen_metrics["mugwort_pollen"] >= 20:
            score += 3
            drivers.append("mugwort pollen")

    active_values = [v for v in pollen_metrics.values() if isinstance(v, (int, float))]
    return {
        "score": score,
        "drivers": drivers,
        "season": season,
        "metrics": pollen_metrics,
        "max_any_pollen": max(active_values) if active_values else None,
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

    score += pollen["score"]
    drivers.extend(pollen["drivers"])

    if max_temp is not None and max_temp >= 32:
        score += 2
        drivers.append("heat")
    if min_temp is not None and min_temp <= 0:
        score += 2
        drivers.append("cold")

    humidity_flag = max_humidity is not None and max_humidity >= 85

    if max_precip is not None and max_precip >= 10:
        score += 1
        drivers.append("heavy rain / storm conditions")
    if max_gust is not None and max_gust >= 60:
        score += 1
        drivers.append("strong wind")

    if "heat" in drivers and "ozone" in drivers:
        score += 3
        drivers.append("heat + ozone synergy")
    if "PM2.5" in drivers and "ozone" in drivers:
        score += 3
        drivers.append("PM + ozone synergy")

    pollen_driver_present = any("pollen" in d for d in drivers)
    if pollen_driver_present and "heavy rain / storm conditions" in drivers:
        score += 3
        drivers.append("pollen + storm synergy")

    if humidity_flag and len(drivers) >= 2:
        score += 1
        drivers.append("humidity (secondary)")

    if score >= 9:
        level = "critical"
    elif score >= 6:
        level = "high"
    elif score >= 4:
        level = "moderate"
    else:
        level = "low"

    core_drivers = [d for d in drivers if "humidity" not in d]
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
    return {"low": 0, "moderate": 1, "high": 2, "critical": 3, "error": -1}.get(level, 1)

def build_alerts(request: RiskRequest):
    alerts = []
    selected_locations = [loc for loc in LOCATIONS if loc["country"] in request.countries]

    for loc in selected_locations:
        try:
            forecast = fetch_forecast(loc["lat"], loc["lon"], request.forecast_hours)
            air = fetch_air_quality(loc["lat"], loc["lon"], request.forecast_hours)
            risk = calculate_risk(forecast, air)

            if level_rank(risk["risk_level"]) >= level_rank(request.min_alert_level):
                alerts.append({
                    "country": loc["country"],
                    "city": loc["city"],
                    "risk_level": risk["risk_level"],
                    "score": risk["score"],
                    "drivers": risk["drivers"],
                    "metrics": risk["metrics"],
                    "respiratory_relevance": "Environmental conditions may increase respiratory burden and exacerbation risk in asthma and COPD populations.",
                    "recommended_action": "Monitor local respiratory risk signals, consider non-promotional HCP/patient awareness messaging where appropriate, and follow official weather and public health warnings.",
                })
        except Exception as e:
            alerts.append({
                "country": loc["country"],
                "city": loc["city"],
                "risk_level": "error",
                "drivers": ["data retrieval failed"],
                "error": str(e),
            })

    return selected_locations, alerts

@app.post("/risk-check")
def risk_check(request: RiskRequest):
    selected_locations, alerts = build_alerts(request)
    return {
        "status": "success",
        "generated_at": datetime.utcnow().isoformat(),
        "locations_checked": len(selected_locations),
        "summary": f"{len(alerts)} alert(s) at or above {request.min_alert_level} detected across {len(selected_locations)} checked locations.",
        "alerts": alerts,
        "data_sources": ["Open-Meteo Forecast API", "Open-Meteo Air Quality API"],
        "limitations": "Automated screening tool only. Not medical advice. No individual patient data or official national health alert systems included.",
    }

def format_teams_message(alerts: List[Dict[str, Any]]) -> Dict[str, str]:
    lines = [
        "🚨 CEE Respiratory Weather Risk Alert",
        "",
        f"Generated: {datetime.utcnow().isoformat()} UTC",
        "",
    ]

    for alert in alerts:
        lines.append(
            f"- {alert['country']} / {alert['city']}: "
            f"{alert['risk_level'].upper()} "
            f"(score {alert.get('score')}) – "
            f"{', '.join(alert.get('drivers', []))}"
        )

    lines.extend([
        "",
        "Relevance: Potentially increased respiratory burden for asthma/COPD populations.",
        "Action: Monitor local signals and official warnings; consider appropriate non-promotional awareness messaging.",
    ])

    return {"text": "\n".join(lines)}

def send_teams_alert(alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    webhook_url = os.getenv("TEAMS_WEBHOOK_URL")
    if not webhook_url:
        return {"sent": False, "reason": "TEAMS_WEBHOOK_URL not configured"}

    payload = format_teams_message(alerts)
    response = requests.post(webhook_url, json=payload, timeout=20)

    return {
        "sent": response.status_code in [200, 202],
        "status_code": response.status_code,
        "response_text": response.text[:500],
    }

@app.get("/run-alert-check")
def run_alert_check():
    request = RiskRequest(
        countries=["HU", "CZ", "SK", "SI", "RO", "BG"],
        forecast_hours=72,
        min_alert_level="high",
    )

    selected_locations, alerts = build_alerts(request)

    if not alerts:
        return {
            "status": "success",
            "generated_at": datetime.utcnow().isoformat(),
            "locations_checked": len(selected_locations),
            "alerts_sent": False,
            "reason": "No High or Critical alerts detected.",
        }

    send_result = send_teams_alert(alerts)

    return {
        "status": "success",
        "generated_at": datetime.utcnow().isoformat(),
        "locations_checked": len(selected_locations),
        "alerts_found": len(alerts),
        "alerts_sent": send_result.get("sent"),
        "send_result": send_result,
        "alerts": alerts,
    }
