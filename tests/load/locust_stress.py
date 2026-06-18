# стресс: locust -f tests/load/locust_stress.py --headless
from common import MonkeyUser  # noqa: F401
from shapes import StressShape  # noqa: F401
