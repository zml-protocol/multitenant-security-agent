"""Load scenario truth for operator demos; never copy this module into a reviewer bundle."""
import importlib
import json
from pathlib import Path


TRUTH_PATH = Path(__file__).with_name("operator-truth.json")


def catalog():
    return json.loads(TRUTH_PATH.read_text(encoding="utf-8"))["scenarios"]


def scenario_record(reference):
    scenarios = catalog()
    if reference in scenarios:
        return {"label": reference, **scenarios[reference]}
    for label, record in scenarios.items():
        if record["scenario_id"] == reference:
            return {"label": label, **record}
    raise ValueError("Unknown evaluation scenario")


def load_policy(reference):
    return importlib.import_module(scenario_record(reference)["module"])
