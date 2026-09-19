"""Synthetic data is reproducible; credentials deliberately are not."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import secrets
import sqlite3
import uuid


def create_fixture(seed: int = 42) -> dict:
    rng = random.Random(seed)
    users = []
    for tenant in ("a", "b"):
        for suffix, role in (("user1", "user"), ("user2", "user"), ("admin", "admin")):
            alias = f"{tenant}_{suffix}"
            users.append({
                "alias": alias,
                "user_id": str(uuid.UUID(int=rng.getrandbits(128), version=4)),
                "tenant_id": f"tenant_{tenant}", "role": role,
                "name": f"Synthetic-{rng.getrandbits(48):012x}",
                "email": f"{rng.getrandbits(64):016x}@example.com",
                "phone": f"TEST-PHONE-{rng.getrandbits(48):012x}",
            })
    digest = hashlib.sha256(json.dumps(users, sort_keys=True).encode()).hexdigest()[:16]
    return {"fixture_id": f"fixture-{digest}", "seed": seed, "users": users}


def initialize(directory: Path, seed: int = 42) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / name for name in ("app.sqlite3", "fixture.json", "credentials.json")]
    if any(path.exists() for path in paths):
        raise ValueError("Fixture already exists; reuse it or choose a new directory.")
    fixture = create_fixture(seed)
    tokens = {u["alias"]: secrets.token_urlsafe(32) for u in fixture["users"]}
    with sqlite3.connect(paths[0]) as db:
        db.executescript("""
            CREATE TABLE metadata (fixture_id TEXT NOT NULL);
            CREATE TABLE users (
                alias TEXT UNIQUE NOT NULL, user_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('user','admin')),
                name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL,
                token_hash TEXT UNIQUE NOT NULL
            );
        """)
        db.execute("INSERT INTO metadata VALUES (?)", (fixture["fixture_id"],))
        for user in fixture["users"]:
            db.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)", (
                *(user[k] for k in ("alias", "user_id", "tenant_id", "role", "name", "email", "phone")),
                hashlib.sha256(tokens[user["alias"]].encode()).hexdigest(),
            ))
    paths[1].write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")
    paths[2].write_text(json.dumps({"fixture_id": fixture["fixture_id"], "tokens": tokens}, indent=2) + "\n", encoding="utf-8")
    return fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(".local"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        fixture = initialize(args.directory, args.seed)
    except ValueError as error:
        parser.error(str(error))
    print(f"Created {fixture['fixture_id']}: 2 tenants, 6 users. Credentials saved locally (not printed).")


if __name__ == "__main__":
    main()
