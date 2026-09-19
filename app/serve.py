"""Local-only launcher with structured application audit logs."""
import logging
import os

import uvicorn

from app.main import create_app
from evaluation.operator import load_policy


def create_configured_app():
    reference = os.getenv("LAB_SCENARIO", os.getenv("LAB_MODE", "secure"))
    return create_app(policy=load_policy(reference))


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run("app.serve:create_configured_app", factory=True, host="127.0.0.1", port=8000, access_log=False)


if __name__ == "__main__":
    main()
