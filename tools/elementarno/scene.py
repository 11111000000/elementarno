"""Structural validation of scene graphs.

The scene graph is the only thing a claim may stand on, so it is checked
before anything else: dangling references, duplicate ids, unsupported enum
values. Cheap checks that catch the errors that would otherwise become
confident nonsense.
"""

VALID_REGIONS = {
    "dust_outline", "empty_hook", "unfaded_patch", "stain", "scratch", "crack",
    "dent", "burn", "water_line", "mold_patch", "footprint", "tyre_mark",
    "tool_mark", "puddle", "condensation", "disturbed_dust", "mud_footprint", "wet_trace",
    "fingerprint", "paint_splash", "paint_trace", "sawdust", "flour_dust",
    "oil_trace", "weld_spatter", "plaster_dust", "ink_trace", "cup_ring",
    "metal_swarf", "other",
}

VALID_OBJECT_STATES = {"new", "clean", "worn", "damaged", "fresh", "stale", "unknown"}
VALID_DUST_STATES = {"none", "even", "uneven", "patchy"}
VALID_FRESHNESS = {"sharp", "soft", "erased", "unknown"}
VALID_EDGES = {"concave", "convex", "flat", "ragged", "unknown"}


def validate_scene(scene):
    problems = []
    if not isinstance(scene, dict):
        return [{"code": "not_an_object", "detail": "scene must be a JSON object"}]

    for collection in ("surfaces", "objects", "regions"):
        if collection not in scene:
            problems.append({"code": "missing_collection", "detail": collection})
        elif not isinstance(scene[collection], list):
            problems.append({"code": "collection_not_a_list", "detail": collection})

    ids = {}
    for collection in ("surfaces", "objects", "regions"):
        for item in scene.get(collection, []) or []:
            item_id = item.get("id")
            if not item_id:
                problems.append({"code": "missing_id", "detail": f"{collection}: {item}"})
                continue
            if item_id in ids:
                problems.append({
                    "code": "duplicate_id",
                    "detail": f"{item_id} used in {ids[item_id]} and {collection}",
                })
            ids[item_id] = collection

    surface_ids = {s.get("id") for s in scene.get("surfaces", []) or []}
    region_ids = {r.get("id") for r in scene.get("regions", []) or []}

    for obj in scene.get("objects", []) or []:
        on = obj.get("on")
        if on and on not in surface_ids:
            problems.append({
                "code": "dangling_surface",
                "detail": f"object {obj.get('id')} rests on unknown surface {on}",
            })
        region = obj.get("region")
        if region and region not in region_ids:
            problems.append({
                "code": "dangling_region",
                "detail": f"object {obj.get('id')} points at unknown region {region}",
            })
        state = obj.get("state")
        if state and state not in VALID_OBJECT_STATES:
            problems.append({
                "code": "bad_enum",
                "detail": f"object {obj.get('id')}: unknown state {state}",
            })

    for region in scene.get("regions", []) or []:
        kind = region.get("kind")
        if kind and kind not in VALID_REGIONS:
            problems.append({
                "code": "bad_enum",
                "detail": f"region {region.get('id')}: unknown kind {kind}",
            })
        for field, allowed in (("freshness", VALID_FRESHNESS), ("edges", VALID_EDGES)):
            value = region.get(field)
            if value and value not in allowed:
                problems.append({
                    "code": "bad_enum",
                    "detail": f"region {region.get('id')}: unknown {field} {value}",
                })
        bbox = region.get("bbox")
        if bbox is not None and (not isinstance(bbox, list) or len(bbox) != 4):
            problems.append({
                "code": "bad_bbox",
                "detail": f"region {region.get('id')}: bbox must have 4 numbers",
            })

    known_vertices = region_ids | surface_ids | {o.get("id") for o in scene.get("objects", []) or []}
    for obs in scene.get("observations", []) or []:
        about = obs.get("about")
        if about and about not in known_vertices:
            problems.append({
                "code": "dangling_observation",
                "detail": f"observation {obs.get('id')} about unknown element {about}",
            })

    for surface in scene.get("surfaces", []) or []:
        dust_state = surface.get("dust_state")
        if dust_state and dust_state not in VALID_DUST_STATES:
            problems.append({
                "code": "bad_enum",
                "detail": f"surface {surface.get('id')}: unknown dust_state {dust_state}",
            })

    return problems
