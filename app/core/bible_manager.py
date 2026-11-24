"""
Bible Manager for PromptBeast Pro.
Handles flexible user-provided production bibles (Characters, Environments, Props, Style).
Supports:
1. Flexible bulk input: single file with multiple bibles, directory of bible files, or pasted text.
2. Robust parsing of standard human-readable and markdown bibles (like Bibles.txt).
3. Selection of active bible for project prompt expansion without any Groq bible generation.
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from app.models.planning import StoryIntelligence, ScriptAnalysis
from app.models.scene import StoryAnalysis


class BibleManager:
    """Manages loading, parsing, and selecting user-provided production bibles."""

    @classmethod
    def load_bibles_from_path(cls, path: Union[str, Path]) -> Dict[str, Dict[str, Any]]:
        """
        Loads bibles from either a file path or a folder path.
        Returns a dictionary mapping {bible_name: parsed_bible_dict}.
        """
        p = Path(path)
        if not p.exists():
            return {}

        if p.is_dir():
            return cls._load_bibles_from_folder(p)
        else:
            return cls._load_bibles_from_file(p)

    @classmethod
    def _load_bibles_from_file(cls, file_path: Path) -> Dict[str, Dict[str, Any]]:
        """Loads and parses a single file which may contain one or multiple bibles."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            try:
                content = file_path.read_text(encoding="latin-1")
            except Exception:
                return {}

        # If it's a JSON file
        if file_path.suffix.lower() == ".json":
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    # Check if it's a dictionary of multiple bibles or a single bible
                    if any(k in data for k in ("characters", "environments", "story_bible", "key_objects")):
                        return {file_path.stem: data}
                    else:
                        # Collection of bibles
                        result = {}
                        for k, v in data.items():
                            if isinstance(v, dict):
                                result[k] = v
                        if result:
                            return result
            except Exception:
                pass

        # Text format: check for multiple bibles or single bible
        return cls.parse_bulk_bibles_text(content, default_name=file_path.stem)

    @classmethod
    def _load_bibles_from_folder(cls, folder_path: Path) -> Dict[str, Dict[str, Any]]:
        """Scans a directory for bible text or JSON files."""
        result: Dict[str, Dict[str, Any]] = {}
        extensions = {".txt", ".json", ".md"}
        files = [f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() in extensions]

        # Check if folder has separate component files for a single bible (e.g. character_bible.txt, location_bible.txt)
        component_stems = {"character_bible", "location_bible", "environment_bible", "story_bible", "props_bible", "style_bible"}
        found_stems = {f.stem.lower() for f in files}
        if len(found_stems.intersection(component_stems)) >= 2:
            unified = cls._assemble_components_from_files(files)
            if unified:
                result[folder_path.name] = unified
                return result

        for f in files:
            bibles_in_file = cls._load_bibles_from_file(f)
            for name, b_data in bibles_in_file.items():
                key = name if name != f.stem else f.stem
                if key in result:
                    key = f"{f.stem}_{name}"
                result[key] = b_data

        return result

    @classmethod
    def _assemble_components_from_files(cls, files: List[Path]) -> Dict[str, Any]:
        """Combines separate component files into a single structured bible."""
        combined_text_parts = []
        for f in files:
            try:
                txt = f.read_text(encoding="utf-8")
                combined_text_parts.append(txt)
            except Exception:
                pass
        combined = "\n\n".join(combined_text_parts)
        return cls.parse_single_bible_text(combined)

    @classmethod
    def parse_bulk_bibles_text(cls, text: str, default_name: str = "Production Bible") -> Dict[str, Dict[str, Any]]:
        """
        Detects if text contains multiple bibles separated by clear story/bible headers.
        If multiple bibles exist, splits and returns {name: bible_dict}.
        Otherwise returns {default_name: bible_dict}.
        """
        if not text or not text.strip():
            return {}

        # Look for explicit delimiter headers like '=== BIBLE: <Name> ===' or '### BIBLE: <Name>'
        split_pattern = r"(?:^|\n)(?:={3,}|#{2,})\s*(?:BIBLE|STORY|PROJECT):\s*([^\n=]+?)\s*(?:={3,}|#{2,}|\n)"
        matches = list(re.finditer(split_pattern, text, flags=re.IGNORECASE))

        if len(matches) >= 2:
            bibles = {}
            for i, match in enumerate(matches):
                name = match.group(1).strip()
                start_idx = match.end()
                end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                sub_text = text[start_idx:end_idx].strip()
                if sub_text:
                    bibles[name] = cls.parse_single_bible_text(sub_text)
            if bibles:
                return bibles

        # Single bible
        return {default_name: cls.parse_single_bible_text(text)}

    @classmethod
    def parse_single_bible_text(cls, bible_text: str) -> Dict[str, Any]:
        """
        Parses human-readable or markdown production bibles into structured dictionaries.
        Supports:
        - 1. CHARACTER BIBLE (Characters with Name, Role, Appearance/Anatomy, Clothing/Wardrobe, Props, Continuity)
        - 2. ENVIRONMENT BIBLE (Locations with Name, Architecture, Asset Blocks, Lighting, Progression)
        - 3. OBJECT AND PROP BIBLE (Equipment, Communications, Structural, Props)
        - 4. CINEMATIC STYLE BIBLE (Aesthetic Definition, Color Palette, Lighting Rules, Composition)
        - 5. CHRONOLOGY AND CONTINUITY BIBLE
        - 6. IMPORTANT VISUAL CONTINUITY RULES
        - 7. FINAL STORY VISUAL IDENTITY
        """
        bibles: Dict[str, Any] = {
            "story_bible": {
                "premise": "",
                "summary": "",
                "genre_and_tone": "",
                "setting_period": "Modern Day",
                "visual_identity": ""
            },
            "characters": [],
            "environments": [],
            "key_objects": [],
            "visual_style_bible": {
                "style_name": "",
                "color_palette": "",
                "lighting_rules": "",
                "camera_guidelines": ""
            },
            "visual_continuity_rules": [],
            "chronological_events": []
        }

        if not bible_text or not bible_text.strip():
            return bibles

        # Helper to clean markdown formatting from lines
        def clean_md(text: str) -> str:
            t = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
            t = re.sub(r'__(.*?)__', r'\1', t)
            t = re.sub(r'\*(.*?)\*', r'\1', t)
            t = re.sub(r'`(.*?)`', r'\1', t)
            return t.strip()

        # If it's raw JSON
        trimmed = bible_text.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            try:
                data = json.loads(trimmed)
                if isinstance(data, dict):
                    for k in bibles.keys():
                        if k in data:
                            bibles[k] = data[k]
                    return bibles
            except Exception:
                pass

        # Normalize text by stripping markdown bold wrappers on section titles and lines
        normalized_lines = []
        for raw_line in bible_text.splitlines():
            cleaned = clean_md(raw_line)
            normalized_lines.append(cleaned)
        norm_text = "\n".join(normalized_lines)

        # Split into main bible sections
        # Section headers typically start with '1. CHARACTER BIBLE', 'CHARACTER BIBLE', '# CHARACTER BIBLE', etc.
        sec_pattern = r'(?im)^\s*(?:[0-9]+\.\s*|#+\s*)?([A-Z\s]{3,}BIBLE[^\n]*)$'
        parts = re.split(sec_pattern, norm_text)

        sections: Dict[str, str] = {}
        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                sec_title = parts[i].strip().upper()
                sec_body = parts[i + 1].strip() if i + 1 < len(parts) else ""
                sections[sec_title] = sec_body
        else:
            # Fallback: scan whole text for keywords
            sections["CHARACTER BIBLE"] = norm_text
            sections["ENVIRONMENT BIBLE"] = norm_text
            sections["OBJECT AND PROP BIBLE"] = norm_text
            sections["CINEMATIC STYLE BIBLE"] = norm_text

        # -------------------------------------------------------------
        # 1. PARSE CHARACTERS
        # -------------------------------------------------------------
        char_text = ""
        for k, v in sections.items():
            if "CHARACTER" in k:
                char_text += "\n" + v

        if char_text:
            c_pattern = r'\n(?=(?:CHARACTER\s+\d+:?|CHARACTER:?|[A-Z0-9\s\(\)\"\'\—\-]{3,}\n+(?:Role|Identity|Appearance|Anatomy|Wardrobe|Clothing)))'
            raw_c_blocks = [b.strip() for b in re.split(c_pattern, "\n" + char_text, flags=re.IGNORECASE) if b.strip()]

            for cb in raw_c_blocks:
                lines = [l.strip() for l in cb.split("\n") if l.strip()]
                if not lines:
                    continue

                raw_name = lines[0]
                if re.match(r'^(?:[0-9]+\.\s*)?CHARACTER BIBLE', raw_name, re.IGNORECASE):
                    if len(lines) > 1:
                        raw_name = lines[1]
                        lines = lines[1:]
                    else:
                        continue

                name = re.sub(r'^(?:CHARACTER\s+\d+:?|CHARACTER:?)\s*', '', raw_name, flags=re.IGNORECASE).strip()
                name = clean_md(name).rstrip(":")
                if not name or len(name) < 2 or "CHARACTER BIBLE" in name.upper():
                    continue

                role = ""
                anatomy_lines = []
                wardrobe_lines = []
                props_lines = []
                rules_lines = []
                curr_cat = "anatomy"

                for line in lines[1:]:
                    line_clean = clean_md(line).lstrip("-*• ")
                    low = line_clean.lower()
                    if low.startswith(("role & identity:", "role:", "identity:")):
                        role = line_clean.split(":", 1)[1].strip()
                        curr_cat = "role"
                    elif low.startswith(("anatomy & head proportions:", "anatomy:", "appearance:", "build:", "age:")):
                        curr_cat = "anatomy"
                        val = line_clean.split(":", 1)[1].strip()
                        if val:
                            anatomy_lines.append(val)
                    elif low.startswith(("locked wardrobe & colors:", "locked wardrobe:", "wardrobe:", "clothing:", "outfit:")):
                        curr_cat = "wardrobe"
                        val = line_clean.split(":", 1)[1].strip()
                        if val:
                            wardrobe_lines.append(val)
                    elif low.startswith(("important props & tools:", "important props:", "props:", "tools:")):
                        curr_cat = "props"
                        val = line_clean.split(":", 1)[1].strip()
                        if val:
                            props_lines.append(val)
                    elif low.startswith(("visual continuity rules:", "visual continuity:", "continuity:")):
                        curr_cat = "rules"
                        val = line_clean.split(":", 1)[1].strip()
                        if val:
                            rules_lines.append(val)
                    elif low.startswith("visual expression & demeanor:"):
                        curr_cat = "anatomy"
                        val = line_clean.split(":", 1)[1].strip()
                        if val:
                            anatomy_lines.append(val)
                    else:
                        clean_item = line_clean.strip()
                        if not clean_item:
                            continue
                        if curr_cat == "role":
                            role += (" " + clean_item) if role else clean_item
                        elif curr_cat == "anatomy":
                            anatomy_lines.append(clean_item)
                        elif curr_cat == "wardrobe":
                            wardrobe_lines.append(clean_item)
                        elif curr_cat == "props":
                            props_lines.append(clean_item)
                        elif curr_cat == "rules":
                            rules_lines.append(clean_item)

                bibles["characters"].append({
                    "name": name,
                    "role": role or "Survivor / Narrative Role",
                    "physical_description": ". ".join(anatomy_lines) if anatomy_lines else "Standard visual build adhering to style directives.",
                    "clothing_and_gear": ". ".join(wardrobe_lines) if wardrobe_lines else "Consistent wardrobe across all scenes.",
                    "props": ", ".join(props_lines),
                    "consistency_rules": "; ".join(rules_lines)
                })

        # -------------------------------------------------------------
        # 2. PARSE ENVIRONMENTS
        # -------------------------------------------------------------
        env_text = ""
        for k, v in sections.items():
            if "ENVIRONMENT" in k or "LOCATION" in k:
                env_text += "\n" + v

        if env_text:
            e_pattern = r'\n(?=(?:LOCATION\s+\d+:?|LOCATION:?|ENVIRONMENT\s+\d+:?|[A-Z0-9\s\(\)\"\'\—\-]{3,}\n+(?:Primary Setting|Architecture|2D Architectural|Setting|Setting:|Layout:)))'
            raw_e_blocks = [b.strip() for b in re.split(e_pattern, "\n" + env_text, flags=re.IGNORECASE) if b.strip()]

            for eb in raw_e_blocks:
                lines = [l.strip() for l in eb.split("\n") if l.strip()]
                if not lines:
                    continue

                raw_name = lines[0]
                if re.match(r'^(?:[0-9]+\.\s*)?ENVIRONMENT BIBLE', raw_name, re.IGNORECASE):
                    if len(lines) > 1:
                        raw_name = lines[1]
                        lines = lines[1:]
                    else:
                        continue

                name = re.sub(r'^(?:LOCATION\s+\d+:?|LOCATION:?|ENVIRONMENT\s+\d+:?)\s*', '', raw_name, flags=re.IGNORECASE).strip()
                name = clean_md(name).rstrip(":")
                if not name or len(name) < 2 or "ENVIRONMENT BIBLE" in name.upper():
                    continue

                arch_lines = []
                feature_lines = []
                lighting_lines = []
                prog_lines = []
                curr_cat = "arch"

                for line in lines[1:]:
                    line_clean = clean_md(line).lstrip("-*• ")
                    low = line_clean.lower()
                    if low.startswith(("primary setting & layout:", "primary setting:", "setting:", "layout:")):
                        curr_cat = "arch"
                        val = line_clean.split(":", 1)[1].strip()
                        if val:
                            arch_lines.append(val)
                    elif low.startswith(("2d architectural style:", "architecture style:", "architectural style:", "architecture:", "scale:")):
                        curr_cat = "arch"
                        val = line_clean.split(":", 1)[1].strip()
                        if val:
                            arch_lines.append(val)
                    elif low.startswith(("flat asset blocks:", "interior design & assets:", "interior:", "features:", "assets:")):
                        curr_cat = "features"
                        val = line_clean.split(":", 1)[1].strip()
                        if val:
                            feature_lines.append(val)
                    elif low.startswith(("atmospheric lighting:", "lighting scheme:", "lighting:", "atmosphere:")):
                        curr_cat = "lighting"
                        val = line_clean.split(":", 1)[1].strip()
                        if val:
                            lighting_lines.append(val)
                    elif low.startswith(("visual progression:", "progression:")):
                        curr_cat = "prog"
                        val = line_clean.split(":", 1)[1].strip()
                        if val:
                            prog_lines.append(val)
                    else:
                        clean_item = line_clean.strip()
                        if not clean_item:
                            continue
                        if curr_cat == "arch":
                            arch_lines.append(clean_item)
                        elif curr_cat == "features":
                            feature_lines.append(clean_item)
                        elif curr_cat == "lighting":
                            lighting_lines.append(clean_item)
                        elif curr_cat == "prog":
                            prog_lines.append(clean_item)

                bibles["environments"].append({
                    "name": name,
                    "architectural_style": ". ".join(arch_lines) if arch_lines else "Consistent architectural framing and scale.",
                    "environmental_features": ", ".join(feature_lines),
                    "lighting_and_atmosphere": ". ".join(lighting_lines) if lighting_lines else "Atmospheric directional lighting matching story mood.",
                    "visual_progression": "; ".join(prog_lines)
                })

        # -------------------------------------------------------------
        # 3. PARSE PROPS & OBJECTS
        # -------------------------------------------------------------
        obj_text = ""
        for k, v in sections.items():
            if "OBJECT" in k or "PROP" in k:
                obj_text += "\n" + v

        if obj_text:
            p_lines = [clean_md(l).lstrip("-*• ") for l in obj_text.split("\n") if l.strip() and not clean_md(l).rstrip().endswith(":")]
            props_list = [p for p in p_lines if len(p) > 2 and not p.upper().endswith("BIBLE")]
            if props_list:
                bibles["key_objects"] = [{"name": p, "description": p} for p in props_list[:40]]

        # -------------------------------------------------------------
        # 4. PARSE VISUAL STYLE
        # -------------------------------------------------------------
        style_text = ""
        for k, v in sections.items():
            if "STYLE" in k or "CINEMATIC" in k:
                style_text += "\n" + v

        if style_text:
            p_match = re.search(r"(?:COLOR PALETTE|PALETTE)[:\s]*([^\n]+)", style_text, re.IGNORECASE)
            if p_match:
                bibles["visual_style_bible"]["color_palette"] = clean_md(p_match.group(1))
            l_match = re.search(r"(?:LIGHTING|LIGHTING RULES)[:\s]*([^\n]+)", style_text, re.IGNORECASE)
            if l_match:
                bibles["visual_style_bible"]["lighting_rules"] = clean_md(l_match.group(1))
            c_match = re.search(r"(?:COMPOSITION|CAMERA GUIDELINES)[:\s]*([^\n]+)", style_text, re.IGNORECASE)
            if c_match:
                bibles["visual_style_bible"]["camera_guidelines"] = clean_md(c_match.group(1))

        # -------------------------------------------------------------
        # 5. PARSE CONTINUITY RULES
        # -------------------------------------------------------------
        rules_text = ""
        for k, v in sections.items():
            if "CONTINUITY" in k or "RULES" in k:
                rules_text += "\n" + v

        if rules_text:
            r_items = [clean_md(l).lstrip("-*• ") for l in rules_text.split("\n") if l.strip()]
            bibles["visual_continuity_rules"] = [r for r in r_items if len(r) > 10 and not r.upper().endswith("BIBLE")][:30]

        # Story premise summary from first 300 chars
        if not bibles["story_bible"]["summary"]:
            bibles["story_bible"]["summary"] = (char_text or env_text or norm_text)[:300].strip()

        return bibles

    @classmethod
    def bible_to_story_intelligence(cls, bible_dict: Dict[str, Any]) -> StoryIntelligence:
        """
        Converts structured bible dictionary directly to StoryIntelligence model
        for seamless consumption by Stage 3 prompt expansion.
        """
        sb = bible_dict.get("story_bible", {})
        summary = sb.get("summary") or sb.get("logline") or sb.get("premise") or "User-provided story bible"

        chars = bible_dict.get("characters", [])
        envs = bible_dict.get("environments", [])
        props = bible_dict.get("key_objects", [])
        style = bible_dict.get("visual_style_bible", {})

        return StoryIntelligence(
            story_summary=summary,
            characters=chars,
            environments=envs,
            objects_and_props=props,
            visual_style_bible=style
        )

