"""
Stock Video Service for PromptBeast / Vidroa.
Queries Pexels Video API and Pixabay Video API for B-roll footage.
Supports:
  - Cartoon / flat-2D query priority (Pixabay animation first, Pexels fallback)
  - Realistic / history query priority (Pexels first, Pixabay fallback)
  - Fetching top 3 candidates per scene
  - Downloading clips to local project cache
"""
import os
import re
import json
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.config.settings import SettingsManager


def is_cartoon_style(style_id: str) -> bool:
    """Checks whether the visual style corresponds to cartoon / animation / flat 2D."""
    s = (style_id or "").lower()
    return any(k in s for k in ["flat", "2d", "cartoon", "vector", "stickman", "anime", "animation"])


def determine_stock_route(
    style_id: str = "century_old_photograph",
    keywords: Optional[List[str]] = None,
    treatment: Optional[str] = None,
) -> tuple[str, str]:
    """
    Determines stock video provider priority and video_type filter.
    Returns: (first_provider, video_type) where first_provider is 'pexels' or 'pixabay',
    and video_type is 'animation' or 'all'.

    Routing Rules:
      - Archival treatment (treatment 11): Pexels first (realistic, video_type='all').
      - Engraving and Maps treatments (treatments 10 & 12): Pixabay first with
        video_type='animation' ONLY if the keywords explicitly ask for animation
        (animation, animated, drawing, sketch, cgi, cartoon), otherwise Pexels first
        for real footage of the place or subject (video_type='all').
      - Flat 2D / Cartoon styles (zombie, whatif, stickman): Pixabay first with video_type='animation'.
      - Baseline Century-Old / Other styles: Pexels first (realistic, video_type='all').
    """
    sid = (style_id or "").lower().strip()
    t = (treatment or "").lower().strip()
    kw_str = " ".join(keywords or []).lower()
    animation_needed = any(w in kw_str for w in ["animation", "animated", "cartoon", "drawing", "illustration", "sketch", "cgi"])

    # 1. Check treatments (exact treatment IDs / aliases for Century-Old Photograph style)
    if t in {"authentic_archival", "authentic_archival_photography", "archival_photography", "archival_photo", "treatment_11", "11"}:
        return ("pexels", "all")
    elif t in {"antique_engraving", "engraving", "copperplate", "treatment_10", "10", "historical_maps", "historical_map", "maps", "map", "treatment_12", "12"}:
        if animation_needed:
            return ("pixabay", "animation")
        return ("pexels", "all")

    # 2. Check base visual style (exact live style IDs)
    if sid in {"zombie_survival", "whatif_flat_vector", "3d_red_blue_stickman"}:
        return ("pixabay", "animation")
    else:
        return ("pexels", "all")


