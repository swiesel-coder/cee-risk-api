from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from datetime import datetime

app = FastAPI()

class RiskRequest(BaseModel):
    countries: List[str]
    forecast_hours: int
    min_alert_level: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/risk-check")
def risk_check(request: RiskRequest):
    return {
        "status": "success",
        "generated_at": datetime.utcnow().isoformat(),
        "summary": "Test alert: High respiratory risk in Budapest.",
        "alerts": [
            {
                "country": "HU",
                "city": "Budapest",
                "risk_level": "high",
                "drivers": ["heat", "ozone"],
                "respiratory_relevance": "Increased risk for asthma/COPD exacerbations.",
                "recommended_action": "Reduce outdoor exposure and monitor symptoms."
            }
        ]
    }