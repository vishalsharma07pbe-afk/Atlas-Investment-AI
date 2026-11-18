"""Strict model-independent verdict contract. Unverified outputs never become trade signals."""
import json
import re
from decimal import Decimal, InvalidOperation
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ACTIONS = {"BUY", "SELL", "HOLD", "AVOID"}
HORIZONS = {"INTRADAY", "SWING", "SHORT_TERM", "LONG_TERM"}
SAFE_TEXT = re.compile(r"(?i)(?:bearer\s+\S+|(?:api[_ -]?key|access[_ -]?token|password|account[_ -]?id)\s*[:=]|sk-[a-z0-9_-]{12,})")

class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: str
    confidence: float = Field(ge=0, le=1)
    target_1: float | None
    target_2: float | None
    stop_loss: float | None
    holding_horizon: str
    pros: list[str] = Field(min_length=1, max_length=5)
    cons: list[str] = Field(min_length=1, max_length=5)

    @field_validator("action")
    @classmethod
    def action_allowed(cls, value):
        if value not in ACTIONS:
            raise ValueError("INVALID_ACTION")
        return value

    @field_validator("holding_horizon")
    @classmethod
    def horizon_allowed(cls, value):
        if value not in HORIZONS:
            raise ValueError("INVALID_HORIZON")
        return value

    @field_validator("target_1","target_2","stop_loss")
    @classmethod
    def positive_level(cls, value):
        if value is not None and (not Decimal(str(value)).is_finite() or value <= 0):
            raise ValueError("INVALID_PRICE_LEVEL")
        return value

    @field_validator("pros","cons", mode="before")
    @classmethod
    def short_safe_reasons(cls, value):
        if not isinstance(value,list):
            raise ValueError("INVALID_REASONS")
        value=[reason for reason in value if isinstance(reason,str)
               and reason.strip().lower() not in {"null","none","n/a","na","unknown"}]
        if not value:
            raise ValueError("EMPTY_REASONS")
        if any(not reason.strip() or len(reason)>280 or SAFE_TEXT.search(reason) for reason in value):
            raise ValueError("UNSAFE_REASON")
        return value

    @model_validator(mode="after")
    def consistent_levels(self):
        if self.action in ("HOLD","AVOID") and any(x is not None for x in
            (self.target_1,self.target_2,self.stop_loss)):
            raise ValueError("NON_ACTIONABLE_VERDICT_HAS_PRICE_LEVELS")
        if self.action=="BUY" and all(x is not None for x in
            (self.target_1,self.target_2,self.stop_loss)):
            if not self.stop_loss < self.target_1 <= self.target_2:
                raise ValueError("INCONSISTENT_BUY_LEVELS")
        return self

def parse_verdict(raw: str) -> Verdict:
    if not isinstance(raw,str) or len(raw)>16000:
        raise ValueError("INVALID_VERDICT_PAYLOAD")
    try:
        data=json.loads(raw)
    except (ValueError,TypeError) as exc:
        raise ValueError("VERDICT_NOT_JSON") from exc
    return Verdict.model_validate(data)

VERDICT_PROMPT = """Return exactly one JSON object, no Markdown, no other text.
Required keys: action (BUY|SELL|HOLD|AVOID), confidence (number 0..1),
target_1 (positive number or null), target_2 (positive number or null),
stop_loss (positive number or null), holding_horizon
(INTRADAY|SWING|SHORT_TERM|LONG_TERM), pros (1..5 short strings),
cons (1..5 short strings). Use null levels for HOLD or AVOID.
Every pro and con must cite a supplied observation or an explicit missing-data
limitation. Never emit the strings "null", "none", or "unknown" as reasons.
Do not invent missing market observations. When uncertain choose AVOID.
"""
