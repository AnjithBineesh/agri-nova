"""Soil profile interpretation with explicit, referenced rating systems.

* pH classes: USDA-NRCS Soil Survey Manual (Soil Science Division Staff, 2017), reaction classes.
* Organic carbon (Walkley–Black, %), available N (alkaline KMnO4, kg/ha), Olsen P (kg P/ha) and
  NH4OAc-exchangeable K (kg K/ha): soil-test ratings used by India's Soil Health Card scheme
  (after Muhr et al., 1965; Subbiah & Asija, 1956). These are method- and region-specific; other
  laboratories and countries use different calibrations. Agri Nova reports which system it applied.
* Available water capacity by texture when not measured: FAO-56 Table 19 (midpoint of θFC − θWP).
"""

PH_CLASSES = [
    (4.5, "extremely acid"), (5.0, "very strongly acid"), (5.5, "strongly acid"), (6.0, "moderately acid"),
    (6.5, "slightly acid"), (7.3, "neutral"), (7.8, "slightly alkaline"), (8.4, "moderately alkaline"),
    (9.0, "strongly alkaline"), (99, "very strongly alkaline"),
]

TEXTURE_GROUP = {
    "sand": "light", "loamy sand": "light", "sandy loam": "light",
    "loam": "medium", "silt loam": "medium", "silt": "medium", "sandy clay loam": "medium",
    "clay loam": "heavy", "silty clay loam": "heavy", "sandy clay": "heavy", "silty clay": "heavy", "clay": "heavy",
    "peat": "organic", "muck": "organic",
}
TEXTURES = list(TEXTURE_GROUP)

# FAO-56 Table 19, (θFC − θWP) range in m3/m3 -> midpoint in mm water per m soil
AWC_MM_PER_M = {
    "sand": 80, "loamy sand": 90, "sandy loam": 130, "loam": 155, "silt loam": 160, "silt": 180,
    "sandy clay loam": 145, "silty clay loam": 155, "clay loam": 150, "silty clay": 160, "sandy clay": 145,
    "clay": 160,
}

MG_KG_TO_KG_HA = 2.24  # 0–15 cm plough layer, bulk density ≈1.5 g/cm3 (standard soil-testing convention)

RATINGS = {
    "organic_carbon": {"unit": "%", "low": 0.5, "high": 0.75, "method": "Walkley–Black"},
    "nitrogen": {"unit": "kg/ha", "low": 280, "high": 560, "method": "Alkaline KMnO4 (Subbiah & Asija)"},
    "phosphorus": {"unit": "kg/ha", "low": 10, "high": 25, "method": "Olsen (0.5 M NaHCO3), as P"},
    "potassium": {"unit": "kg/ha", "low": 108, "high": 280, "method": "1 N NH4OAc exchangeable K"},
}
RATING_SYSTEM = "India Soil Health Card soil-test ratings (method-specific)"


def ph_class(ph: float) -> str:
    for upper, name in PH_CLASSES:
        if ph <= upper:
            return name
    return "very strongly alkaline"


def to_kg_ha(value: float | None, unit: str | None) -> float | None:
    if value is None:
        return None
    u = (unit or "kg/ha").lower().replace(" ", "")
    if u in ("kg/ha", "kgha-1", "kg/hectare"):
        return value
    if u in ("mg/kg", "ppm", "mgkg-1"):
        return value * MG_KG_TO_KG_HA
    if u in ("lb/acre", "lbs/acre"):
        return value * 1.12085
    return None


def _rate(value: float, key: str) -> str:
    r = RATINGS[key]
    return "low" if value < r["low"] else ("medium" if value <= r["high"] else "high")


def estimated_awc(texture: str | None) -> float | None:
    return AWC_MM_PER_M.get((texture or "").lower())


