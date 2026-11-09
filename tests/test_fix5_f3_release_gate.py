"""
Phase 3 Tests: Fix 5 (F3) — Release Gate Enforcement.
Verifies:
1. Stage8FinalValidator blocks delivery (is_valid=False) when audit_report has NEEDS_REPAIR, score < 85, or alignment findings.
2. Stage8FinalValidator approves delivery (is_valid=True) when audit_report is APPROVED with score >= 85 and no alignment findings.
3. PipelineOrchestrator marks job FAILED (never COMPLETED) when audit rejects board after 3 replan rounds.
4. PipelineOrchestrator marks job COMPLETED when audit is APPROVED and validation passes.
5. CloudJobWorker emits job_failed when audit rejects board, withholding COMPLETED status while preserving valid scenes.
"""
import json
import pytest
from pathlib import Path
from app.models.job import JobStatus, JobStage
from app.models.planning import (
    StoryboardAuditReport,
    CategoryScores,
    AlignmentFinding,
    SceneRepairInstruction
)
from app.models.scene import VisualScene
from app.ai.schemas import JobCreateRequest
from backend.jobs.store import JobStore
from backend.inference.engine import BaseInferenceEngine
from backend.pipeline.stage8_validation import Stage8FinalValidator
from backend.pipeline.orchestrator import PipelineOrchestrator
from app.ai.job_worker import CloudJobWorker


