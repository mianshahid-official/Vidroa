import json
import re
import difflib
from pathlib import Path

def test():
    speech_path = Path("audio and files/speech.json")
    sample_path = Path("sample data.txt")

    if not speech_path.exists() or not sample_path.exists():
        print("Files not found")
        return

    with open(speech_path, "r", encoding="utf-8") as f:
        words = json.load(f)["words"]

    with open(sample_path, "r", encoding="utf-8") as f:
        txt = f.read()

    visuals = re.findall(r"Visual\s+(\d+)\s+Words:\s*(.*?)\s*Visual:\s*(.*?)(?=Visual\s+\d+\s+Words:|$)", txt, re.DOTALL)
    print(f"Total visuals parsed from text: {len(visuals)}")

    def norm(t):
        t = t.lower()
        t = re.sub(r"\b(sixty|60)\b", "60", t)
        t = re.sub(r"\b(twenty|20)\b", "20", t)
        t = re.sub(r"\b(four|4)\b", "4", t)
        t = re.sub(r"\b(three|3)\b", "3", t)
        t = re.sub(r"\b(two|2)\b", "2", t)
        t = re.sub(r"\b(one|1)\b", "1", t)
        t = re.sub(r"[^\w\s]", "", t)
        return " ".join(t.split())

    full_speech_norm = [norm(w["word"]) for w in words]

    curr_w_idx = 0
    aligned = []

    for v_num, v_words, v_vis in visuals:
        v_norm = norm(v_words).split()
        if not v_norm:
            continue

        best_start = curr_w_idx
        best_len = max(1, len(v_norm))
        best_score = 0.0

        search_limit = min(len(words), curr_w_idx + 80)
        target_str = " ".join(v_norm)

        for s_idx in range(curr_w_idx, search_limit):
            for length in range(max(1, len(v_norm) - 2), min(len(v_norm) + 4, len(words) - s_idx + 1)):
                sub = " ".join(full_speech_norm[s_idx:s_idx+length])
                score = difflib.SequenceMatcher(None, target_str, sub).ratio()
                if score > best_score:
                    best_score = score
                    best_start = s_idx
                    best_len = length
                if score > 0.85:
                    break
            if best_score > 0.85:
                break

        end_idx = min(len(words) - 1, best_start + best_len - 1)
        start_time = words[best_start]["start"]
        end_time = words[end_idx]["end"]
        # Ensure duration is at least 0.5s
        if end_time <= start_time:
            end_time = start_time + 1.0

        curr_w_idx = end_idx + 1
        aligned.append({
            "visual_id": int(v_num),
            "start": round(start_time, 2),
            "end": round(end_time, 2),
            "duration": round(end_time - start_time, 2),
            "words": v_words.strip(),
            "visual_idea": v_vis.strip(),
            "score": round(best_score, 2)
        })

    print(f"Total visuals successfully aligned: {len(aligned)} / {len(visuals)}")
    low_scores = [a for a in aligned if a["score"] < 0.6]
    print(f"Matches with score < 0.6: {len(low_scores)}")
    for a in aligned[:5]:
        print(f"Visual {a['visual_id']}: [{a['start']}s -> {a['end']}s] ({a['duration']}s) score={a['score']} | {a['words'][:35]}...")
    print("...")
    for a in aligned[-3:]:
        print(f"Visual {a['visual_id']}: [{a['start']}s -> {a['end']}s] ({a['duration']}s) score={a['score']} | {a['words'][:35]}...")

if __name__ == "__main__":
    test()

