"""
Story Pack Manager & Unified Faction Sanitizer.
Quarantines story-specific historical knowledge into opt-in story packs.
Generic shared code knows nothing about Constantinople, Caesar, Cortés, or Dorothea.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
from app.config.constants import PROJECT_ROOT_DIR

STORY_PACKS_DIR = PROJECT_ROOT_DIR / "config" / "story_packs"
if not STORY_PACKS_DIR.exists():
    STORY_PACKS_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "story_packs"


@dataclass
class StoryPack:
    id: str
    name: str
    match_keywords: List[str] = field(default_factory=list)
    characters: List[Dict[str, Any]] = field(default_factory=list)
    locations: List[Dict[str, Any]] = field(default_factory=list)
    objects: List[Dict[str, Any]] = field(default_factory=list)
    period: Dict[str, Any] = field(default_factory=dict)
    faction_rules: Dict[str, Any] = field(default_factory=dict)
    spoiler_rules: List[Dict[str, Any]] = field(default_factory=list)
    audit_checks: List[str] = field(default_factory=list)
    prompt_fragment: str = ""


class StoryPackManager:
    """Discovers, loads, and matches story packs."""

    _cache: Dict[str, StoryPack] = {}

    @classmethod
    def list_pack_ids(cls) -> List[str]:
        if not STORY_PACKS_DIR.exists():
            return []
        return [p.name for p in STORY_PACKS_DIR.iterdir() if p.is_dir() and (p / "pack.json").exists()]

    @classmethod
    def get_pack(cls, slug: str) -> Optional[StoryPack]:
        if slug in cls._cache:
            return cls._cache[slug]

        pack_dir = STORY_PACKS_DIR / slug
        pack_json = pack_dir / "pack.json"
        if not pack_json.exists():
            return None

        try:
            data = json.loads(pack_json.read_text(encoding="utf-8"))
            frag_file = pack_dir / "prompt_fragment.txt"
            frag_text = frag_file.read_text(encoding="utf-8").strip() if frag_file.exists() else ""

            pack = StoryPack(
                id=data.get("id", slug),
                name=data.get("name", slug),
                match_keywords=data.get("match_keywords", []),
                characters=data.get("characters", []),
                locations=data.get("locations", []),
                objects=data.get("objects", []),
                period=data.get("period", {}),
                faction_rules=data.get("faction_rules", {}),
                spoiler_rules=data.get("spoiler_rules", []),
                audit_checks=data.get("audit_checks", []),
                prompt_fragment=frag_text
            )
            cls._cache[slug] = pack
            return pack
        except Exception as e:
            print(f"[StoryPackManager] Error loading pack '{slug}': {e}")
            return None

    @classmethod
    def match_pack(cls, story_text: str, explicit_pack_id: Optional[str] = None) -> Optional[StoryPack]:
        """
        Loads a pack explicitly or auto-matches on story text keywords.
        Auto-matching MUST print an explicit log message per specification.
        """
        if explicit_pack_id:
            pack = cls.get_pack(explicit_pack_id)
            if pack:
                print(f"[StoryPack] story pack {pack.id} explicitly selected")
                return pack

        if not story_text:
            return None

        for slug in cls.list_pack_ids():
            pack = cls.get_pack(slug)
            if not pack:
                continue
            for kw in pack.match_keywords:
                # Word-boundary match to avoid accidental substring hits
                if re.search(rf"\b{re.escape(kw)}\b", story_text, re.IGNORECASE):
                    print(f"[StoryPack] story pack {pack.id} auto-matched on keyword '{kw}'")
                    return pack

        return None


def sanitize_stickman_prompt(
    prompt_text: str,
    protagonist_name: str = "Protagonist",
    supporting_names: Optional[List[str]] = None,
    active_pack: Optional[StoryPack] = None,
    narration_text: str = ""
) -> str:
    """
    Unified faction sanitizer for 3D red/blue stickman style.
    Consolidates previously duplicated and divergent faction logic from stages 5, 6, 7, and 8.
    """
    p_text = prompt_text

    # 1. Strip realistic facial features, hair, and clothing
    p_text = re.sub(
        r"\b(with a|with|having a|wearing a)?\s*(dark|trimmed|short|full|imperial)?\s*(beard|beards|mustache|mustaches)\b",
        "", p_text, flags=re.IGNORECASE
    )
    p_text = re.sub(
        r"\b(wearing (an|a)?\s*(imperial|embroidered)?\s*(turban|silk caftan|velvet cape|tunic|leather boots|flowing robe|armor plate|cape|cloak))\b",
        "solid matte colored stick figure", p_text, flags=re.IGNORECASE
    )
    p_text = re.sub(r"\bhuman (face|eyes|skin|facial features|hair)\b", "featureless spherical 3D stickman head", p_text, flags=re.IGNORECASE)
    p_text = re.sub(r"\b(realistic|photorealistic|detailed)\s+(face|eyes|skin|beard|mustache|clothing)\b", "featureless smooth 3D geometry", p_text, flags=re.IGNORECASE)

    # 2. Pack-specific faction rules (e.g. Caesar = RED, conspirators = BLUE)
    if active_pack and active_pack.id == "caesar-44bc":
        p_text = re.sub(
            r"\b(solid\s+)?blue\s+(3d\s+)?(stick\s+figure|stickman)\s*\((caesar|the dictator|julius caesar)\)",
            r"solid bright red 3D stick figure (\4 with gold toy crown)",
            p_text,
            flags=re.IGNORECASE
        )
        p_text = re.sub(
            r"\b(solid\s+)?blue\s+(3d\s+)?stick\s+figure\s+caesar\b",
            "solid bright red 3D stick figure Caesar",
            p_text,
            flags=re.IGNORECASE
        )
        p_text = re.sub(
            r"\b(solid\s+)?(bright\s+)?red\s+(3d\s+)?(stick\s+figure|stickman|figures|stickmen)\s*\((conspirators?|assassins?|liberatores?|cimber|casca|brutus|cassius|senators?)\)",
            r"solid blue 3D \4 (\5)",
            p_text,
            flags=re.IGNORECASE
        )
        p_text = re.sub(
            r"\ba\s+single\s+bright\s+red\s+3d\s+stick\s+figure\s*\(cimber\)",
            "a single solid blue 3D stick figure (Cimber)",
            p_text,
            flags=re.IGNORECASE
        )
        p_text = re.sub(
            r"\ba\s+pack\s+of\s+solid\s+bright\s+red\s+3d\s+stick\s+figures\s*\(liberatores\)",
            "a pack of solid blue 3D stick figures (Liberatores)",
            p_text,
            flags=re.IGNORECASE
        )
    elif active_pack and active_pack.id == "constantinople-1453":
        # Siege faction purity
        p_lower = p_text.lower()
        narr_lower = narration_text.lower() if narration_text else ""
        is_defending_scene = any(w in narr_lower or w in p_lower for w in ["repaired", "defenders", "inside the city", "rubble", "timber", "walls resisted", "harbor", "chain"])
        is_attacking_scene = any(w in narr_lower or w in p_lower for w in ["cannon", "bombard", "encampment", "dragged overland", "artillery battery", "opened fire outside", "ottoman cannons"])
        is_combat_clash = any(w in narr_lower or w in p_lower for w in ["final assault", "hand-to-hand", "clash", "storming", "combat"])

        if is_defending_scene and not is_combat_clash:
            if "zero red figures" not in p_lower:
                p_text += " Exclusively solid blue 3D stick figures inside the city. Zero red figures present."
        elif is_attacking_scene and not is_combat_clash:
            if "zero blue figures" not in p_lower:
                p_text += " Exclusively solid bright red 3D stick figures outside the fortifications. Zero blue figures present."
    else:
        # Generic faction rules: protagonist is RED, supporting figures are BLUE
        if protagonist_name and protagonist_name != "Protagonist":
            escaped_proto = re.escape(protagonist_name)
            p_text = re.sub(
                rf"\b(solid\s+)?blue\s+(3d\s+)?(stick\s+figure|stickman)\s*\({escaped_proto}\)",
                rf"solid bright red 3D stick figure ({protagonist_name})",
                p_text,
                flags=re.IGNORECASE
            )

    # 3. Clean up leaked pipeline scaffolding
    p_text = re.sub(r"\b(Active progression|Consequential development|Establishing perspective):\s*", "", p_text)
    p_text = re.sub(r"^(A wide, low|A split|A solitary, evocative wide shot)\s*—?\s*", "", p_text)
    p_text = re.sub(r"Setting:\s*Fortified historical cityscape and defensive ramparts\.?", "", p_text)
    p_text = re.sub(r"Setting:\s*Fortified historical setting\.?", "", p_text)
    p_text = re.sub(r"\s+", " ", p_text).strip()

    # 4. Append Negative Prompts
    if "STRICT NEGATIVE:" not in p_text:
        p_text = (
            f"{p_text.rstrip('. ')}. 3D animated stickman universe, stylized toy CGI render, smooth matte plastic. "
            f"STRICT NEGATIVE: human face, realistic eyes, nose, mouth, beard, mustache, human hair, human skin texture, realistic fabric, realistic clothing, turban, cape, cloak, tunic, boots, doll, claymation human, photorealism, live-action."
        )

    return p_text