class CannedOrchestratorEngine(BaseInferenceEngine):
    def __init__(self, audit_recommendation: str = "APPROVED", audit_score: float = 95.0, alignment_findings: list = None):
        super().__init__()
        self.audit_rec = audit_recommendation
        self.audit_score = audit_score
        self.align_findings = alignment_findings or []

    def generate_text(self, prompt: str, system_prompt: str = None, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        # Stage 1 Analysis response
        if "### SCRIPT ANALYSIS SCHEMA" in prompt or "genre_and_tone" in prompt:
            return json.dumps({
                "script_summary": "Historical narrative depicting military defense.",
                "core_narrative_premise": "Defenders hold the fortress walls",
                "genre_and_tone": "Dramatic Historical",
                "setting_period": "Medieval",
                "continuity_bible": {
                    "characters": [{"name": "Captain", "role": "Commander", "appearance": "Plate armor", "costume": "Tunic"}],
                    "locations": [{"name": "Gate", "description": "Stone gate", "environment_details": "Stone", "lighting_default": "Day", "historical_or_setting_constraints": "None"}]
                },
                "temporal_and_causal_structure": {"chronological_order": "Linear"},
                "visual_planning_constraints": {}
            })

        # Stage 3 Visual Beats response
        if "visual_beats" in prompt:
            return json.dumps({
                "visual_beats": [
                    {
                        "beat_id": "VB-001",
                        "narrative_purpose": "Soldiers advance",
                        "exact_narration_segment": "The infantry units advanced toward the fortified iron gates under a hail of arrows.",
                        "primary_visual_concept": "Infantry units advancing on city gates with shields raised under hail of arrows",
                        "what_new_information_is_shown": "Initial assault formation",
                        "composition": "Wide establishing shot",
                        "lighting_and_atmosphere": "Overcast sky",
                        "why_this_is_not_repetitive": "Initial approach sequence",
                        "continuity_references": ["Captain"]
                    },
                    {
                        "beat_id": "VB-002",
                        "narrative_purpose": "Archers defend",
                        "exact_narration_segment": "Archers positioned along the upper battlements fired coordinated volleys.",
                        "primary_visual_concept": "Archers on battlements releasing arrows downward into the valley",
                        "what_new_information_is_shown": "Defensive counter-fire",
                        "composition": "Medium angle shot",
                        "lighting_and_atmosphere": "Overcast sky",
                        "why_this_is_not_repetitive": "Transition to aerial defensive volley",
                        "continuity_references": []
                    }
                ]
            })

        # Stage 5 Prompts response
        if "prompts" in prompt:
            return json.dumps({
                "prompts": [
                    {
                        "scene_id": "001",
                        "prompt": "Dramatic wide shot of armored infantry units advancing toward fortified iron gates with shields raised under hail of arrows, dust and grit."
                    },
                    {
                        "scene_id": "002",
                        "prompt": "Medium shot of archers positioned along high stone battlements drawing bows and firing arrow volleys downward."
                    }
                ]
            })

        # Stage 6 Audit response
        if "category_scores" in prompt:
            return json.dumps({
                "overall_score": self.audit_score,
                "category_scores": {
                    "narration_alignment": self.audit_score,
                    "visual_progression": self.audit_score,
                    "temporal_pacing": self.audit_score,
                    "continuity": self.audit_score,
                    "style_fidelity": self.audit_score,
                    "prompt_quality": self.audit_score
                },
                "repetition_findings": [],
                "timing_findings": [],
                "alignment_findings": self.align_findings,
                "scene_repairs": [{"scene_id": "001", "problem": "Mismatch", "required_change": "Fix", "suggested_visual_direction": "Fix"}] if self.align_findings else [],
                "final_recommendation": self.audit_rec
            })

        # Stage 7 Replanner response
        if "repaired_prompts" in prompt:
            return json.dumps({
                "repaired_prompts": [
                    {
                        "scene_id": "001",
                        "prompt": "Repaired dramatic wide shot of infantry units advancing toward fortified iron gates."
                    }
                ]
            })

        return "{}"

    def repair_and_parse_json(self, raw_text: str) -> dict:
        try:
            return json.loads(raw_text)
        except Exception:
            return {}


def _create_valid_scene() -> VisualScene:
    return VisualScene(
        scene_id="001",
        start=0.0,
        end=4.0,
        duration=4.0,
        narration_excerpt="The infantry units advanced toward the fortified iron gates under a hail of arrows.",
        visual_subject="Infantry units advancing on city gates",
        prompt="Dramatic wide shot of armored infantry units advancing toward fortified iron gates with shields raised under hail of arrows, dust and grit.",
        composition="Wide shot",
        source_word_start=0,
        source_word_end=12,
        chronological_order=1
    )


def test_stage8_validator_blocks_on_needs_repair_audit():
    scene = _create_valid_scene()
    bad_audit = StoryboardAuditReport(
        overall_score=72.0,
        category_scores=CategoryScores(
            narration_alignment=65.0,
            visual_progression=75.0,
            temporal_pacing=95.0,
            continuity=80.0,
            style_fidelity=95.0,
            prompt_quality=75.0
        ),
        repetition_findings=[],
        timing_findings=[],
        alignment_findings=[AlignmentFinding(scene_id="001", issue="Narration-Prompt mismatch")],
        scene_repairs=[SceneRepairInstruction(scene_id="001", problem="Mismatch", required_change="Depict gates", suggested_visual_direction="Depict gates")],
        final_recommendation="NEEDS_REPAIR"
    )

    val_res = Stage8FinalValidator.execute(
        scenes=[scene],
        audit_report=bad_audit
    )

    assert val_res.is_valid is False
    assert "Quality Audit Gate" in val_res.validation_summary
    assert "NEEDS_REPAIR" in val_res.validation_summary
    assert "72.0" in val_res.validation_summary
    assert "#001" in val_res.validation_summary


def test_stage8_validator_approves_on_good_audit():
    scene = _create_valid_scene()
    good_audit = StoryboardAuditReport(
        overall_score=94.0,
        category_scores=CategoryScores(
            narration_alignment=95.0,
            visual_progression=95.0,
            temporal_pacing=95.0,
            continuity=95.0,
            style_fidelity=95.0,
            prompt_quality=95.0
        ),
        repetition_findings=[],
        timing_findings=[],
        alignment_findings=[],
        scene_repairs=[],
        final_recommendation="APPROVED"
    )

    val_res = Stage8FinalValidator.execute(
        scenes=[scene],
        audit_report=good_audit
    )

    assert val_res.is_valid is True
    assert "RELEASE GATE: PASSED" in val_res.validation_summary


def test_orchestrator_fails_job_when_audit_rejects_board():
    store = JobStore()
    job_id = "test-f3-fail-job"
    store.create_job(job_id=job_id, project_id="test-proj", settings={})

    engine = CannedOrchestratorEngine(
        audit_recommendation="NEEDS_REPAIR",
        audit_score=68.0,
        alignment_findings=[{"scene_id": "001", "issue": "Narration-Prompt mismatch"}]
    )

    request = JobCreateRequest(
        project_name="Test Project",
        story_text="The infantry units advanced toward the fortified iron gates under a hail of arrows. Archers positioned along the upper battlements fired coordinated volleys.",
        subject_id="general_documentary",
        visual_style_id="2d_stickman"
    )

    PipelineOrchestrator.run_pipeline(
        job_id=job_id,
        request=request,
        engine=engine
    )

    job = store.get_job(job_id)
    assert job is not None
    # Must end FAILED, never COMPLETED
    assert job.status == JobStatus.FAILED
    assert "RELEASE GATE FAILED" in (job.error or "")
    assert "Recommendation: NEEDS_REPAIR" in (job.error or "")
    assert "#001" in (job.error or "")
    # Valid scenes are still preserved for inspection
    scenes = store.get_scenes(job_id)
    assert len(scenes) >= 1


def test_orchestrator_completes_job_when_audit_approved():
    store = JobStore()
    job_id = "test-f3-success-job"
    store.create_job(job_id=job_id, project_id="test-proj", settings={})

    engine = CannedOrchestratorEngine(
        audit_recommendation="APPROVED",
        audit_score=95.0,
        alignment_findings=[]
    )

    request = JobCreateRequest(
        project_name="Test Project",
        story_text="The infantry units advanced toward the fortified iron gates under a hail of arrows. Archers positioned along the upper battlements fired coordinated volleys.",
        subject_id="general_documentary",
        visual_style_id="2d_stickman"
    )

    PipelineOrchestrator.run_pipeline(
        job_id=job_id,
        request=request,
        engine=engine
    )

    job = store.get_job(job_id)
    assert job is not None
    assert job.status == JobStatus.COMPLETED
    assert "Complete visual planning finished successfully" in job.progress.message
    assert "Audit score:" in job.progress.message


def test_job_worker_fails_on_audit_rejection(monkeypatch):
    failed_signals = []
    completed_signals = []

    valid_scene = _create_valid_scene()

    worker = CloudJobWorker(
        request=JobCreateRequest(
            project_name="Test Worker",
            story_text="The infantry units advanced toward the fortified iron gates under a hail of arrows. Archers positioned along the upper battlements fired coordinated volleys.",
            subject_id="general_documentary",
            visual_style_id="2d_stickman"
        ),
        scenes_to_generate=[valid_scene]
    )
    worker.job_failed.connect(lambda user_msg, tech_msg: failed_signals.append((user_msg, tech_msg)))
    worker.job_completed.connect(lambda resp: completed_signals.append(resp))

    engine = CannedOrchestratorEngine(
        audit_recommendation="NEEDS_REPAIR",
        audit_score=65.0,
        alignment_findings=[{"scene_id": "001", "issue": "Narration-Prompt mismatch"}]
    )

    monkeypatch.setattr("app.ai.job_worker.GroqInferenceEngine", lambda **kw: engine)
    worker.run()

    assert len(failed_signals) == 1
    assert len(completed_signals) == 0
    user_err, tech_err = failed_signals[0]
    assert "Stage 8 Release Gate rejected storyboard" in user_err
    assert "Recommendation: NEEDS_REPAIR" in tech_err
    assert "#001" in tech_err
