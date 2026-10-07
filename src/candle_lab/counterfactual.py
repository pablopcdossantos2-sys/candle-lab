from __future__ import annotations

import random


def _bridge(start: int, end: int, low: int, high: int, steps: int, rng: random.Random) -> list[int]:
    if steps <= 0:
        return [end]
    out: list[int] = []
    current = start
    for i in range(steps):
        remaining = steps - i
        if remaining <= abs(end - current):
            current += 1 if end > current else -1 if end < current else 0
        else:
            candidates = [x for x in (current - 1, current, current + 1) if low <= x <= high]
            candidates.extend([current + (1 if end > current else -1 if end < current else 0)] * 2)
            candidates = [x for x in candidates if low <= x <= high]
            current = rng.choice(candidates)
        out.append(current)
    out[-1] = end
    return out


def generate_ohlc_path(
    open_ticks: int,
    high_ticks: int,
    low_ticks: int,
    close_ticks: int,
    points: int = 64,
    seed: int | None = None,
) -> list[int]:
    """Gera um caminho discreto compatível com OHLC."""
    if not (low_ticks <= open_ticks <= high_ticks and low_ticks <= close_ticks <= high_ticks):
        raise ValueError("OHLC inconsistente")
    if points < 4:
        raise ValueError("points deve ser >= 4")

    rng = random.Random(seed)
    extrema = [high_ticks, low_ticks]
    rng.shuffle(extrema)
    anchors = [open_ticks, *extrema, close_ticks]

    remaining = points - 1
    base = remaining // 3
    counts = [base, base, remaining - 2 * base]

    path = [open_ticks]
    for target, n in zip(anchors[1:], counts):
        path.extend(_bridge(path[-1], target, low_ticks, high_ticks, n, rng))

    path[0] = open_ticks
    path[-1] = close_ticks
    if high_ticks not in path or low_ticks not in path:
        raise AssertionError("Falha interna ao visitar extremos")
    if max(path) != high_ticks or min(path) != low_ticks:
        raise AssertionError("Falha interna nos limites OHLC")
    return path
