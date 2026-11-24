"""
Data models for subject presets and visual style presets.
"""
from typing import Optional
from pydantic import BaseModel, Field


class SubjectPreset(BaseModel):
    id: str = Field(..., description="Unique identifier for the subject preset")
    name: str = Field(..., description="Human-readable display name")
    category: str = Field(default="General", description="Subject grouping category")
    description: str = Field(..., description="Short user-facing explanation")
    system_instructions: str = Field(..., description="Detailed instructions for the AI prompt builder")
    is_custom: bool = Field(default=False, description="Whether this is a user-created preset")


class VisualStylePreset(BaseModel):
    id: str = Field(..., description="Unique identifier for the visual style preset")
    name: str = Field(..., description="Human-readable display name")
    category: str = Field(default="General", description="Style grouping category")
    description: str = Field(..., description="Short user-facing explanation")
    system_instructions: str = Field(..., description="Detailed instructions for the AI prompt builder")
    is_custom: bool = Field(default=False, description="Whether this is a user-created preset")
