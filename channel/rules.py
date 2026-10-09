"""Deterministic channel rules. Original conversation is retained in japan_rules.json."""
import copy
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PROFILE = json.loads((ROOT / "profiles/japan_v1.0.json").read_text(encoding="utf-8"))
FORBIDDEN = r"必ず儲かる|保証|絶対|最強|まさに|徹底|No\.1|[!！]"
TTS_FORBIDDEN = r"[〜～()（）\[\]［］→％%/Ａ-Ｚａ-ｚA-Za-z]"
ENDINGS = sorted(["です", "ます", "ました", "ません", "んです", "んですね", "ましょう", "ますよね", "てください"], key=len, reverse=True)


def profile_snapshot():
    profile = copy.deepcopy(PROFILE)
    profile["bible"] = (ROOT / "prompts/bible_v1.0.txt").read_text(encoding="utf-8")
    profile["narration_guide"] = (ROOT / "prompts/narration_v1.0.txt").read_text(encoding="utf-8")
    return profile


def system_prompt(profile):
    return profile["bible"] + "\n" + profile["narration_guide"] + (
        "\nQUY TẮC GIẢI QUYẾT MÂU THUẪN: opening và disclaimer cố định được chèn bằng code. "
        "Chỉ hai chuỗi cố định này được miễn kiểm tra độ dài câu; chữ 保証 chỉ được phép trong disclaimer nguyên văn. "
        "Không sao chép số liệu ví dụ trong tài liệu thành sự thật. Không tự bịa nguồn hoặc URL. "
        "Chỉ dùng số liệu có trong tài liệu nguồn người dùng cung cấp; thiếu nguồn thì nói định tính, ghi needs_research. "
        "Ngày tham chiếu lấy từ yêu cầu hiện tại, không cố định năm 2026. "
        "Không sao chép mẫu hứa hẹn lợi nhuận. Mascot ghép từ PNG cố định, không sinh trong ảnh nền."
    )


def image_prompt(text, profile):
    # Repeated application does not stack style prefixes.
    text = str(text).strip()
    if text.startswith(profile["style_lock"]):
        text = text[len(profile["style_lock"]):].lstrip(". ")
    if text.endswith(profile["negative"]):
        text = text[:-len(profile["negative"])].rstrip(". ")
    return f"{profile['style_lock']}. {text}. {profile['negative']}"


def sentences(text):
    return [s.strip() for s in re.findall(r"[^。！？!?\n]+[。！？!?]?", text) if s.strip()]


def narration_issues(text, profile):
    # Fixed legal/brand copy is a narrowly scoped exception, never a global exemption.
    text = text.replace(profile["opening"], "").replace(profile["disclaimer"], "")
    issues = []
    for pattern, label in [(FORBIDDEN, "Từ quảng bá hoặc dấu than bị cấm"),
                           (TTS_FORBIDDEN, "Ký tự cần viết lại cho TTS"),
                           (r"することができます|させていただ[くき]|なのです", "Văn phong máy hoặc quá trang trọng")]:
        if re.search(pattern, text):
            issues.append(label)
    parts = sentences(text)
    if any(len(s.rstrip("。！？!?")) > profile["max_sentence"] for s in parts):
        issues.append("Câu dài hơn 45 ký tự")
    tails = [next((ending for ending in ENDINGS if s.rstrip("。！？!?").endswith(ending)), None) for s in parts]
    if any(tails[i] and tails[i] == tails[i+1] == tails[i+2] for i in range(len(tails)-2)):
        issues.append("Lặp cùng đuôi câu 3 lần")
    if sum(bool(re.match(r"(?:しかしながら|また、|さらに、|したがって|なぜなら)", s)) for s in parts) > 1:
        issues.append("Quá nhiều liên từ văn viết")
    if len(re.findall(r"[?？]", text)) > 1:
        issues.append("Quá 1 câu hỏi trong cảnh")
    if text.count("……") > 1:
        issues.append("Quá 1 khoảng nghỉ …… trong cảnh")
    return issues


