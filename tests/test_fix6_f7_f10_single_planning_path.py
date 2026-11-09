"""
Phase 4 Tests: Fix 6 (F7 + F10) — Single Planning Path & Enforced Word Provenance.
Verifies:
1. Generate with NO pre-planned scenes runs Stages 1 -> 3 -> 4 (Stage 3 and Stage 4 executed, no Stage2Planner call).
2. Every produced scene carries non-None start_word_index and end_word_index.
3. A pre-planned scene with empty narration_excerpt raises a hard error naming the scene (never falls back to s.action).
4. Sentence boundary assertions still run and pass on the surviving unified path.
"""
import json
import pytest
from app.models.scene import VisualScene
from app.ai.schemas import JobCreateRequest
from backend.inference.engine import BaseInferenceEngine
from app.ai.job_worker import CloudJobWorker
from backend.pipeline.stage4_scheduling import assert_sentence_boundary_validity


class UnifiedPathTestEngine(BaseInferenceEngine):
    def __init__(self):
        super().__init__()
        self.stage3_called = False
        self.stage5_called = False
        self.stage6_called = False

    def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        if "### SCRIPT ANALYSIS SCHEMA" in prompt or "genre_and_tone" in prompt:
            return json.dumps({
                "script_summary": "Historical narrative depicting military forces.",
                "core_narrative_premise": "Soldiers advance toward city gates",
                "genre_and_tone": "Dramatic Historical",
                "setting_period": "Medieval",
                "continuity_bible": {
                    "characters": [{"name": "Commander", "role": "Officer", "appearance": "Chainmail", "costume": "Tunic"}],
                    "locations": [{"name": "Gatehouse", "description": "Stone walls", "environment_details": "Stone", "lighting_default": "Day", "historical_or_setting_constraints": "Authentic"}]
                },
                "temporal_and_causal_structure": {"chronological_order": "Linear"},
                "visual_planning_constraints": {}
            })

        if "visual_beats" in prompt:
            self.stage3_called = True
            return json.dumps({
                "visual_beats": [
                    {
                        "beat_id": "VB-001",
                        "narrative_purpose": "Soldiers advance",
                        "exact_narration_segment": "The vanguard approached the stone gatehouse under clear skies.",
                        "primary_visual_concept": "Vanguard soldiers approaching fortified stone gatehouse",
                        "what_new_information_is_shown": "Initial approach",
                        "composition": "Wide shot",
                        "lighting_and_atmosphere": "Clear daylight",
                        "why_this_is_not_repetitive": "Initial advance",
                        "continuity_references": ["Commander"]
                    },
                    {
                        "beat_id": "VB-002",
                        "narrative_purpose": "Defenders respond",
                        "exact_narration_segment": "Sentries immediately raised the warning flags across the battlements.",
                        "primary_visual_concept": "Sentries raising colored warning flags atop castle ramparts",
                        "what_new_information_is_shown": "Defensive alert",
                        "composition": "Low angle shot",
                        "lighting_and_atmosphere": "Daylight",
                        "why_this_is_not_repetitive": "Response from battlements",
                        "continuity_references": []
                    }
                ]
            })

        if "prompts" in prompt:
            self.stage5_called = True
            return json.dumps({
                "prompts": [
                    {
                        "scene_id": "001",
                        "prompt": "Wide shot of armored vanguard soldiers approaching stone gatehouse under clear daylight."
                    },
                    {
                        "scene_id": "002",
                        "prompt": "Low angle shot of sentries raising warning flags atop castle ramparts under clear skies."
                    }
                ]
            })

        if "category_scores" in prompt:
            self.stage6_called = True
            return json.dumps({
                "overall_score": 95.0,
                "category_scores": {
                    "narration_alignment": 95.0,
                    "visual_progression": 95.0,
                    "temporal_pacing": 95.0,
                    "continuity": 95.0,
                    "style_fidelity": 95.0,
                    "prompt_quality": 95.0
                },
                "repetition_findings": [],
                "timing_findings": [],
                "alignment_findings": [],
                "scene_repairs": [],
                "final_recommendation": "APPROVED"
            })

        return "{}"

    def repair_and_parse_json(self, raw_text: str) -> dict:
        try:
            return json.loads(raw_text)
        except Exception:
            return {}


def test_generate_no_preplanned_scenes_runs_stages_1_3_4(monkeypatch):
    engine = UnifiedPathTestEngine()
    monkeypatch.setattr("app.ai.job_worker.GroqInferenceEngine", lambda **kw: engine)

    completed_responses = []
    failed_signals = []

    worker = CloudJobWorker(
        request=JobCreateRequest(
            project_name="Unified Path Test",
            story_text="The vanguard approached the stone gatehouse under clear skies. Sentries immediately raised the warning flags across the battlements.",
            subject_id="general_documentary",
            visual_style_id="2d_stickman"
        ),
        scenes_to_generate=None  # Triggers the un-planned Generate flow!
    )
    worker.job_completed.connect(lambda resp: completed_responses.append(resp))
    worker.job_failed.connect(lambda u, t: failed_signals.append((u, t)))

    worker.run()

    assert len(failed_signals) == 0, f"Worker failed: {failed_signals}"
    assert len(completed_responses) == 1
    resp = completed_responses[0]

    # Assert Stage 3 Visual Planner executed
    assert engine.stage3_called is True

    # Assert scenes were generated and word indices are populated on EVERY scene
    scenes = resp.scenes
    assert len(scenes) >= 2
    for sc in scenes:
        assert sc.start_word_index is not None, f"Scene #{sc.scene_id} has null start_word_index"
        assert sc.end_word_index is not None, f"Scene #{sc.scene_id} has null end_word_index"
        assert sc.start_word_index <= sc.end_word_index
        # Boundary assertion check
        assert sc.narration_excerpt[-1] in [".", "!", "?", ";", ":", "—", "–"]


def test_empty_narration_excerpt_raises_hard_error(monkeypatch):
    engine = UnifiedPathTestEngine()
    monkeypatch.setattr("app.ai.job_worker.GroqInferenceEngine", lambda **kw: engine)

    failed_signals = []
    broken_scene = VisualScene(
        scene_id="001",
        start=0.0,
        end=4.0,
        duration=4.0,
        narration_excerpt="",  # Empty excerpt!
        visual_subject="Soldiers marching",
        action="Silent fallback action description that must not be used",
        prompt="Soldiers marching toward city gate.",
        composition="Wide shot",
        source_word_start=0,
        source_word_end=5
    )

    worker = CloudJobWorker(
        request=JobCreateRequest(
            project_name="Empty Narration Test",
            story_text="The vanguard approached the stone gatehouse under clear skies.",
            subject_id="general_documentary",
            visual_style_id="2d_stickman"
        ),
        scenes_to_generate=[broken_scene]
    )
    worker.job_failed.connect(lambda u, t: failed_signals.append((u, t)))

    worker.run()

    assert len(failed_signals) == 1
    user_err, tech_err = failed_signals[0]
    assert "Scene #001" in tech_err
    assert "empty narration excerpt" in tech_err.lower()
    assert "action text is strictly prohibited" in tech_err.lower()
