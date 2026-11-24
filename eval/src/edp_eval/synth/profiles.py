"""Drawing-standard profiles for synthetic drawings (OD-1: "try both" ISO and ASME).

The plan names ISO and ASME only as the standards to choose between (plan §11
question 1). The conventions below are generator settings, not plan values.
Which details each profile must follow is open as OD-41.
"""

from dataclasses import dataclass
from typing import Literal

ProfileName = Literal["iso", "asme"]


@dataclass(frozen=True)
class DrawingProfile:
    name: ProfileName
    projection: Literal["first_angle", "third_angle"]
    units: Literal["mm", "in"]
    insunits: int  # DXF $INSUNITS: 4 = millimetres, 1 = inches
    measurement: int  # DXF $MEASUREMENT: 1 = metric, 0 = imperial
    text_height: float
    arrow_size: float
    decimals: int
    general_tolerance: str
    materials: tuple[str, ...]

    def convert(self, value_mm: float) -> float:
        """Convert a generator value in millimetres to this profile's units."""
        return value_mm if self.units == "mm" else round(value_mm / 25.4, self.decimals)


PROFILES: dict[ProfileName, DrawingProfile] = {
    "iso": DrawingProfile(
        name="iso",
        projection="first_angle",
        units="mm",
        insunits=4,
        measurement=1,
        text_height=2.5,
        arrow_size=2.5,
        decimals=2,
        general_tolerance="ISO 2768-m",
        materials=("S235JR", "EN AW-5754", "1.4301"),
    ),
    "asme": DrawingProfile(
        name="asme",
        projection="third_angle",
        units="in",
        insunits=1,
        measurement=0,
        text_height=0.12,
        arrow_size=0.12,
        decimals=3,
        general_tolerance="ASME Y14.5; UNLESS OTHERWISE SPECIFIED .XXX = +/-.005",
        materials=("ASTM A36", "AL 6061-T6", "AISI 304"),
    ),
}
