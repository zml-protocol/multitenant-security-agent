"""Authorization policy implementation for a neutral evaluation scenario."""


def authorize_list(actor):
    if actor["role"] != "admin":
        return False, "admin_required"
    return True, "tenant_administrator"


def authorize_detail(actor, target):
    if actor["tenant_id"] != target["tenant_id"]:
        return False, "tenant_boundary"
    return True, "tenant_member"
