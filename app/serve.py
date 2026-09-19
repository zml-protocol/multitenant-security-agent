"""Local-only launcher with structured application audit logs."""
import logging

import uvicorn


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run("app.main:create_app", factory=True, host="127.0.0.1", port=8000, access_log=False)


if __name__ == "__main__":
    main()
