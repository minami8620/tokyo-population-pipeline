from datetime import date
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
AS_OF = date(2026, 9, 1)


@pytest.fixture
def population_raw() -> bytes:
    return (FIXTURES / "population_2026-09.csv").read_bytes()


@pytest.fixture
def movement_raw() -> bytes:
    return (FIXTURES / "movement_2026-09.csv").read_bytes()
