"""Default authorization policy shipped with the application."""


def authorize_list(actor):
    if actor["role"] != "admin":
        return False, "admin_required"
    return True, "tenant_administrator"


def authorize_detail(actor, target):
    if actor["tenant_id"] != target["tenant_id"]:
        return False, "tenant_boundary"
    if actor["user_id"] == target["user_id"] or actor["role"] == "admin":
        return True, "self_or_tenant_administrator"
    return False, "owner_required"
