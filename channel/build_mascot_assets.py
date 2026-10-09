"""Rebuild the fixed, editable vector mascot set as transparent PNG assets.

Run: python -m channel.build_mascot_assets
The same five source illustrations are reused across episodes; no generation API.
"""
from pathlib import Path
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parent / "assets" / "mascot"


def svg_for(pose):
    eyes = ('<path d="M187 245 Q204 260 221 245 M293 245 Q310 260 327 245" fill="none"/>' if pose == "sleep" else
            '<ellipse cx="204" cy="247" rx="10" ry="16" fill="#26364a"/><ellipse cx="310" cy="247" rx="10" ry="16" fill="#26364a"/>')
    mouth = ('<ellipse cx="257" cy="308" rx="20" ry="25" fill="#774d43"/>' if pose == "surprised" else
             '<path d="M233 305 Q257 328 282 303" fill="none"/>' if pose in ("smile", "point") else
             '<path d="M243 311 Q257 304 271 311" fill="none"/>')
    arm = ('<path d="M374 445 Q421 423 422 361 L422 286 Q422 267 434 267 Q447 267 447 285 L447 331 Q472 323 481 347 L475 410 Q457 476 392 502" fill="#f0c6a7"/>' if pose == "point" else
           '<path d="M382 506 Q347 448 287 374 L267 349 Q253 332 265 321 Q277 310 291 328 L310 347 Q330 333 344 351 L392 425 Q427 465 421 496" fill="#f0c6a7"/>' if pose == "think" else
           '<path d="M116 463 Q69 417 67 372 L59 321 Q56 305 68 302 Q83 299 88 318 L95 339 L95 294 Q95 277 109 277 Q122 277 122 293 L126 337 Q147 326 158 345 L153 410 L166 440" fill="#f0c6a7"/>' if pose == "surprised" else
           '<path d="M131 470 Q106 531 143 557 L200 565 Q220 560 213 541 L170 525 L180 482" fill="#f0c6a7"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="640" viewBox="0 0 512 640">
<g stroke="#24354b" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">
<path d="M116 639 L112 464 Q117 414 178 394 L216 376 L295 376 L340 394 Q397 412 407 466 L423 639" fill="#1F3864"/>
<path d="M216 378 L255 421 L296 378 L319 411 L291 639 L224 639 L196 411" fill="#fffdf5"/>
<path d="M246 420 L268 420 L278 450 L266 479 L285 609 L259 633 L237 609 L247 477 L237 452 Z" fill="#43816b"/>
<path d="M181 394 L151 450 L192 467 L174 487 L223 620 L207 420 Z M335 394 L367 450 L325 467 L344 487 L291 620 L309 420 Z" fill="#294b7e"/>
<path d="M216 344 L216 380 Q254 422 296 380 L296 344" fill="#e8b999"/>
<ellipse cx="151" cy="254" rx="25" ry="38" fill="#efc4a6"/><ellipse cx="363" cy="254" rx="25" ry="38" fill="#efc4a6"/>
<path d="M154 181 Q158 95 256 95 Q352 95 361 185 L355 286 Q347 363 258 377 Q174 365 157 288 Z" fill="#f2cfb3"/>
<path d="M156 226 Q127 172 149 129 Q148 91 200 77 Q224 49 273 70 Q340 65 366 124 Q386 174 361 226 L339 184 Q291 170 259 124 Q229 174 166 179 Z" fill="#c8ced5"/>
<path d="M164 153 Q213 144 255 102 M170 129 Q209 122 232 98 M281 101 Q301 147 347 156" fill="none" stroke="#929fac" stroke-width="5"/>
<path d="M182 216 Q202 204 224 214 M289 213 Q311 205 333 218" fill="none" stroke="#7e8791" stroke-width="9"/>
{eyes}
<path d="M258 250 L248 283 Q258 290 271 283" fill="none" stroke="#b58770" stroke-width="4"/>
<path d="M178 282 L188 287 M323 286 L335 280" fill="none" stroke="#ca9c80" stroke-width="4"/>
{mouth}
<path d="M145 467 L136 518 M380 468 L389 530" fill="none" stroke="#45648e" stroke-width="4"/>
{arm}
<path d="M303 507 L347 507" stroke="#e0e4e7" stroke-width="5"/>
<circle cx="259" cy="598" r="4" fill="#c8ced5" stroke="none"/>
</g></svg>'''


def build():
    ASSETS.mkdir(parents=True, exist_ok=True)
    for pose in ("surprised", "point", "smile", "think", "sleep"):
        source = svg_for(pose)
        (ASSETS / f"mascot_{pose}.svg").write_text(source, encoding="utf-8")
        renderer = QSvgRenderer(QByteArray(source.encode()))
        image = QImage(512, 640, QImage.Format_ARGB32); image.fill(Qt.transparent)
        painter = QPainter(image); renderer.render(painter); painter.end()
        if not image.save(str(ASSETS / f"mascot_{pose}.png")):
            raise RuntimeError("Không ghi được mascot PNG")


if __name__ == "__main__": build()
