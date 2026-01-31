from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class UserId:
    """Value object representing a user identifier"""

    value: int

    def __post_init__(self):
        if not isinstance(self.value, int) or self.value <= 0:
            raise ValueError("UserId must be a positive integer")

    @classmethod
    def from_int(cls, value: int) -> "UserId":
        """Create UserId from integer"""
        return cls(value)

    @classmethod
    def from_str(cls, value: str) -> "UserId":
        """Create UserId from string"""
        try:
            return cls(int(value))
        except ValueError:
            raise ValueError(f"Invalid UserId string: {value}")

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)
