"""
Data models for visual scenes, storyboard units, and continuity specifications.
"""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CharacterContinuity(BaseModel):
    name: str
    role: Optional[str] = None
    physical_description: str
    clothing: Optional[str] = None
    key_features: Optional[str] = None


class LocationContinuity(BaseModel):
    name: str
    architectural_style: Optional[str] = None
    environmental_features: str
    lighting_mood: Optional[str] = None


class ObjectContinuity(BaseModel):
    name: str
    visual_description: str
    significance: Optional[str] = None


class TimePeriodContinuity(BaseModel):
    era: str = Field(default="Unspecified", description="Specific historical era or epoch")
    decade_or_year: Optional[str] = Field(default=None, description="Estimated year or decade")
    technology_level: str = Field(default="", description="Available technology, transport, machinery, communication")
    lighting_methods: str = Field(default="", description="Authentic historical lighting sources (gaslamps, oil lanterns, candles, sunlight)")
    wardrobe_norms: str = Field(default="", description="Period-accurate fabrics, hats, collars, workwear conventions")
    atmosphere_notes: str = Field(default="", description="Sensory and atmospheric period details")

    @property
    def is_photographic_era(self) -> bool:
        """Returns True only if the historical setting is within the photographic age (circa 1845 onward)."""
        import re
        text = f"{self.era} {self.decade_or_year or ''}".lower()
        years = [int(y) for y in re.findall(r"\b(1\d{3}|20\d{2})\b", text)]
        if years:
            return any(y >= 1845 for y in years)
        pre_photo = ["ancient", "rome", "roman", "greece", "greek", "medieval", "middle ages", "1453", "crusade", "byzantine", "renaissance", "napoleonic", "1700", "1600", "1500", "1400", "bc", "b.c.", "antiquity"]
        if any(k in text for k in pre_photo):
            return False
        photo_keywords = ["victorian", "edwardian", "civil war", "industrial", "185", "186", "187", "188", "189", "190", "191", "192", "ww1", "ww2", "world war"]
        return any(k in text for k in photo_keywords)


class StoryContinuity(BaseModel):
    character_continuity_needed: bool = True
    characters: List[CharacterContinuity] = Field(default_factory=list)
    location_continuity_needed: bool = True
    locations: List[LocationContinuity] = Field(default_factory=list)
    object_continuity_needed: bool = True
    key_objects: List[ObjectContinuity] = Field(default_factory=list)
    time_period: Optional[TimePeriodContinuity] = None


class VisualScene(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scene_id: str = Field(..., description="Unique formatted scene identifier, e.g. '001'")
    start: float = Field(..., ge=0.0, description="Start timestamp in seconds")
    end: float = Field(..., ge=0.0, description="End timestamp in seconds")
    duration: float = Field(..., ge=0.0, description="Duration in seconds")
    start_word_index: Optional[int] = Field(default=None, description="Index of first spoken word in narration array")
    end_word_index: Optional[int] = Field(default=None, description="Index of last spoken word in narration array")
    start_word: Optional[str] = Field(default=None, description="First spoken word")
    end_word: Optional[str] = Field(default=None, description="Last spoken word")
    narration_excerpt: str = Field(default="", description="Spoken narration text corresponding to this scene")
    visual_subject: str = Field(..., description="Concrete visual subject of the scene")
    action: str = Field(default="", description="Specific physical event or action taking place in frame")
    environment: str = Field(default="", description="Specific physical environment, architecture, terrain")
    composition: str = Field(default="", description="Composition framing, camera angle, and focal point")
    emotional_tone: str = Field(default="", description="Dramatic mood or emotional beat")
    confidence: str = Field(default="well_supported_reconstruction", alias="historical_confidence", description="documented | well_supported_reconstruction | artistic_interpretation | uncertain")
    depicted_event: Optional[str] = Field(default="", alias="historical_event", description="The specific narrative event from story decomposition this scene depicts")
    transition_to_next_scene: Optional[str] = Field(default="", description="Visual or causal transition to next scene")
    visual_modality: str = Field(default="cinematic_scene", description="Visual type: cinematic_scene, infographic_chart, blueprint_schematic, historical_document, tactical_map, data_counter")
    visual_purpose: Optional[str] = Field(default="", description="Why this visual accompanies this narration moment")
    framing_suggestion: Optional[str] = Field(default="", description="Recommended camera framing and angle")
    prompt: str = Field(default="", description="Full generated image generation prompt")
    image_path: Optional[str] = Field(default=None, description="Absolute path to generated image file on disk")
    continuity_tags: List[str] = Field(default_factory=list, description="Referenced recurring character/location/object tags")
    source_narrative_beat_ids: List[str] = Field(default_factory=list, description="IDs of source narrative beats")
    source_visual_beat_ids: List[str] = Field(default_factory=list, description="IDs of source visual beats")
    character_ids: List[str] = Field(default_factory=list, description="Character IDs appearing in this scene")
    location_id: Optional[str] = Field(default=None, description="Primary location ID")
    chronological_order: Optional[int] = Field(default=None, description="Chronological sequence position")
    index: Optional[int] = Field(default=None, description="1-based scene index")
    is_manually_edited: bool = Field(default=False, description="Whether the prompt or timing was manually modified by user")
    is_validated: bool = Field(default=False, description="Whether this scene has passed timeline and prompt quality checks")
    validation_notes: Optional[str] = Field(default=None, description="Validation feedback or warnings")

    @property
    def historical_confidence(self) -> str:
        return self.confidence

    @historical_confidence.setter
    def historical_confidence(self, val: str) -> None:
        self.confidence = val

    @property
    def historical_event(self) -> Optional[str]:
        return self.depicted_event

    @historical_event.setter
    def historical_event(self, val: Optional[str]) -> None:
        self.depicted_event = val

    @property
    def visual_summary(self) -> str:
        return self.visual_subject

    @model_validator(mode="after")
    def compute_and_verify_duration(self):
        calculated = round(self.end - self.start, 3)
        if calculated < 0:
            raise ValueError(f"Scene {self.scene_id} end time ({self.end}) cannot precede start time ({self.start})")
        # Ensure duration is synced
        if abs(self.duration - calculated) > 0.05:
            self.duration = calculated
        return self


class StoryAnalysis(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    story_summary: str = Field(default="", description="High-level narrative summary")
    major_events: List[str] = Field(default_factory=list, alias="major_historical_events", description="Ordered chronological sequence of major narrative events")
    cause_and_effect_flow: List[str] = Field(default_factory=list, description="Causal progression linking events across the narrative arc")
    uncertainties: List[str] = Field(default_factory=list, alias="historical_uncertainties", description="Contested or undocumented moments that require artistic reconstruction")
    narrative_beats: List[dict] = Field(default_factory=list)
    facts_and_claims: List[dict] = Field(default_factory=list)
    continuity: StoryContinuity = Field(default_factory=StoryContinuity)
    visual_tone_notes: Optional[str] = Field(default="")
    thumbnail_headline: Optional[str] = Field(default="", description="High-CTR 2-4 word uppercase headline for thumbnail")
    thumbnail_prompt: Optional[str] = Field(default="", description="Dedicated high-CTR visual composition prompt for thumbnail")

    @property
    def major_historical_events(self) -> List[str]:
        return self.major_events

    @major_historical_events.setter
    def major_historical_events(self, val: List[str]) -> None:
        self.major_events = val

    @property
    def historical_uncertainties(self) -> List[str]:
        return self.uncertainties

    @historical_uncertainties.setter
    def historical_uncertainties(self, val: List[str]) -> None:
        self.uncertainties = val