def scene_issues(scenes, profile):
    errors, ids = [], set()
    if not isinstance(scenes, list) or not scenes:
        return ["Kịch bản chưa có cảnh"]
    types = []
    for sc in scenes:
        if not isinstance(sc, dict):
            errors.append("Cảnh phải là object"); continue
        sid = sc.get("id", "")
        if not isinstance(sid, str) or not re.fullmatch(r"SC\d{2,4}", sid) or sid in ids:
            errors.append("ID cảnh không hợp lệ hoặc trùng")
        ids.add(str(sid))
        types.append(sc.get("type"))
        if sc.get("type") not in ("hook", "intro", "item", "mid", "recap", "outro"):
            errors.append(f"{sid}: loại cảnh không hợp lệ")
        if sc.get("emotion") not in profile["poses"]:
            errors.append(f"{sid}: biểu cảm không hợp lệ")
        telop, vo, visual = sc.get("telop"), sc.get("vo"), sc.get("visual_prompt")
        if not isinstance(telop, str) or not 1 <= len(telop) <= profile["max_telop"] or re.search(FORBIDDEN, telop or ""):
            errors.append(f"{sid}: telop phải 1–13 ký tự, không từ cấm")
        if not isinstance(vo, str) or not vo.strip():
            errors.append(f"{sid}: thiếu lời đọc")
        else:
            errors.extend(f"{sid}: {e}" for e in narration_issues(vo, profile))
            if sc.get("type") == "hook" and (len(re.findall(r"[?？]", vo)) != 1 or not re.search(r"\d|[一二三四五六七八九十]", vo)):
                errors.append(f"{sid}: hook cần đúng 1 câu hỏi và teaser có số")
        if not isinstance(visual, str) or not visual.strip():
            errors.append(f"{sid}: thiếu mô tả ảnh nền")
        if sc.get("type") == "item" and (type(sc.get("number")) is not int or sc["number"] < 1):
            errors.append(f"{sid}: mục cần số nguyên dương")
    if types[:2] != ["hook", "intro"] or types[-2:] != ["recap", "outro"] or "mid" not in types or "item" not in types:
        errors.append("Thứ tự cần hook → intro → item → mid → item → recap → outro")
    for kind in ("hook", "intro", "mid", "recap", "outro"):
        if types.count(kind) != 1:
            errors.append(f"Cần đúng 1 cảnh {kind}")
    item_numbers = [sc.get("number") for sc in scenes if isinstance(sc, dict) and sc.get("type") == "item"]
    if item_numbers != list(range(1, len(item_numbers)+1)):
        errors.append("Số thứ tự item phải liên tục từ 1")
    if "mid" in types and ("item" not in types[:types.index("mid")] or "item" not in types[types.index("mid")+1:]):
        errors.append("Checkpoint mid phải nằm giữa các item")
    intros = [sc for sc in scenes if isinstance(sc, dict) and sc.get("type") == "intro"]
    if intros and (not isinstance(intros[0].get("vo"), str) or not intros[0]["vo"].startswith(profile["opening"] + profile["disclaimer"])):
        errors.append("Intro phải bắt đầu bằng opening và disclaimer cố định")
    return errors


def seo_issues(seo, profile, keyword=""):
    if not isinstance(seo, dict):
        return ["SEO phải là object"]
    errors = []
    titles = seo.get("titles", [])
    if not isinstance(titles, list) or len(titles) != 3:
        errors.append("Cần đúng 3 tiêu đề")
        titles = []
    for title in titles:
        if (not isinstance(title, str) or not 1 <= len(title) <= profile["max_title"] or
                not re.search(r"\d", title) or not re.search(r"【.+?】", title) or
                re.search(FORBIDDEN, title) or (keyword and keyword not in title)):
            errors.append("Tiêu đề phải ≤48 ký tự, chứa số, 【】 và từ khóa, không từ cấm")
    tags = seo.get("tags", [])
    if not isinstance(tags, list) or len(tags) != 15 or not all(isinstance(t, str) and t.strip() for t in tags) or len(set(str(t) for t in tags)) != 15:
        errors.append("Cần đúng 15 tags khác nhau")
    description = seo.get("description", "")
    if not isinstance(description, str) or not description.strip():
        errors.append("Thiếu mô tả")
    elif re.search(FORBIDDEN, description.replace(profile["disclaimer"], "")):
        errors.append("Mô tả có từ cấm")
    if not isinstance(seo.get("pinned_comment"), str) or len(re.findall(r"[?？]", seo.get("pinned_comment", ""))) != 1:
        errors.append("Bình luận ghim cần 1 câu hỏi mở")
    return errors


def thumb_issues(lines, profile):
    if not isinstance(lines, list) or not 1 <= len(lines) <= 2:
        return ["Thumbnail cần 1–2 dòng"]
    if any(not isinstance(t, str) or not 1 <= len(t) <= profile["max_thumb_line"] or re.search(FORBIDDEN, t) for t in lines):
        return ["Chữ thumbnail phải ≤14 ký tự/dòng, không từ cấm"]
    return []
