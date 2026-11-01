#!/usr/bin/env python3
"""Generate an animated contribution-snake SVG for a GitHub profile.

Stdlib only, no token. Scrapes the public contribution calendar HTML,
rebuilds the 7 x 53 grid, then emits an SVG whose snake glides along
every contributed cell in boustrophedon order.

    python scripts/gen_snake.py Sakamuraa --out assets
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import urllib.request

PALETTE = {
    "dark": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
    "light": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
}
SNAKE = {"dark": "#58a6ff", "light": "#1f6feb"}
CELL, GAP, PAD = 10, 2, 8
DUR = "8s"

TD_RE = re.compile(r"<td\b[^>]*>", re.S)


def attr(tag: str, name: str) -> str | None:
    m = re.search(name + r'="([^"]*)"', tag)
    return m.group(1) if m else None


def fetch(username: str, start: dt.date, end: dt.date) -> str:
    url = (
        f"https://github.com/users/{username}/contributions"
        f"?from={start}&to={end}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "snake-gen/1.0"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", "replace")


def parse(html: str) -> list[tuple[dt.date, int]]:
    cells = []
    for tag in TD_RE.findall(html):
        date, level = attr(tag, "data-date"), attr(tag, "data-level")
        if date and level is not None and level.isdigit():
            cells.append((dt.date.fromisoformat(date), int(level)))
    if not cells:
        raise SystemExit("no contribution cells found - layout changed?")
    return cells


def to_grid(cells):
    first = min(d for d, _ in cells)
    first -= dt.timedelta(days=(first.weekday() + 1) % 7)  # back to Sunday
    pts: dict[tuple[int, int], int] = {}
    for date, level in cells:
        col = (date - first).days // 7
        row = (date.weekday() + 1) % 7  # Monday=0 -> Sunday=0
        pts[(col, row)] = level
    return pts, max(col for col, _ in pts) + 1


def snake_path(pts, cols: int) -> str:
    segs: list[str] = []
    pen: tuple[int, int] | None = None
    for col in range(cols):
        rows = range(7) if col % 2 == 0 else range(6, -1, -1)
        for row in rows:
            if pts.get((col, row), 0) <= 0:
                continue
            x = PAD + col * (CELL + GAP) + CELL / 2
            y = PAD + row * (CELL + GAP) + CELL / 2
            if pen and abs(pen[0] - col) + abs(pen[1] - row) == 1:
                segs.append(f"L{x:g} {y:g}")
            else:
                segs.append(f"M{x:g} {y:g}")
            pen = (col, row)
    return " ".join(segs)


def build(pts, cols: int, theme: str) -> str:
    fills = PALETTE[theme]
    w = PAD * 2 + cols * (CELL + GAP) - GAP
    h = PAD * 2 + 7 * (CELL + GAP) - GAP
    rects = []
    for (col, row), level in sorted(pts.items()):
        x = PAD + col * (CELL + GAP)
        y = PAD + row * (CELL + GAP)
        rects.append(
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
            f'rx="2" fill="{fills[min(level, 4)]}"/>'
        )
    path = snake_path(pts, cols)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="1.6" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <g>{''.join(rects)}</g>
  <path id="snake" d="{path}" fill="none" stroke="{SNAKE[theme]}" stroke-width="4"
        stroke-linecap="round" stroke-linejoin="round" pathLength="1000"
        stroke-dasharray="70 1000" filter="url(#glow)">
    <animate attributeName="stroke-dashoffset" from="0" to="-1070" dur="{DUR}"
             repeatCount="indefinite"/>
  </path>
  <circle r="3.4" fill="{SNAKE[theme]}" filter="url(#glow)">
    <animateMotion dur="{DUR}" repeatCount="indefinite" calcMode="linear"
                   keyPoints="0;1" keyTimes="0;1">
      <mpath href="#snake"/>
    </animateMotion>
  </circle>
</svg>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("username")
    ap.add_argument("--out", default="assets", type=pathlib.Path)
    ap.add_argument("--days", default=365, type=int)
    args = ap.parse_args()

    end = dt.date.today()
    start = end - dt.timedelta(days=args.days)
    pts, cols = to_grid(parse(fetch(args.username, start, end)))

    args.out.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        dest = args.out / f"snake-{theme}.svg"
        dest.write_text(build(pts, cols, theme), encoding="utf-8")
        print(f"{dest}  {cols} cols  {sum(1 for v in pts.values() if v)} active cells")


if __name__ == "__main__":
    main()
