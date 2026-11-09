import pytest
from app.config.settings import AppSettings
from app.models.project import ProjectConfig
from app.ai.schemas import JobCreateRequest
from app.presets.loader import PresetManager
from app.core.validation import TimelineValidator, ValidationSeverity
from app.models.scene import VisualScene, StoryContinuity, TimePeriodContinuity


def test_neutral_app_and_model_defaults():
    settings = AppSettings()
    assert settings.default_subject_id == "general_documentary"
    assert settings.default_visual_style_id == "2d_stickman"

    config = ProjectConfig()
    assert config.subject_id == "general_documentary"
    assert config.visual_style_id == "2d_stickman"

    job_req = JobCreateRequest(project_name="test", story_text="some story")
    assert job_req.subject_id == "general_documentary"
    assert job_req.visual_style_id == "2d_stickman"


def test_preset_manager_neutral_fallbacks():
    PresetManager.initialize()
    unknown_subj = PresetManager.get_subject_by_id("non_existent_subject_123")
    assert unknown_subj is not None
    assert unknown_subj.id == "general_documentary"

    unknown_style = PresetManager.get_style_by_id("non_existent_style_123")
    assert unknown_style is not None
    assert unknown_style.id == "2d_stickman"


def test_anachronism_validation_no_fez_leak():
    # 1. Pre-modern scene with a fez should NOT trigger error/warning
    scenes_with_fez = [
        VisualScene(
            scene_id="1",
            index=1,
            start=0.0,
            end=4.0,
            duration=4.0,
            narration_excerpt="Defenders on the ramparts.",
            visual_subject="Defenders wearing fez hats on the ramparts",
            prompt="Defenders wearing fez on the battlements."
        )
    ]
    continuity_pre_modern = StoryContinuity(
        time_period=TimePeriodContinuity(era="1453 Ottoman Byzantine Era")
    )
    result = TimelineValidator.validate_project(scenes_with_fez, continuity=continuity_pre_modern)
    fez_issues = [i for i in result.issues if "fez" in i.message.lower()]
    assert len(fez_issues) == 0

    # 2. Pre-modern scene with modern smartphone SHOULD trigger anachronism warning
    scenes_with_phone = [
        VisualScene(
            scene_id="1",
            index=1,
            start=0.0,
            end=4.0,
            duration=4.0,
            narration_excerpt="An emperor reading the decree.",
            visual_subject="An emperor checking his smartphone on the throne",
            prompt="Emperor looking at a glowing smartphone screen on a throne."
        )
    ]
    result_phone = TimelineValidator.validate_project(scenes_with_phone, continuity=continuity_pre_modern)
    anachronisms = [i for i in result_phone.issues if i.rule == "ANACHRONISM_DETECTED"]
    assert len(anachronisms) == 1
    assert "modern technology" in anachronisms[0].message.lower()

    # 3. Modern scene with smartphone should NOT trigger anachronism warning
    continuity_modern = StoryContinuity(
        time_period=TimePeriodContinuity(era="2024 Contemporary Era")
    )
    result_modern = TimelineValidator.validate_project(scenes_with_phone, continuity=continuity_modern)
    anachronisms_modern = [i for i in result_modern.issues if i.rule == "ANACHRONISM_DETECTED"]
    assert len(anachronisms_modern) == 0
