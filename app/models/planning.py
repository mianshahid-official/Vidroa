"""
Structured Pydantic data models for the complete 8-stage visual planning engine.
Conforms strictly to the Google Antigravity Visual Planning Specification.
"""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator


# ============================================================================
# STAGE 1: SCRIPT ANALYSIS & CONTINUITY BIBLE
# ============================================================================

class NarrativeBeat(BaseModel):
    beat_id: str = Field(..., description="Unique beat identifier, e.g. 'BEAT-001'")
    narration_reference: str = Field(..., description="Exact quotation from the script")
    story_fact: str = Field(..., description="Core narrative fact or dramatic development")
    narrative_function: str = Field(..., description="Function: hook, exposition, complication, climax, reflection, etc.")
    visual_potential: str = Field(..., description="Visual opportunities and key imagery suggested by this beat")
    pacing_weight: Literal["high", "medium", "low"] = Field(default="medium", description="Rhythm/pacing importance")


class FactClaim(BaseModel):
    claim_id: str = Field(..., description="Unique claim identifier, e.g. 'CLAIM-001'")
    statement: str = Field(..., description="Specific claim made in narration")
    certainty: Literal["established_fact", "interpretive_claim", "dramatic_flourish"] = Field(
        default="established_fact",
        description="Historical or factual certainty level"
    )
    visual_implication: str = Field(..., description="How this certainty influences visual depiction")


class CharacterEntity(BaseModel):
    name: str = Field(..., description="Name or identifier of character")
    role: str = Field(..., description="Role in story (e.g. Commander, Defender)")
    appearance: str = Field(..., description="Detailed physical features: age, ethnicity, facial hair, build")
    costume: str = Field(..., description="Period-accurate garments, armor, textures, colors")
    recurring_motifs: List[str] = Field(default_factory=list, description="Visual motifs associated with character")
    transformations: List[str] = Field(default_factory=list, description="Changes over narrative arc (e.g. wounded, aging, travel-worn)")


class LocationEntity(BaseModel):
    name: str = Field(..., description="Name of location")
    description: str = Field(..., description="Architectural or geographical character")
    environment_details: str = Field(..., description="Specific environmental conditions, terrain, weather, materials")
    lighting_default: str = Field(..., description="Default lighting scheme appropriate for setting")
    historical_or_setting_constraints: str = Field(..., description="Constraints to prevent anachronisms")


class ObjectEntity(BaseModel):
    name: str = Field(..., description="Name of key artifact, tool, or weapon")
    description: str = Field(..., description="Material composition, craftsmanship, wear")
    symbolic_or_narrative_meaning: str = Field(..., description="Narrative significance or thematic weight")


class ContinuityBible(BaseModel):
    characters: List[CharacterEntity] = Field(default_factory=list)
    locations: List[LocationEntity] = Field(default_factory=list)
    objects_and_motifs: List[ObjectEntity] = Field(default_factory=list)


class TemporalCausalStructure(BaseModel):
    chronological_order: str = Field(..., description="Narrative chronological progression")
    flashbacks_or_nonlinear_elements: List[str] = Field(default_factory=list, description="Non-linear elements or memories")
    causal_chain: List[str] = Field(default_factory=list, description="Cause-and-effect progression through narrative")


class PlanningConstraints(BaseModel):
    must_visualize: List[str] = Field(default_factory=list, description="Critical moments that must receive visual focus")
    must_not_visualize: List[str] = Field(default_factory=list, description="Elements to avoid (e.g. anachronisms, misleading symbols)")
    high_risk_repetition_concepts: List[str] = Field(default_factory=list, description="Concepts that risk repetitive scenes")


class ScriptAnalysis(BaseModel):
    script_summary: str = Field(..., description="Complete narrative summary")
    core_narrative_premise: str = Field(..., description="Central thematic question or premise")
    genre_and_tone: str = Field(..., description="Genre and emotional tone")
    historical_or_setting_period: str = Field(..., description="Setting era or epoch")
    narrative_beats: List[NarrativeBeat] = Field(default_factory=list)
    facts_and_claims: List[FactClaim] = Field(default_factory=list)
    continuity_bible: ContinuityBible = Field(default_factory=ContinuityBible)
    temporal_and_causal_structure: TemporalCausalStructure
    visual_planning_constraints: PlanningConstraints
    thumbnail_headline: Optional[str] = Field(default="", description="High-CTR 2-4 word uppercase headline")
    thumbnail_prompt: Optional[str] = Field(default="", description="Dedicated high-CTR visual composition prompt")


# ============================================================================
# STAGE 3: NARRATION-ALIGNED VISUAL PLANNING
# ============================================================================

class VisualBeat(BaseModel):
    beat_id: str = Field(..., description="Unique beat reference or sequence ID, e.g. 'VB-001'")
    source_beat_ids: List[str] = Field(default_factory=list, description="IDs of source narrative beats, e.g. ['BEAT-001']")
    exact_narration_segment: str = Field(..., description="Exact spoken script words this visual depicts")
    narrative_purpose: str = Field(..., description="Why this visual is chosen for this spoken moment")
    primary_visual_concept: str = Field(..., description="Concrete physical scene, subjects, action, and setting")
    what_new_information_is_shown: str = Field(..., description="New visual fact, action, or consequence shown")
    why_this_is_not_repetitive: str = Field(..., description="Distinction from preceding and subsequent visuals")
    composition: str = Field(..., description="Shot framing, camera angle, and focal hierarchy")
    lighting_and_atmosphere: str = Field(..., description="Atmospheric depth, key lighting source, mood")
    continuity_references: List[str] = Field(default_factory=list, description="Referenced characters, locations, objects")