class StockVideoService:
    """Manages searching and downloading stock video footage from Pexels and Pixabay."""

    @classmethod
    def get_api_keys(cls) -> Dict[str, str]:
        """Retrieves Pexels and Pixabay API keys from settings or environment."""
        settings = SettingsManager.load_settings()
        pexels = (settings.pexels_api_key or os.environ.get("PEXELS_API_KEY", "")).strip()
        pixabay = (settings.pixabay_api_key or os.environ.get("PIXABAY_API_KEY", "")).strip()
        return {
            "pexels": pexels,
            "pixabay": pixabay,
        }

    @classmethod
    def search_candidates(
        cls,
        keywords: List[str],
        style_id: str = "century_old_photograph",
        treatment: Optional[str] = None,
        max_candidates: int = 3,
        pexels_key: Optional[str] = None,
        pixabay_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Searches for stock video candidates using keywords, style, and treatment priority.
        Returns top candidates with metadata.
        """
        keys = cls.get_api_keys()
        p_key = (pexels_key or keys["pexels"]).strip()
        px_key = (pixabay_key or keys["pixabay"]).strip()

        first_provider, video_type = determine_stock_route(style_id=style_id, keywords=keywords, treatment=treatment)
        candidates: List[Dict[str, Any]] = []

        if first_provider == "pixabay":
            # Pixabay first
            if px_key:
                candidates.extend(cls.search_pixabay(keywords, api_key=px_key, video_type=video_type))
            # Fallback to Pexels
            if len(candidates) < max_candidates and p_key:
                candidates.extend(cls.search_pexels(keywords, api_key=p_key))
        else:
            # Pexels first
            if p_key:
                candidates.extend(cls.search_pexels(keywords, api_key=p_key))
            # Fallback to Pixabay
            if len(candidates) < max_candidates and px_key:
                candidates.extend(cls.search_pixabay(keywords, api_key=px_key, video_type="all"))

        # Deduplicate candidates by download url or id
        seen = set()
        unique_candidates = []
        for c in candidates:
            url = c.get("download_url") or c.get("id")
            if url and url not in seen:
                seen.add(url)
                unique_candidates.append(c)
                if len(unique_candidates) >= max_candidates:
                    break

        return unique_candidates

    @classmethod
    def search_pexels(
        cls,
        keywords: List[str],
        api_key: str,
        per_page: int = 15,
    ) -> List[Dict[str, Any]]:
        """Searches Pexels Video API."""
        if not api_key:
            return []

        query = " ".join(keywords[:4]) if keywords else "historical"
        params = urllib.parse.urlencode({
            "query": query,
            "per_page": per_page,
            "orientation": "landscape",
            "min_width": 1280,
            "min_height": 720,
        })
        url = f"https://api.pexels.com/videos/search?{params}"

        req = urllib.request.Request(url, headers={
            "Authorization": api_key,
            "User-Agent": "PromptBeast/1.0"
        })

        results = []
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                data = json.loads(response.read().decode("utf-8"))
                for v in data.get("videos", []):
                    v_id = str(v.get("id", ""))
                    dur = float(v.get("duration", 0.0))
                    width = int(v.get("width", 0))
                    height = int(v.get("height", 0))
                    v_url = v.get("url", "")
                    
                    # Extract tags/title from pexels url e.g. /video/walking-down-the-street-123/
                    title = ""
                    tags = []
                    if v_url:
                        parts = v_url.strip("/").split("/")
                        if parts:
                            slug = parts[-1].rsplit("-", 1)[0]
                            title = slug.replace("-", " ")
                            tags = [t.strip() for t in slug.split("-") if t.strip()]

                    # Find best HD/FHD mp4 file
                    video_files = v.get("video_files", [])
                    best_file = None
                    for vf in video_files:
                        if vf.get("file_type") == "video/mp4" or "mp4" in str(vf.get("link", "")):
                            w = int(vf.get("width") or 0)
                            h = int(vf.get("height") or 0)
                            if w >= 1280 or h >= 720:
                                best_file = vf
                                break
                    if not best_file and video_files:
                        best_file = video_files[0]

                    if best_file:
                        results.append({
                            "candidate_id": f"pexels_{v_id}",
                            "source": "pexels",
                            "download_url": best_file.get("link"),
                            "duration": dur,
                            "width": int(best_file.get("width") or width),
                            "height": int(best_file.get("height") or height),
                            "title": title,
                            "tags": tags,
                            "raw_meta": v,
                        })
        except Exception as e:
            print(f"[StockVideoService] Pexels search error: {e}")

        return results

    @classmethod
    def search_pixabay(
        cls,
        keywords: List[str],
        api_key: str,
        video_type: str = "all",
        per_page: int = 15,
    ) -> List[Dict[str, Any]]:
        """Searches Pixabay Video API."""
        if not api_key:
            return []

        query = " ".join(keywords[:4]) if keywords else "historical"
        params = urllib.parse.urlencode({
            "key": api_key,
            "q": query,
            "video_type": video_type,
            "per_page": per_page,
        })
        url = f"https://pixabay.com/api/videos/?{params}"

        req = urllib.request.Request(url, headers={"User-Agent": "PromptBeast/1.0"})

        results = []
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                data = json.loads(response.read().decode("utf-8"))
                for hit in data.get("hits", []):
                    h_id = str(hit.get("id", ""))
                    dur = float(hit.get("duration", 0.0))
                    tags_str = str(hit.get("tags", ""))
                    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                    title = tags_str

                    # Videos dict has: large, medium, small, tiny
                    videos = hit.get("videos", {})
                    chosen_vid = videos.get("large") or videos.get("medium") or videos.get("small")
                    if chosen_vid:
                        w = int(chosen_vid.get("width", 0))
                        h = int(chosen_vid.get("height", 0))
                        dl_url = chosen_vid.get("url")
                        if dl_url:
                            results.append({
                                "candidate_id": f"pixabay_{h_id}",
                                "source": "pixabay",
                                "download_url": dl_url,
                                "duration": dur,
                                "width": w,
                                "height": h,
                                "title": title,
                                "tags": tags,
                                "raw_meta": hit,
                            })
        except Exception as e:
            print(f"[StockVideoService] Pixabay search error: {e}")

        return results

    @classmethod
    def download_candidate(
        cls,
        candidate: Dict[str, Any],
        output_path: str,
        timeout: int = 30,
    ) -> Optional[str]:
        """Downloads a video candidate file to output_path."""
        dl_url = candidate.get("download_url")
        if not dl_url:
            return None

        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        try:
            req = urllib.request.Request(dl_url, headers={"User-Agent": "PromptBeast/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(out_p, "wb") as f:
                f.write(resp.read())
            candidate["file_path"] = str(out_p.resolve())
            return str(out_p.resolve())
        except Exception as e:
            print(f"[StockVideoService] Error downloading candidate {candidate.get('candidate_id')}: {e}")
            return None
