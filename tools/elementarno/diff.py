"""Cross-image difference extraction.

The entertainment core of the "who did it" genre is not the single frame but
the change between frames. Explicit diffs give the rule layer something
deterministic to reason over instead of a vague impression of difference.
"""

from .paths import resolve


def _key(obj):
    return (obj.get("category", ""), obj.get("material", ""))


def _bbox(region):
    box = region.get("bbox")
    return box if isinstance(box, list) and len(box) == 4 else None


def _iou(a, b):
    if not a or not b:
        return 0.0
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _match_regions(before, after):
    pairs, removed, added = [], [], list(after)
    for region in before:
        best, best_score = None, 0.0
        for candidate in added:
            if candidate.get("kind") != region.get("kind"):
                continue
            score = _iou(_bbox(region), _bbox(candidate))
            if score > best_score:
                best, best_score = candidate, score
        if best is not None and best_score >= 0.3:
            added.remove(best)
            pairs.append((region, best))
        else:
            removed.append(region)
    return pairs, removed, added


def diff_scenes(before, after):
    changes = []

    before_objs = list(before.get("objects", []))
    after_objs = list(after.get("objects", []))
    matched_after = set()

    for obj in before_objs:
        candidates = [o for o in after_objs if id(o) not in matched_after and _key(o) == _key(obj)]
        if candidates:
            match = candidates[0]
            matched_after.add(id(match))
            if obj.get("on") != match.get("on"):
                changes.append({
                    "kind": "object_moved",
                    "category": obj.get("category"),
                    "object_id": obj.get("id"),
                    "from": obj.get("on"),
                    "to": match.get("on"),
                })
            continue
        changes.append({
            "kind": "object_removed",
            "category": obj.get("category"),
            "object_id": obj.get("id"),
            "size_m": obj.get("size_m"),
            "material": obj.get("material"),
        })

    for obj in after_objs:
        if id(obj) not in matched_after:
            changes.append({
                "kind": "object_added",
                "category": obj.get("category"),
                "object_id": obj.get("id"),
                "size_m": obj.get("size_m"),
                "material": obj.get("material"),
                "wet": bool(obj.get("wet")),
            })

    pairs, removed_regions, added_regions = _match_regions(
        before.get("regions", []), after.get("regions", [])
    )
    for region in removed_regions:
        changes.append({
            "kind": "region_removed",
            "region_kind": region.get("kind"),
            "region_id": region.get("id"),
        })
    for region in added_regions:
        changes.append({
            "kind": "region_added",
            "region_kind": region.get("kind"),
            "region_id": region.get("id"),
            "wet": bool(region.get("wet")),
        })

    before_surfaces = {s.get("name"): s for s in before.get("surfaces", [])}
    after_surfaces = {s.get("name"): s for s in after.get("surfaces", [])}
    for name, surface in after_surfaces.items():
        old = before_surfaces.get(name)
        if not old:
            continue
        for field in ("dust_state", "wet", "dust_present"):
            if field in surface and old.get(field) != surface.get(field):
                changes.append({
                    "kind": "surface_changed",
                    "surface": name,
                    "field": field,
                    "from": old.get(field),
                    "to": surface.get(field),
                })

    before_obs = {(o.get("about"), o.get("feature")): o for o in before.get("observations", [])}
    for obs in after.get("observations", []):
        key = (obs.get("about"), obs.get("feature"))
        old = before_obs.get(key)
        if old is not None and old.get("value") != obs.get("value"):
            changes.append({
                "kind": "observation_changed",
                "about": obs.get("about"),
                "feature": obs.get("feature"),
                "from": old.get("value"),
                "to": obs.get("value"),
            })

    for index, change in enumerate(changes, start=1):
        change["id"] = f"ch{index}"

    changes = _link_removals_to_outlines(changes, after)
    return changes


def _link_removals_to_outlines(changes, after):
    """A removed object whose footprint matches a dust outline is a removal
    that happened recently. The link is explicit, not inferred by a model."""
    outlines = [r for r in after.get("regions", []) if r.get("kind") in ("dust_outline", "unfaded_patch")]
    for change in changes:
        if change["kind"] != "object_removed":
            continue
        size = change.get("size_m")
        if size is None:
            continue
        best, best_delta = None, None
        for outline in outlines:
            area = outline.get("area_m2")
            if area is None:
                continue
            delta = abs(area - size * size) / max(size * size, 1e-6)
            if delta <= 0.6 and (best_delta is None or delta < best_delta):
                best, best_delta = outline, delta
        if best is not None:
            change["matched_region"] = best.get("id")
            change["match_quality"] = round(1.0 - best_delta, 3)
    return changes


def attach_changes(scene, changes):
    scene = dict(scene)
    scene["changes"] = list(changes)
    return scene


def changed_categories(changes):
    return {c.get("category") for c in changes if c.get("category")}
