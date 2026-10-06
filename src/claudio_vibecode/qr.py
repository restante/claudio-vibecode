"""QR codes for pairing: plain text blocks for the terminal and an SVG page for the desktop."""

from __future__ import annotations

import io

import segno


def text(url: str, invert: bool = False) -> str:
    """The QR as half-block characters (two rows per line). `invert` for light terminals."""
    matrix = [list(row) for row in segno.make(url, error="m").matrix]
    border = 2
    width = len(matrix[0]) + 2 * border
    grid = [[0] * width for _ in range(border)]
    grid += [[0] * border + [int(bool(v)) for v in row] + [0] * border for row in matrix]
    grid += [[0] * width for _ in range(border)]
    if len(grid) % 2:
        grid.append([0] * width)
    # Dark modules are drawn as spaces and light ones as blocks (right for a dark terminal).
    glyph = {(0, 0): "█", (1, 1): " ", (0, 1): "▀", (1, 0): "▄"}
    if invert:
        glyph = {(1, 1): "█", (0, 0): " ", (1, 0): "▀", (0, 1): "▄"}
    lines = []
    for top, bottom in zip(grid[0::2], grid[1::2], strict=True):
        lines.append("".join(glyph[(a, b)] for a, b in zip(top, bottom, strict=True)))
    return "\n".join(lines)


def svg(url: str) -> str:
    out = io.BytesIO()
    segno.make(url, error="m").save(out, kind="svg", scale=8, border=3, xmldecl=False)
    return out.getvalue().decode()
