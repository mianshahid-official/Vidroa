"""
Data models for timeline validation and quality inspection.
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationIssue(BaseModel):
    scene_id: Optional[str] = None
    severity: ValidationSeverity = ValidationSeverity.WARNING
    rule: str = Field(..., description="The validation rule name (e.g. 'GAP_DETECTED', 'SHORT_PROMPT')")
    message: str = Field(..., description="Human-readable explanation of the issue")
    suggested_action: Optional[str] = None


class ValidationResult(BaseModel):
    is_valid: bool = True
    total_scenes_checked: int = 0
    issues: List[ValidationIssue] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == ValidationSeverity.ERROR for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)
