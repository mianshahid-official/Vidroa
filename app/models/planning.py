"""
Structured Pydantic data models for PromptBeast / Vidroa's 4-stage visual planning engine.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator


class ScriptAnalysis(BaseModel):
    script_summary: str = Field(..., description="Complete narrative summary")
    core_narrative_premise: str = Field(..., description="Central thematic question or premise")
    genre_and_tone: str = Field(..., description="Genre and emotional tone")
    historical_or_setting_period: str = Field(..., description="Setting era or epoch")
    narrative_beats: List[Dict[str, Any]] = Field(default_factory=list)
    facts_and_claims: List[Dict[str, Any]] = Field(default_factory=list)
    continuity_bible: Dict[str, Any] = Field(default_factory=dict)
    temporal_and_causal_structure: Dict[str, Any] = Field(default_factory=dict)
    visual_planning_constraints: Dict[str, Any] = Field(default_factory=dict)
    thumbnail_headline: Optional[str] = Field(default="", description="High-CTR 2-4 word uppercase headline")
    thumbnail_prompt: Optional[str] = Field(default="", description="Dedicated high-CTR visual composition prompt")


class StoryIntelligence(BaseModel):
    """
    Unified persistent Story Intelligence object.
    Holds complete narrative decomposition, character bibles, environment bibles,
    object bibles, timeline, visual continuity rules, and high-CTR thumbnail assets.
    """
    story_summary: str = Field(default="", description="High-level narrative summary")
    core_narrative_premise: str = Field(default="", description="Central narrative premise or dramatic hook")
    genre_and_tone: str = Field(default="", description="Story genre, atmosphere, and emotional tone")
    historical_or_setting_period: str = Field(default="", description="Setting era, epoch, or time period")
    chronological_events: List[str] = Field(default_factory=list, description="Chronological sequence of key events")
    cause_and_effect_flow: List[str] = Field(default_factory=list, description="Causal progression linking events across the narrative arc")
    characters: List[Dict[str, Any]] = Field(default_factory=list, description="Character Bible entries")
    environments: List[Dict[str, Any]] = Field(default_factory=list, description="Environment Bible entries")
    objects_and_props: List[Dict[str, Any]] = Field(default_factory=list, description="Object and Prop Bible entries")
    visual_style_bible: Dict[str, Any] = Field(default_factory=dict, description="Color palette, lighting, camera guidelines")
    visual_continuity_rules: List[str] = Field(default_factory=list, description="Authoritative continuity and consistency rules")
    visual_constraints: Dict[str, Any] = Field(default_factory=dict, description="must_visualize, must_not_visualize, high_risk_repetition")
    narrative_beats: List[Dict[str, Any]] = Field(default_factory=list, description="Scene-level narrative beats or requirements")
    thumbnail_headline: Optional[str] = Field(default="", description="High-CTR 2-4 word uppercase headline")
    thumbnail_prompt: Optional[str] = Field(default="", description="Dedicated high-CTR visual composition prompt")
    raw_response: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Raw extraction payload")

    def to_story_analysis(self):
        """Converts to legacy StoryAnalysis for UI compatibility."""
        from app.models.scene import (
            StoryAnalysis,
            StoryContinuity,
            CharacterContinuity,
            LocationContinuity,
            ObjectContinuity,
            TimePeriodContinuity,
        )
        chars = [
            CharacterContinuity(
                name=c.get("name", "Unknown"),
                role=c.get("role", ""),
                physical_description=c.get("physical_description", c.get("appearance", "")),
                clothing=c.get("clothing_and_gear", c.get("costume", "")),
                key_features=c.get("consistency_rules", "")
            )
            for c in self.characters
        ]
        locs = [
            LocationContinuity(
                name=l.get("name", "Unknown"),
                architectural_style=l.get("architectural_style", l.get("description", "")),
                environmental_features=l.get("environmental_features", l.get("environment_details", "")),
                lighting_mood=l.get("lighting_and_atmosphere", l.get("lighting_default", ""))
            )
            for l in self.environments
        ]
        objs = [
            ObjectContinuity(
                name=o.get("name", "Unknown"),
                visual_description=o.get("visual_description", o.get("description", "")),
                significance=o.get("significance", o.get("symbolic_or_narrative_meaning", ""))
            )
            for o in self.objects_and_props
        ]
        time_cont = TimePeriodContinuity(
            era=self.historical_or_setting_period or "Modern Era",
            decade_or_year="",
            technology_level="",
            lighting_methods=self.visual_style_bible.get("lighting_rules", ""),
            wardrobe_norms="",
            atmosphere_notes=self.visual_style_bible.get("color_palette", "")
        )
        cont = StoryContinuity(
            character_continuity_needed=bool(chars),
            characters=chars,
            location_continuity_needed=bool(locs),
            locations=locs,
            object_continuity_needed=bool(objs),
            key_objects=objs,
            time_period=time_cont
        )
        return StoryAnalysis(
            story_summary=self.story_summary,
            major_historical_events=self.chronological_events,
            cause_and_effect_flow=self.cause_and_effect_flow,
            historical_uncertainties=[],
            narrative_beats=self.narrative_beats,
            facts_and_claims=[],
            continuity=cont,
            visual_tone_notes=self.genre_and_tone,
            thumbnail_headline=self.thumbnail_headline or "",
            thumbnail_prompt=self.thumbnail_prompt or ""
        )

    def to_script_analysis(self, story_text: str = "") -> ScriptAnalysis:
        """Converts to ScriptAnalysis for pipeline backwards-compatibility."""
        return ScriptAnalysis(
            script_summary=self.story_summary,
            core_narrative_premise=self.core_narrative_premise,
            genre_and_tone=self.genre_and_tone,
            historical_or_setting_period=self.historical_or_setting_period,
            narrative_beats=self.narrative_beats,
            facts_and_claims=[],
            continuity_bible={
                "characters": self.characters,
                "locations": self.environments,
                "objects_and_motifs": self.objects_and_props,
            },
            temporal_and_causal_structure={
                "chronological_order": " -> ".join(self.chronological_events) if self.chronological_events else "Linear chronological order",
                "flashbacks_or_nonlinear_elements": [],
                "causal_chain": self.cause_and_effect_flow,
            },
            visual_planning_constraints={
                "must_visualize": self.visual_constraints.get("must_visualize", []),
                "must_not_visualize": self.visual_constraints.get("must_not_visualize", []),
                "high_risk_repetition_concepts": self.visual_constraints.get("high_risk_repetition", []),
            },
            thumbnail_headline=self.thumbnail_headline or "",
            thumbnail_prompt=self.thumbnail_prompt or ""
        )


class ScheduledScene(BaseModel):
    scene_id: str = Field(..., description="Unique scene ID, e.g. '001'")
    beat_id: str = Field(..., description="Matching beat ID")
    start_time: float = Field(..., ge=0.0, description="Start timestamp in seconds")
    end_time: float = Field(..., ge=0.0, description="End timestamp in seconds")
    duration: float = Field(..., ge=0.0, description="Duration in seconds")
    narration_text: str = Field(..., description="Exact narration segment accompanying this scene")
    visual_summary: str = Field(..., description="Concise visual summary of shot")
    scheduling_reason: str = Field(default="", description="Reason for boundary placement")
    alignment_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Alignment confidence score")
    index: Optional[int] = Field(default=None, description="Sequential 1-based scene index")
    source_narrative_beat_ids: List[str] = Field(default_factory=list, description="IDs of narrative beats contributing to this scene")
    source_visual_beat_ids: List[str] = Field(default_factory=list, description="IDs of visual beats contributing to this scene")
    source_word_start: Optional[int] = Field(default=None, description="Start index in tokenized narration word array")
    source_word_end: Optional[int] = Field(default=None, description="End index in tokenized narration word array")
    character_ids: List[str] = Field(default_factory=list, description="Character IDs appearing in this scene")
    location_id: Optional[str] = Field(default=None, description="Primary location ID for this scene")
    chronological_order: Optional[int] = Field(default=None, description="Chronological sequence order")

    @model_validator(mode="after")
    def sync_duration(self):
        calculated = round(self.end_time - self.start_time, 3)
        if calculated < 0:
            raise ValueError(f"Scene {self.scene_id} end_time ({self.end_time}) < start_time ({self.start_time})")
        if abs(self.duration - calculated) > 0.05:
            self.duration = calculated
        return self


class ScheduledStoryboard(BaseModel):
    scenes: List[ScheduledScene] = Field(default_factory=list)
    total_duration: float = Field(default=0.0, ge=0.0)