class VisualBeatPlan(BaseModel):
    visual_beats: List[VisualBeat] = Field(default_factory=list)


# ============================================================================
# STAGE 4: TEMPORAL SCENE SCHEDULING
# ============================================================================

class ScheduledScene(BaseModel):
    scene_id: str = Field(..., description="Unique scene ID, e.g. '001'")
    beat_id: str = Field(..., description="Matching beat ID from VisualBeatPlan")
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


# ============================================================================
# STAGE 5: IMAGE PROMPT GENERATION
# ============================================================================

class GeneratedPromptItem(BaseModel):
    scene_id: str = Field(..., description="Corresponding scene ID")
    prompt: str = Field(..., description="Full image prompt in user's selected style")
    negative_prompt: Optional[str] = Field(default=None, description="Negative prompt constraints")
    shot_type: str = Field(default="", description="Shot type: wide, medium, close-up, macro, aerial")
    subject: str = Field(default="", description="Primary physical subject")
    environment: str = Field(default="", description="Environment and architectural context")
    lighting: str = Field(default="", description="Lighting setup and source")
    composition: str = Field(default="", description="Compositional balance and depth")
    style_application: str = Field(default="", description="How the user-selected visual style was applied")


class GeneratedPromptBatch(BaseModel):
    prompts: List[GeneratedPromptItem] = Field(default_factory=list)


# ============================================================================
# STAGE 6: STORYBOARD QUALITY AUDIT
# ============================================================================

class CategoryScores(BaseModel):
    narration_alignment: float = Field(..., ge=0.0, le=100.0)
    visual_progression: float = Field(..., ge=0.0, le=100.0)
    temporal_pacing: float = Field(..., ge=0.0, le=100.0)
    continuity: float = Field(..., ge=0.0, le=100.0)
    style_fidelity: float = Field(..., ge=0.0, le=100.0)
    prompt_quality: float = Field(..., ge=0.0, le=100.0)


class RepetitionFinding(BaseModel):
    scene_ids: List[str] = Field(..., description="List of scene IDs that are visually repetitive")
    reason: str = Field(..., description="Why these scenes duplicate visual concept/meaning")
    severity: str = Field(default="warning", description="Severity: critical, warning, minor")


class TimingFinding(BaseModel):
    scene_id: str = Field(..., description="Scene ID with timing defect")
    issue: str = Field(..., description="Issue description (>8.0s, negative, gap, or inappropriate <2.0s)")
    duration: float = Field(..., description="Recorded duration")


class AlignmentFinding(BaseModel):
    scene_id: str = Field(..., description="Scene ID where visual diverges from narration")
    issue: str = Field(..., description="Description of narrative divergence")


class SceneRepairInstruction(BaseModel):
    scene_id: str = Field(..., description="Scene ID requiring correction")
    problem: str = Field(..., description="Specific failure detected")
    required_change: str = Field(..., description="Actionable change required")
    suggested_visual_direction: str = Field(..., description="Recommended distinct visual concept")


class StoryboardAuditReport(BaseModel):
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Overall quality score (0-100)")
    category_scores: CategoryScores
    repetition_findings: List[RepetitionFinding] = Field(default_factory=list)
    timing_findings: List[TimingFinding] = Field(default_factory=list)
    alignment_findings: List[AlignmentFinding] = Field(default_factory=list)
    scene_repairs: List[SceneRepairInstruction] = Field(default_factory=list)
    final_recommendation: Literal["APPROVED", "NEEDS_REPAIR", "CRITICAL_FAILURE"] = Field(...)


# ============================================================================
# STAGE 7: AUTOMATIC REPLANNING
# ============================================================================

class RepairedScene(BaseModel):
    scene_id: str = Field(..., description="Scene ID repaired")
    beat_id: str = Field(..., description="Matching beat ID")
    narration_text: str = Field(..., description="Spoken narration text")
    new_visual_concept: str = Field(..., description="Substantially new visual concept replacing failed concept")
    what_changed: str = Field(..., description="Specific narrative and visual differences introduced")
    repaired_prompt: str = Field(..., description="Complete regenerated image prompt adhering to selected style")
    start_time: float = Field(..., ge=0.0)
    end_time: float = Field(..., ge=0.0)
    duration: float = Field(..., ge=0.0)
    source_narrative_beat_ids: List[str] = Field(default_factory=list, description="IDs of source narrative beats")
    source_visual_beat_ids: List[str] = Field(default_factory=list, description="IDs of source visual beats")

    @model_validator(mode="after")
    def sync_dur(self):
        calc = round(self.end_time - self.start_time, 3)
        if calc < 0:
            raise ValueError(f"Repaired scene {self.scene_id} end < start")
        if abs(self.duration - calc) > 0.05:
            self.duration = calc
        return self


class ReplanningResult(BaseModel):
    repaired_scenes: List[RepairedScene] = Field(default_factory=list)
    unresolved_issues: List[str] = Field(default_factory=list)
    needs_reaudit: bool = Field(default=True)


# ============================================================================
# STAGE 8: FINAL STORYBOARD VALIDATION
# ============================================================================

class StoryboardValidationResult(BaseModel):
    is_valid: bool = Field(..., description="Whether complete storyboard satisfies all rules")
    total_scenes: int = Field(default=0)
    total_duration: float = Field(default=0.0)
    max_scene_duration: float = Field(default=0.0)
    min_scene_duration: float = Field(default=0.0)
    has_gaps: bool = Field(default=False)
    has_overlaps: bool = Field(default=False)
    scenes_exceeding_8s: List[str] = Field(default_factory=list)
    uncovered_narration_gaps: List[str] = Field(default_factory=list)
    repetition_alerts: List[str] = Field(default_factory=list)
    validation_summary: str = Field(default="")

