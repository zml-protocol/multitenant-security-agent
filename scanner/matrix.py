"""Fixed scope and independent, versioned authorization expectations."""
import json
from pathlib import Path
import uuid

RULES = Path(__file__).resolve().parents[1] / "fixtures" / "permissions.v1.json"
TEMPLATE = RULES.with_name("request-template.v1.json")


def load_template(fixture, template_path=TEMPLATE):
    template = json.loads(Path(template_path).read_text(encoding="utf-8"))
    if set(template) != {"version", "method", "path", "identity_alias", "target_alias"}:
        raise ValueError("Request template must use the fixed schema; arbitrary headers are forbidden")
    if template["method"] != "GET" or template["path"] != "/api/users/{user_id}":
        raise ValueError("Request template is outside the allowed method/path scope")
    users = {u["alias"]: u for u in fixture["users"]}
    if template["identity_alias"] not in users or template["target_alias"] not in users:
        raise ValueError("Request template references an unknown identity or user")
    return {**template, "path": template["path"].format(user_id=users[template["target_alias"]]["user_id"])}


def build_cases(fixture, rules_path=RULES):
    rules = json.loads(Path(rules_path).read_text(encoding="utf-8"))
    users = {user["alias"]: user for user in fixture["users"]}
    aliases = rules["aliases"]
    if len(users) != 6 or set(users) != set(aliases) or len(fixture["users"]) != 6:
        raise ValueError("Fixture must match the six configured identities")
    ids = [user["user_id"] for user in users.values()]
    if len(set(ids)) != 6:
        raise ValueError("User IDs must be unique")
    for user_id in ids:
        if str(uuid.UUID(user_id)) != user_id:
            raise ValueError("Only canonical UUID user IDs are allowed")
    cases = []

    def add(case_id, actor, path, allowed, kind, group="matrix", credential="valid", target=None):
        cases.append({"case_id": case_id, "actor": actor, "path": path, "kind": kind,
                      "allowed_aliases": allowed, "expected": "allow" if allowed else "deny",
                      "group": group, "credential": credential, "target": target})

    for actor in aliases:
        add(f"me:{actor}", actor, "/api/me", [actor], "me", target=actor)
        for target in aliases:
            allowed = [target] if target in rules["detail_allow"][actor] else []
            add(f"detail:{actor}:{target}", actor, f"/api/users/{users[target]['user_id']}", allowed, "detail", target=target)
        add(f"list:{actor}", actor, "/api/users", rules["list_allow"][actor], "list")
    for credential in ("missing", "invalid"):
        for kind, path in (("me", "/api/me"), ("detail", f"/api/users/{ids[0]}"), ("list", "/api/users")):
            add(f"auth:{credential}:{kind}", None, path, [], kind, "authentication", credential)
    return rules["version"], cases
