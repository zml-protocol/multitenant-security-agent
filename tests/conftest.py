import json

import pytest

from app.seed import initialize


@pytest.fixture
def lab(tmp_path):
    fixture = initialize(tmp_path)
    credentials = json.loads((tmp_path / "credentials.json").read_text())
    return tmp_path, fixture, credentials