def assess(soil: dict | None) -> dict:
    """Return an itemised, explained assessment. No composite 'soil health score' is produced."""
    if not soil:
        return {"available": False, "items": [], "limitations": [],
                "message": "No soil information yet. Enter values manually or upload a soil test report.",
                "rating_system": RATING_SYSTEM}
    items, limitations, notes = [], [], []

    ph = soil.get("ph")
    if ph is not None:
        cls = ph_class(ph)
        status = "good" if 6.0 <= ph <= 7.5 else ("caution" if 5.5 <= ph <= 8.0 else "constraint")
        expl = f"pH {ph:.1f} is {cls}."
        if ph < 5.5:
            expl += " Strongly acid soils can limit P availability and cause Al/Mn toxicity for sensitive crops."
            limitations.append("Soil acidity")
        elif ph > 8.0:
            expl += " Alkaline soils can reduce availability of P, Fe and Zn; check sodicity (ESP) if pH > 8.5."
            limitations.append("Soil alkalinity")
        items.append({"key": "ph", "parameter": "Soil reaction (pH)", "value": ph, "unit": "pH", "class": cls, "status": status,
                      "explanation": expl, "reference": "USDA-NRCS Soil Survey Manual reaction classes"})

    oc = soil.get("organic_carbon")
    om = soil.get("organic_matter")
    if oc is None and om is not None:
        oc = om / 1.724
        notes.append("Organic carbon estimated from organic matter using the van Bemmelen factor (OC = OM / 1.724).")
    if oc is not None:
        rating = _rate(oc, "organic_carbon")
        items.append({"key": "organic_carbon", "parameter": "Organic carbon", "value": round(oc, 2), "unit": "%", "class": rating,
                      "status": {"low": "constraint", "medium": "caution", "high": "good"}[rating],
                      "explanation": f"Organic carbon is rated {rating} (<0.5 low, 0.5–0.75 medium, >0.75 high). "
                                     "Higher organic carbon generally improves aggregation, water retention and "
                                     "nutrient supply.",
                      "reference": f"{RATING_SYSTEM}; {RATINGS['organic_carbon']['method']}"})
        if rating == "low":
            limitations.append("Low organic carbon")

    for key, label, unit_key in (("nitrogen", "Available nitrogen", "nitrogen_unit"),
                                 ("phosphorus", "Available phosphorus", "phosphorus_unit"),
                                 ("potassium", "Available potassium", "potassium_unit")):
        raw = soil.get(key)
        if raw is None:
            continue
        val = to_kg_ha(raw, soil.get(unit_key))
        if val is None:
            items.append({"key": key, "parameter": label, "value": raw, "unit": soil.get(unit_key), "class": "not rated",
                          "status": "unknown", "explanation": "Unit not recognised for rating; value stored as entered.",
                          "reference": RATING_SYSTEM})
            continue
        rating = _rate(val, key)
        r = RATINGS[key]
        expl = f"{label} ≈ {val:.0f} kg/ha is rated {rating} ({r['method']}: <{r['low']} low, " \
               f"{r['low']}–{r['high']} medium, >{r['high']} high)."
        if key == "phosphorus" and (soil.get("phosphorus_method") or "unknown") not in ("olsen", "unknown"):
            expl += " Ratings are calibrated for Olsen P; this report used a different extractant, so the class " \
                    "is indicative only."
        if soil.get(unit_key, "kg/ha") in ("mg/kg", "ppm"):
            expl += f" Converted from mg/kg using ×{MG_KG_TO_KG_HA} (0–15 cm layer)."
        items.append({"key": key, "parameter": label, "value": round(val, 1), "unit": "kg/ha", "class": rating,
                      "status": {"low": "constraint", "medium": "caution", "high": "good"}[rating],
                      "explanation": expl, "reference": RATING_SYSTEM})
        if rating == "low":
            limitations.append(f"Low {label.lower().replace('available ', '')}")

    tex = (soil.get("soil_texture") or "").lower() or None
    if tex:
        group = TEXTURE_GROUP.get(tex, "unknown")
        expl = {"light": "Light (coarse) soils drain quickly and hold less water and nutrients.",
                "medium": "Medium-textured soils usually balance drainage and water retention.",
                "heavy": "Heavy (fine) soils hold more water but may drain slowly and be hard to work when wet.",
                "organic": "Organic soils have very high water retention; drainage management is important."}.get(
            group, "Texture group not recognised.")
        items.append({"key": "soil_texture", "parameter": "Soil texture", "value": tex, "unit": None, "class": group, "status": "info",
                      "explanation": expl, "reference": "USDA texture classes grouped to ECOCROP light/medium/heavy"})

    whc = soil.get("water_holding_capacity")
    whc_source = "measured/entered"
    if whc is None and tex:
        whc = estimated_awc(tex)
        whc_source = "estimated from texture (FAO-56 Table 19)"
    if whc is not None:
        status = "constraint" if whc < 100 else ("caution" if whc < 140 else "good")
        items.append({"key": "water_holding_capacity", "parameter": "Available water capacity", "value": whc, "unit": "mm per m soil",
                      "class": whc_source, "status": status,
                      "explanation": f"About {whc:.0f} mm of plant-available water per metre of soil "
                                     f"({whc_source}).", "reference": "FAO-56 Table 19"})
        if whc < 100:
            limitations.append("Low water retention")

    depth = soil.get("soil_depth_cm")
    if depth is not None and depth < 50:
        limitations.append("Shallow soil")
        items.append({"key": "soil_depth_cm", "parameter": "Soil depth", "value": depth, "unit": "cm", "class": "shallow",
                      "status": "constraint", "explanation": "Shallow soils restrict rooting depth and stored water.",
                      "reference": "Agronomic convention"})
    ec = soil.get("electrical_conductivity")
    if ec is not None:
        cls = "non-saline" if ec < 2 else ("slightly saline" if ec < 4 else "saline")
        items.append({"key": "electrical_conductivity", "parameter": "Electrical conductivity", "value": ec, "unit": "dS/m", "class": cls,
                      "status": "good" if ec < 2 else ("caution" if ec < 4 else "constraint"),
                      "explanation": "Salinity reduces water uptake; sensitive crops are affected above ~2 dS/m "
                                     "(saturation-extract basis; 1:2 extracts read lower).",
                      "reference": "USDA Salinity Laboratory classes (ECe)"})
        if ec >= 4:
            limitations.append("Salinity")

    measured = sum(1 for k in ("ph", "organic_carbon", "nitrogen", "phosphorus", "potassium", "soil_texture")
                   if soil.get(k) is not None)
    return {"available": True, "items": items, "limitations": sorted(set(limitations)), "notes": notes,
            "completeness": round(measured / 6, 2), "rating_system": RATING_SYSTEM,
            "methodology": "Each parameter is rated individually against the cited reference. Agri Nova does not "
                           "combine them into a single universal soil health score because soil functions depend "
                           "on context, crop and laboratory method.",
            "value_status": soil.get("value_status", {})}
