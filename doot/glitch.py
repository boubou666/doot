"""Rythme et images du doot numerique, sans dependance graphique."""

from __future__ import annotations

from . import png


STEP_MS = 80
STEPS = 8


def phase(elapsed_ms: int) -> int:
    return max(0, int(elapsed_ms)) // STEP_MS % STEPS


def frames(source: png.Frame) -> list[png.Frame]:
    """Bandes dechirees et separation rouge/cyan sur une toile stable.

    Les retours a l'image intacte rendent les parasites irreguliers sans
    clignotement plein ecran. Les pixels restent en BGRA premultiplie.
    """
    width, height, data = source.width, source.height, source.data
    result = []
    unit = max(1, width // 65)
    band = max(1, height // 18)
    for step in range(STEPS):
        if step in (0, 4, 7):
            result.append(source)
            continue
        out = bytearray(len(data))
        split = unit * (1 if step == 1 else 2)
        for y in range(height):
            strip = y // band
            shift = (((strip * 7 + step * 3) % 9) - 4) * unit
            if (strip + step) % 3:
                shift //= 3
            # Quelques lignes coupees, jamais toute l'image.
            if step in (3, 6) and (y + step * band) % (band * 5) < max(1, band // 4):
                continue
            row = y * width * 4
            for x in range(width):
                sx = x - shift
                red_x, cyan_x = sx - split, sx + split
                red = row + red_x * 4 if 0 <= red_x < width else None
                cyan = row + cyan_x * 4 if 0 <= cyan_x < width else None
                target = row + x * 4
                if cyan is not None:
                    out[target:target + 2] = data[cyan:cyan + 2]
                if red is not None:
                    out[target + 2] = data[red + 2]
                out[target + 3] = max(
                    data[red + 3] if red is not None else 0,
                    data[cyan + 3] if cyan is not None else 0,
                )
        result.append(png.Frame(width, height, bytes(out)))
    return result


def text(source: str, step: int) -> str:
    """Dechire aussi l'ASCII et le grand DOOT du mode muet."""
    lines = source.splitlines()
    width = max((len(line) for line in lines), default=0)
    step %= STEPS
    result = []
    for index, line in enumerate(lines):
        line = line.ljust(width)
        if step not in (0, 4, 7):
            shift = ((index * 3 + step) % 5) - 2
            line = ((" " * shift + line)[:width] if shift >= 0
                    else line[-shift:].ljust(width))
            if line.strip() and (index + step) % 3 == 0:
                pos = next(i for i, char in enumerate(line) if char != " ")
                line = line[:pos] + "#" + line[pos + 1:]
        result.append(line)
    return "\n".join(result)
