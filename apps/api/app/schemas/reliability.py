from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, extra="forbid")


class ReliabilityScore(APIModel):
    score: int = Field(ge=0, le=100)
    grade: str = Field(min_length=1, max_length=2)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    components: Dict[str, int] = Field(default_factory=dict)
