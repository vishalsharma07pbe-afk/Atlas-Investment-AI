"""Read-only, on-demand research alert evaluation with fail-closed evidence gates."""
from datetime import date
from typing import Literal
from pydantic import BaseModel,Field,model_validator
from .risk_qualification import qualify

class AlertRule(BaseModel):
    metric: Literal["CLOSE_ABOVE","CLOSE_BELOW","RSI_ABOVE","RSI_BELOW","RELATIVE_VOLUME_ABOVE"]
    threshold: float = Field(gt=0,le=1000000000)

    @model_validator(mode="after")
    def validate_threshold(self):
        if self.metric.startswith("RSI_") and self.threshold>100:
            raise ValueError("RSI threshold must not exceed 100")
        return self

class AlertRequest(BaseModel):
    instrument_id: int = Field(gt=0)
    rules: list[AlertRule] = Field(min_length=1,max_length=10)
    max_age_days: int = Field(default=7,ge=0,le=30)

def evaluate_alerts(raw,rules,max_age_days=7,as_of=None):
    assessment=qualify(raw,as_of=as_of,max_age_days=max_age_days)
    if assessment["status"]!="OBSERVATIONS_READY":
        return {"status":"BLOCKED","failures":assessment["failures"],"alerts":[],
                "notice":"Evidence gates failed. No alert was triggered."}
    candles=raw["candles"]
    close=float(candles[-1]["close"])
    observations=assessment["observations"]
    values={"CLOSE_ABOVE":close,"CLOSE_BELOW":close,
            "RSI_ABOVE":observations["rsi_14"],"RSI_BELOW":observations["rsi_14"],
            "RELATIVE_VOLUME_ABOVE":observations["relative_volume_20"]}
    alerts=[]
    for rule in rules:
        observed=values[rule.metric]
        triggered=observed>rule.threshold if rule.metric.endswith("_ABOVE") else observed<rule.threshold
        alerts.append({"metric":rule.metric,"threshold":rule.threshold,
            "observed":observed,"triggered":triggered,
            "as_of":assessment["as_of"],"timeframe":"1d"})
    return {"status":"EVALUATED","failures":[],"alerts":alerts,
            "triggered_count":sum(x["triggered"] for x in alerts),
            "notice":"On-demand historical daily threshold evaluation only. No push notifications, live monitoring, price targets or investment recommendations."}
