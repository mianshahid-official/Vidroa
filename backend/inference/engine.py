"""
Inference engine interface and JSON repair parser for Qwen 30B models.
"""
import json
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from backend.config import backend_config


class JSONParseError(Exception):
    pass


class BaseInferenceEngine(ABC):
    """Abstract inference engine interface."""

    @abstractmethod
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        """Generates raw text from the model."""
        pass

    def generate_structured_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generates and parses structured JSON from the model with repair mechanisms."""
        raw_output = self.generate_text(prompt, system_prompt=system_prompt, temperature=temperature, max_tokens=max_tokens)
        return self.repair_and_parse_json(raw_output)

    @staticmethod
    def repair_and_parse_json(raw_text: str) -> Dict[str, Any]:
        """Strips markdown fences, isolates outermost JSON braces, and attempts recovery."""
        cleaned = raw_text.strip()

        # Strip markdown ```json ... ``` or ``` ... ```
        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
            if match:
                cleaned = match.group(1).strip()

        # Try direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Find outermost JSON brackets { ... } or [ ... ]
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            sub = cleaned[first_brace:last_brace + 1]
            try:
                return json.loads(sub)
            except json.JSONDecodeError:
                # Remove trailing commas before } or ]
                fixed = re.sub(r",\s*([}\]])", r"\1", sub)
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    pass

        # Check for array [ ... ]
        first_bracket = cleaned.find("[")
        last_bracket = cleaned.rfind("]")
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            sub = cleaned[first_bracket:last_bracket + 1]
            try:
                arr = json.loads(sub)
                return {"items": arr}
            except json.JSONDecodeError:
                pass

        # Truncation recovery: if the LLM output was truncated mid-JSON, recover all completed elements
        if first_brace != -1:
            matches = list(re.finditer(r"\}\s*,?", cleaned))
            if matches:
                for m in reversed(matches[-10:]):
                    candidate = cleaned[first_brace:m.end()].rstrip(", \t\r\n")
                    for closing in ["]}", "}", "]}}", "}\n}"]:
                        try:
                            return json.loads(candidate + closing)
                        except json.JSONDecodeError:
                            pass

        raise JSONParseError(f"Failed to parse structured JSON from model response: {raw_text[:300]}...")


class MockInferenceEngine(BaseInferenceEngine):
    """
    Test fixture inference engine used exclusively during automated unit testing in tests/ directory.
    Never used for production user requests.
    """
    def __init__(self, canned_responses: Optional[Dict[str, Any]] = None):
        self.canned_responses = canned_responses or {}

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        # Match prompt stage
        if "STAGE 1: STORY ANALYSIS" in prompt:
            return json.dumps({
                "story_summary": "A historical chronicle of ancient civilization.",
                "major_historical_events": ["Dawn of civilization", "Tribes gathering"],
                "cause_and_effect_flow": ["Tribes gather to survive harsh winters"],
                "historical_uncertainties": ["Exact tribal languages"],
                "narrative_beats": [{"beat_id": "b1", "summary": "Discovery", "emotional_tone": "wonder"}],
                "character_continuity_needed": False,
                "characters": [],
                "location_continuity_needed": False,
                "locations": [],
                "object_continuity_needed": False,
                "key_objects": [],
                "thumbnail_headline": "ANCIENT DAWN",
                "thumbnail_prompt": "A dramatic archival photograph of ancient stone monoliths."
            })
        elif "visual_beats" in prompt or "VISUAL PLANNING" in prompt or (system_prompt and any(w in system_prompt.lower() for w in ["visual storytelling", "visual beat", "storyboard architect"])):
            unit_lines = [l.strip() for l in prompt.split("\n") if l.strip().startswith("UNIT ")]
            if unit_lines:
                mock_concepts = [
                    ("Sun rising over ancient stone monoliths", "Establish antiquity and setting"),
                    ("Nomadic travelers gathering at river bank", "Introduce the community"),
                    ("Tribal chieftains convening in council", "Strategic council discussion"),
                    ("Scouts observing distant horizon from ridgeline", "Tactical recon and preparation"),
                    ("Armies marching through misty river valley", "Mobilization and progression"),
                    ("Defenders constructing timber palisade", "Defensive fortification"),
                    ("Decisive clash of forces under stormy sky", "Climactic struggle"),
                    ("Peaceful aftermath as dawn breaks over the plain", "Resolution and historical legacy")
                ]
                beats = []
                for idx, u in enumerate(unit_lines):
                    narr = u.split(":", 1)[1].strip().strip('"') if ":" in u else u
                    c_idx = idx % len(mock_concepts)
                    beats.append({
                        "beat_id": f"VB-{idx+1:03d}",
                        "exact_narration_segment": narr,
                        "narrative_purpose": mock_concepts[c_idx][1],
                        "primary_visual_concept": f"{mock_concepts[c_idx][0]} ({idx+1})",
                        "what_new_information_is_shown": mock_concepts[c_idx][1],
                        "why_this_is_not_repetitive": f"Sequential development {idx+1}",
                        "composition": "Wide cinematic shot",
                        "lighting_and_atmosphere": "Authentic period lighting",
                        "continuity_references": []
                    })
                if len(beats) < 2:
                    beats.append({
                        "beat_id": "VB-002",
                        "exact_narration_segment": "Continuing narrative development",
                        "narrative_purpose": "Advance narrative development",
                        "primary_visual_concept": "Defenders assembling along fortified perimeter",
                        "what_new_information_is_shown": "Active progression",
                        "why_this_is_not_repetitive": "Progression from preceding shot",
                        "composition": "Medium eye-level shot",
                        "lighting_and_atmosphere": "Authentic period lighting",
                        "continuity_references": []
                    })
                return json.dumps({"visual_beats": beats})

            return json.dumps({
                "visual_beats": [
                    {
                        "beat_id": "VB-001",
                        "exact_narration_segment": "In the ancient dawn of time",
                        "narrative_purpose": "Establish antiquity and setting",
                        "primary_visual_concept": "Sun rising over ancient stone monoliths",
                        "what_new_information_is_shown": "Ancient dawn",
                        "why_this_is_not_repetitive": "Opening image",
                        "composition": "Wide panoramic shot",
                        "lighting_and_atmosphere": "Golden morning sunlight",
                        "continuity_references": ["Monoliths"]
                    },
                    {
                        "beat_id": "VB-002",
                        "exact_narration_segment": "the tribes gathered together",
                        "narrative_purpose": "Introduce the community",
                        "primary_visual_concept": "Nomadic travelers gathering at river bank",
                        "what_new_information_is_shown": "Gathering tribes",
                        "why_this_is_not_repetitive": "Human community",
                        "composition": "Medium ground-level shot",
                        "lighting_and_atmosphere": "Soft morning haze",
                        "continuity_references": ["Tribes"]
                    }
                ]
            })
        elif "USER-SELECTED VISUAL STYLE" in prompt or "BATCH" in prompt:
            scene_matches = re.findall(r'"scene_id":\s*"([^"]+)"', prompt)
            if not scene_matches:
                scene_matches = ["001", "002"]
            diverse_mock_subjects = [
                ("Ancient stone monoliths at sunrise", "Towering stone monoliths standing on a misty grassy plain at dawn"),
                ("Nomadic travelers at riverbank", "Nomadic travelers congregating beside a flowing river with supply wagons"),
                ("Chieftains convening in council", "Tribal leaders gathered in discussion around a central council fire"),
                ("Scouts on ridge overlooking valley", "Sentinels observing distant terrain from a high rocky ridgeline"),
                ("Armies marching through misty pass", "Columns of soldiers advancing through a mountain pass under overcast skies"),
                ("Builders constructing timber palisades", "Craftsmen assembling defensive wooden fortifications and watchtowers"),
                ("Decisive battle clash under stormy sky", "Fierce engagement of opposing forces across an open plain"),
                ("Peaceful settlement at sunset", "Settlement with thatched roofs and evening light reflecting on water")
            ]
            items = []
            for s_idx, sid in enumerate(scene_matches):
                subj_pair = diverse_mock_subjects[s_idx % len(diverse_mock_subjects)]
                items.append({
                    "scene_id": sid,
                    "prompt": f"An authentic archival photograph of {subj_pair[1]}. Rich silver-toned monochrome and warm sepia, plate camera optics, sharp clear central subject, no modern RGB colors.",
                    "composition": "Wide panoramic shot" if s_idx % 2 == 0 else "Medium eye-level shot",
                    "environment": "Authentic historical setting",
                    "subject": subj_pair[0]
                })
            return json.dumps({"scenes": items})
        elif "AUDIT" in prompt or "COMPLETE STORYBOARD TO AUDIT" in prompt:
            return json.dumps({
                "overall_score": 92.0,
                "category_scores": {
                    "narration_alignment": 95.0,
                    "visual_progression": 90.0,
                    "temporal_pacing": 95.0,
                    "continuity": 90.0,
                    "style_fidelity": 95.0,
                    "prompt_quality": 90.0
                },
                "repetition_findings": [],
                "timing_findings": [],
                "alignment_findings": [],
                "scene_repairs": [],
                "final_recommendation": "APPROVED"
            })
        elif "FAILING SCENES REQUIRING REPAIR" in prompt:
            return json.dumps({
                "repaired_scenes": [],
                "unresolved_issues": [],
                "needs_reaudit": False
            })
        elif "STAGE 2" in prompt or (system_prompt and any(w in system_prompt.lower() for w in ["storyboard", "visual pacing architect", "visual scene planning"])):
            return json.dumps({
                "total_scenes": 2,
                "estimated_total_duration": 10.0,
                "scenes": [
                    {
                        "scene_id": "001",
                        "start": 0.0,
                        "end": 5.0,
                        "duration": 5.0,
                        "start_word_index": 0,
                        "end_word_index": 10,
                        "start_word": "In",
                        "end_word": "beginning",
                        "narration_excerpt": "In the ancient dawn of time",
                        "visual_subject": "Sun rising over ancient stone monoliths",
                        "visual_purpose": "Establish antiquity and setting",
                        "framing_suggestion": "Wide panoramic shot"
                    },
                    {
                        "scene_id": "002",
                        "start": 5.0,
                        "end": 10.0,
                        "duration": 5.0,
                        "start_word_index": 11,
                        "end_word_index": 20,
                        "start_word": "the",
                        "end_word": "earth",
                        "narration_excerpt": "the tribes gathered together",
                        "visual_subject": "Nomadic travelers gathering at river bank",
                        "visual_purpose": "Introduce the community",
                        "framing_suggestion": "Medium ground-level view"
                    }
                ]
            })
        elif "STAGE 3: BATCH IMAGE PROMPT" in prompt:
            return json.dumps({
                "batch_index": 0,
                "prompts": [
                    {
                        "scene_id": "001",
                        "visual_subject": "Sun rising over ancient stone monoliths",
                        "prompt": "An authentic archival photograph of towering weathered stone monoliths on a misty grassy plain at sunrise. Soft gelatin silver tones, authentic aged emulsion with fine grain, long dramatic shadows stretching across the dewy earth, wide panoramic landscape."
                    },
                    {
                        "scene_id": "002",
                        "visual_subject": "Nomadic travelers gathering at river bank",
                        "prompt": "A historical photograph of nomadic travelers wearing coarse linen tunics and leather sandals congregating on a sandy riverbank. Clay water jugs and wooden carts visible in the background, low morning sunlight creating natural rim highlights, natural documentary composition."
                    }
                ]
            })
        # Stage 3 single-scene plain-text prompt (new per-scene approach - no JSON needed)
        elif "expert image prompt writer" in prompt or "SCENE TO DESCRIBE" in prompt:
            return "An authentic archival photograph capturing the visual scene with documentary clarity. Wide angle lens, natural period-accurate lighting, no modern elements present."
        return json.dumps({"status": "ok"})


class VLLMInferenceEngine(BaseInferenceEngine):
    """vLLM engine running on Modal with Qwen 30B/32B models."""

    def __init__(self, llm_instance=None):
        self.llm = llm_instance

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        if self.llm is None:
            raise RuntimeError("vLLM model instance is not initialized on this worker.")

        temp = temperature if temperature is not None else backend_config.temperature
        max_tok = max_tokens if max_tokens is not None else backend_config.max_output_tokens

        # Use vLLM sampling params
        from vllm import SamplingParams
        sampling_params = SamplingParams(
            temperature=temp,
            top_p=backend_config.top_p,
            max_tokens=max_tok
        )

        outputs = self.llm.generate([prompt], sampling_params)
        if outputs and outputs[0].outputs:
            return outputs[0].outputs[0].text
        return ""


class ErrorReportingEngine(BaseInferenceEngine):
    """Engine that captures model loading errors and reports them gracefully to the client."""

    def __init__(self, error_message: str):
        self.error_message = error_message

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        raise RuntimeError(f"Modal AI model initialization error: {self.error_message}")


class OpenAICompatibleInferenceEngine(BaseInferenceEngine):
    """Inference engine that queries standard OpenAI-compatible endpoints (such as Modal vllm serve)."""

    def __init__(self, base_url: str, api_key: Optional[str] = None, model: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or "EMPTY"
        self.model = model or backend_config.model_name or backend_config.model_hf_path

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        temp = temperature if temperature is not None else backend_config.temperature
        max_tok = max_tokens if max_tokens is not None else backend_config.max_output_tokens

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temp,
            "max_tokens": max_tok
        }

        import httpx
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""
            else:
                raise RuntimeError(f"OpenAI-compatible LLM endpoint ({url}) returned {resp.status_code}: {resp.text}")


class GroqInferenceEngine(BaseInferenceEngine):
    """Local inference engine that routes prompt requests through Groq's multi-key pooled API."""

    def __init__(self, model_name: str = "qwen/qwen3.8-27b", default_model: Optional[str] = None):
        from app.ai.groq_engine import get_groq_engine
        self.groq = get_groq_engine()
        self.model_name = default_model or model_name

    def current_effective_max_tokens(self, baseline: int = 950) -> int:
        """Delegates to the underlying Groq engine's effective output cap."""
        accessor = getattr(self.groq, "current_effective_max_tokens", None)
        if callable(accessor):
            return int(accessor(baseline))
        return baseline

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        temp = temperature if temperature is not None else 0.4
        max_tok = max_tokens if max_tokens is not None else 2500
        return self.groq.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            model=self.model_name,
            temperature=temp,
            max_tokens=max_tok
        )


class ModalRemoteInferenceEngine(BaseInferenceEngine):
    """Legacy remote inference engine - routed to GroqInferenceEngine for local execution."""

    def __init__(self, **kwargs):
        self._groq = GroqInferenceEngine()

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        return self._groq.generate_text(prompt=prompt, system_prompt=system_prompt, temperature=temperature, max_tokens=max_tokens)

