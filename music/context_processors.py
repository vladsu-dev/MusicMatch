from __future__ import annotations

from .services import matches_for, profile_for


def navigation(request):
    member = getattr(request, "member", None)
    if member is None:
        return {"member": None, "member_profile": None, "match_count": 0}
    profile = profile_for(member)
    try:
        match_count = matches_for(member).count()
    except Exception:
        match_count = 0
    return {"member": member, "member_profile": profile, "match_count": match_count}
