"""Grid layout shared by look.py (preview sheets) and montage.py (compositions).

Builds one magick argv - no montage/compare sub-commands, only `magick` image
operators that behave the same on ImageMagick 6 (through a `magick` shim) and 7.
Every cell is exactly cell_w x cell_h (plus a label strip), so the sheet's size is
known before anything runs and can be checked afterwards.
"""
import math

from _common import escape_magick_text


def grid_shape(count, cols):
    cols = max(1, min(cols, count))
    return cols, math.ceil(count / cols)


def sheet_size(count, cols, cell_w, cell_h, gap, label_h):
    cols, rows = grid_shape(count, cols)
    return cols * cell_w + (cols - 1) * gap, rows * (cell_h + label_h) + (rows - 1) * gap


def _cell(path, cell_w, cell_h, background, checker, shrink_only, label, font, label_h, left_gap):
    box = f"{cell_w}x{cell_h}>" if shrink_only else f"{cell_w}x{cell_h}"
    image = [f"{path}[0]", "-auto-orient", "-resize", box]
    if checker:
        # Transparency shows as a checkerboard under the image's own area (and only there,
        # so letterboxing around an opaque image is never mistaken for transparency).
        image += ["(", "+clone", "-tile", "pattern:checkerboard", "-draw", "color 0,0 reset", ")",
                  "+swap", "-compose", "over", "-composite"]
    parts = ["("] + image + ["-background", background, "-gravity", "center", "-extent", f"{cell_w}x{cell_h}"]
    if label is not None:
        parts += [
            "(", "-background", "white", "-fill", "black", "-font", font,
            "-size", f"{cell_w}x{label_h}", "-gravity", "center", f"label:{escape_magick_text(label)}", ")",
            "-gravity", "northwest", "-append",
        ]
    if left_gap:
        # Inside the cell's own parentheses: -splice acts on every image in the current
        # list, and outside them that list also holds the row built so far.
        parts += ["-background", background, "-gravity", "northwest", "-splice", f"{left_gap}x0"]
    return parts + [")"]


def grid_command(magick, paths, output, cols, cell_w, cell_h, background, gap=0, checker=False,
                 shrink_only=True, labels=None, font=None, label_h=0):
    """argv that writes `paths` as a cols-wide grid of cell_w x cell_h cells to `output`.

    labels: None, or one string per path rendered under its cell with `font`.
    """
    cols, rows = grid_shape(len(paths), cols)
    cmd = [magick]
    for r in range(rows):
        row_paths = paths[r * cols:(r + 1) * cols]
        cmd.append("(")
        for c, path in enumerate(row_paths):
            label = labels[r * cols + c] if labels else None
            cmd += _cell(path, cell_w, cell_h, background, checker, shrink_only, label, font, label_h,
                         gap if c > 0 else 0)
            if c > 0:
                cmd += ["-gravity", "northwest", "+append"]
        if r > 0 and gap:
            cmd += ["-background", background, "-gravity", "northwest", "-splice", f"0x{gap}"]
        cmd.append(")")
        if r > 0:
            cmd += ["-background", background, "-gravity", "northwest", "-append"]
    width, height = sheet_size(len(paths), cols, cell_w, cell_h, gap, label_h)
    # A short last row is narrower than the others; -append pads it with the background,
    # and -extent pins the sheet to the size computed above in every case.
    cmd += ["-background", background, "-gravity", "northwest", "-extent", f"{width}x{height}", output]
    return cmd
