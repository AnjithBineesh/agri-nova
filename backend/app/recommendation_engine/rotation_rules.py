"""Agronomic rotation rules applied to a crop sequence.

Rules are qualitative principles widely used in rotation design (e.g. FAO Conservation
Agriculture guidance; Bullock 1992, Crit. Rev. Plant Sci. 11:309–326; Peoples et al. 2009):
break pest/disease cycles by avoiding the same crop or family in succession, include legumes,
alternate cereals and legumes, diversify rooting depth, and avoid sequencing hosts of shared
soil-borne pathogens. Penalties and bonuses are transparent heuristics, not calibrated models.
"""

# Crops sharing important soil-borne pathogens/pests (beyond botanical family).
SHARED_HOST_GROUPS = {
    "Sclerotinia (white mould)": {"sunflower", "soybean", "mustard", "cabbage", "chickpea", "lentil", "groundnut",
                                  "tomato", "potato"},
    "Root-knot nematodes": {"tomato", "potato", "cowpea", "soybean", "cotton", "sunn_hemp", "green_gram",
                            "black_gram", "cabbage"},
    "Bacterial wilt (Ralstonia)": {"tomato", "potato", "groundnut"},
}
FALLOW = "fallow"


def evaluate(sequence: list[str], crops: dict[str, dict], history: list[str] | None = None) -> dict:
    """Evaluate a sequence (crop slugs or 'fallow') and return findings plus a 0–1 rotation health index."""
    history = history or []
    full = history[-2:] + sequence
    offset = len(full) - len(sequence)
    findings: list[dict] = []
    penalty = 0.0
    bonus = 0.0
    planted = [s for s in sequence if s != FALLOW]

    for i in range(offset, len(full)):
        cur = full[i]
        if cur == FALLOW:
            continue
        c = crops[cur]
        for back in range(1, 3):
            j = i - back
            if j < 0:
                break
            prev = full[j]
            if prev == FALLOW:
                continue
            p = crops[prev]
            pos = f"season {i - offset + 1}"
            if prev == cur and back <= max(1, c["rotation"]["min_break_seasons_same_crop"]):
                if back == 1:
                    sev = "warning" if c["category"] in ("cereal",) else "critical"
                    findings.append({"rule": "repeated_crop", "severity": sev, "position": pos,
                                     "message": f"{c['crop_name']} follows {p['crop_name']} directly: pests and "
                                                f"diseases specific to this crop can build up."})
                    penalty += 0.12 if sev == "warning" else 0.25
                elif c["rotation"]["min_break_seasons_same_crop"] >= 2:
                    findings.append({"rule": "short_break", "severity": "warning", "position": pos,
                                     "message": f"{c['crop_name']} returns after one season; a break of "
                                                f"{c['rotation']['min_break_seasons_same_crop']} seasons is advised."})
                    penalty += 0.1
            elif p["crop_family"] == c["crop_family"]:
                need = c["rotation"]["min_break_seasons_same_family"]
                if back == 1 and (need >= 1 or c["crop_family"] == "Poaceae"):
                    sev = "info" if c["crop_family"] == "Poaceae" else "warning"
                    findings.append({"rule": "same_family", "severity": sev, "position": pos,
                                     "message": f"{c['crop_name']} follows {p['crop_name']} (both {c['crop_family']}); "
                                                "related crops share pests and diseases."})
                    penalty += 0.04 if sev == "info" else 0.12
                elif back == 2 and need >= 3:
                    findings.append({"rule": "family_break", "severity": "warning", "position": pos,
                                     "message": f"{c['crop_family']} crops need a longer break ({need} seasons)."})
                    penalty += 0.08
            if back == 1:
                for group, members in SHARED_HOST_GROUPS.items():
                    if cur in members and prev in members and prev != cur and p["crop_family"] != c["crop_family"]:
                        findings.append({"rule": "shared_host", "severity": "warning", "position": pos,
                                         "message": f"{p['crop_name']} and {c['crop_name']} are both hosts of {group}."})
                        penalty += 0.06

    legumes = [s for s in planted if crops[s]["nitrogen_fixation"]]
    if legumes:
        bonus += 0.1
        findings.append({"rule": "legume_inclusion", "severity": "positive",
                         "message": f"Includes legume(s): {', '.join(sorted({crops[s]['crop_name'] for s in legumes}))}. "
                                    "Biological N fixation can reduce N fertiliser needs, but net soil N gain depends "
                                    "on residue management and grain removal."})
    else:
        findings.append({"rule": "no_legume", "severity": "info",
                         "message": "No legume in the sequence: all N must come from soil reserves, fertiliser or manure."})
    alternations = sum(1 for a, b in zip(planted, planted[1:])
                       if {crops[a]["category"], crops[b]["category"]} >= {"cereal"} and
                       (crops[a]["nitrogen_fixation"] != crops[b]["nitrogen_fixation"]))
    if alternations:
        bonus += min(0.1, 0.04 * alternations)
        findings.append({"rule": "cereal_legume", "severity": "positive",
                         "message": f"{alternations} cereal–legume transition(s), a well-documented rotation benefit."})
    depth_classes = {crops[s]["root_characteristics"]["depth_class"] for s in planted}
    if len(depth_classes) >= 2:
        bonus += 0.05
        findings.append({"rule": "root_diversity", "severity": "positive",
                         "message": f"Rooting depth diversity ({', '.join(sorted(depth_classes))}) uses water and "
                                    "nutrients from different soil layers."})
    families = {crops[s]["crop_family"] for s in planted}
    fallows = sequence.count(FALLOW)
    if fallows:
        findings.append({"rule": "fallow", "severity": "info",
                         "message": f"{fallows} fallow season(s): saves water but leaves soil exposed unless "
                                    "residues or a cover are maintained."})
    health = max(0.0, min(1.0, 0.75 - penalty + bonus))
    return {"findings": findings, "rotation_health_index": round(health, 3), "families": sorted(families),
            "family_count": len(families), "legume_count": len(legumes)}
