"""Parametric part families for synthetic drawings.

Families follow plan Phase 0 task 3, recommended for R1: "prismatic machined
parts and sheet-metal brackets" (working assumption for OD-12). Parameter ranges
are generator settings in millimetres, not plan values.
"""

import random
from dataclasses import dataclass, field
from typing import Literal

Family = Literal["plate", "bracket"]
FAMILIES: tuple[Family, ...] = ("plate", "bracket")


@dataclass(frozen=True)
class Hole:
    x: float  # from the left edge
    y: float  # from the bottom edge
    diameter: float


@dataclass(frozen=True)
class Plate:
    """Prismatic plate with a hole pattern and an optional centre slot."""

    length: float
    width: float
    thickness: float
    holes: tuple[Hole, ...]
    slot_length: float | None = None
    slot_width: float | None = None
    family: Family = field(default="plate", init=False)


@dataclass(frozen=True)
class Bracket:
    """Sheet-metal L-bracket: vertical flange A, horizontal flange B, one bend."""

    flange_a: float  # outer height
    flange_b: float  # outer length
    width: float
    thickness: float
    bend_radius: float  # inner radius
    hole: Hole  # in flange B, x from the outer back face
    family: Family = field(default="bracket", init=False)


Part = Plate | Bracket


def sample_plate(rng: random.Random) -> Plate:
    length = rng.randrange(60, 205, 5)
    width = rng.randrange(40, 125, 5)
    thickness = rng.choice((5, 6, 8, 10, 12))
    diameter = rng.choice((5.5, 6.6, 9.0, 11.0))
    inset = rng.choice((8, 10, 12, 15))
    corners = [
        (inset, inset),
        (length - inset, inset),
        (length - inset, width - inset),
        (inset, width - inset),
    ]
    count = rng.choice((2, 4))
    holes = tuple(Hole(float(x), float(y), diameter) for x, y in corners[:count])
    slot_length = slot_width = None
    if rng.random() < 0.5 and length >= 100 and width >= 60:
        slot_length = float(rng.randrange(20, 45, 5))
        slot_width = float(rng.choice((6, 8, 10)))
    return Plate(float(length), float(width), float(thickness), holes, slot_length, slot_width)


def sample_bracket(rng: random.Random) -> Bracket:
    thickness = rng.choice((1.5, 2.0, 2.5, 3.0))
    bend_radius = thickness * rng.choice((1.0, 1.5))
    flange_a = float(rng.randrange(30, 85, 5))
    flange_b = float(rng.randrange(40, 105, 5))
    width = float(rng.randrange(30, 85, 5))
    diameter = rng.choice((5.5, 6.6, 9.0))
    min_x = thickness + bend_radius + diameter
    hole = Hole(x=round(rng.uniform(min_x, flange_b - diameter), 1), y=width / 2, diameter=diameter)
    return Bracket(flange_a, flange_b, width, thickness, bend_radius, hole)


def sample(family: Family, rng: random.Random) -> Part:
    return sample_plate(rng) if family == "plate" else sample_bracket(rng)
