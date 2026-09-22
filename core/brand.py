"""
Brand constants and mascot locks for JP Faceless YouTube Factory.
"""

# MASCOT_LOCK: phải nối vào MỌI image prompt để khóa nhân vật đồng nhất
MASCOT_LOCK = (
    "same character exactly as reference sheet: middle-aged Japanese businessman mascot, "
    "silver-gray hair, round friendly face, gray suit, white shirt, green tie"
)

# STYLE_LOCK: khóa phong cách minh họa
STYLE_LOCK = (
    "flat corporate cartoon vector illustration, clean thick outlines, bright "
    "saturated colors, simple background, Japanese YouTube explainer style, NO text, "
    "NO letters, NO watermark"
)

# Font settings
FONT_JP = "Noto Sans JP"
FONT_JP_HEAVY = "Noto Sans JP Black"

# Narration speed: ký tự/phút
CHAR_RATE_CPM = 320

# Disclaimer cố định (nhúng vào kịch bản & description)
DISCLAIMER_JP = (
    "この動画は情報整理と紹介が目的で、投資勧誘や利益の保証ではありません。"
    "成果は地域と運営次第で変わります。"
)

# Video specs
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30

# Thumbnail specs
THUMB_WIDTH = 1280
THUMB_HEIGHT = 720
