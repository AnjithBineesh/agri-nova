"""Builds app/agriculture/data/crops.json.

Climatic, pH, soil-texture and drainage requirements are taken verbatim from the FAO ECOCROP
database as distributed in the Recocrop R package (Hijmans, CRAN; file inst/parameters/ecocrop.rds).
Crop coefficients and rooting depths come from FAO Irrigation & Drainage Paper 56 (Allen et al. 1998,
Tables 12 and 22) and seasonal water needs from FAO Irrigation Water Management Training Manual 3
(Brouwer & Heibloem 1986). Nutrient removal, residue ratios, %N from fixation and residual-N credits
are INDICATIVE coefficients for the simulation model; they are labelled as such in the output and
should be calibrated locally.

Usage:  python scripts/build_crop_database.py /path/to/ecocrop.rds
"""
import json
import sys
from pathlib import Path

import rdata

OUT = Path(__file__).resolve().parent.parent / "app" / "agriculture" / "data" / "crops.json"

# slug -> (ECOCROP row label NAME, curated record)
# Curated keys: name, family, category, typical_days, kc (ini, mid, end), root_m (min, max),
# fao_water_mm (min, max) or None, removal (N, P2O5, K2O kg per t product), ref_yield_t_ha,
# residue_ratio (t residue per t product), ndfa (fraction of N from fixation, legumes only),
# n_credit (residue removed, residue retained) kg N/ha central values, diseases, notes, standing_water
CURATED = {
    "rice": ("Rice paddy (Japonica)", dict(name="Rice (paddy)", family="Poaceae", category="cereal", typical_days=120,
             kc=(1.05, 1.20, 0.90), root_m=(0.5, 1.0), fao_water_mm=(450, 700), removal=(11, 5, 3), ref_yield=4.5,
             residue_ratio=1.5, standing_water=True,
             diseases=["Blast and sheath blight build-up under continuous rice", "Stem borers carry over in stubble"],
             benefits=["Tolerates flooded soils", "Large residue biomass when straw is retained"],
             season_note="Warm, wet season; requires assured water for puddled cultivation")),
    "maize": ("Maize", dict(name="Maize", family="Poaceae", category="cereal", typical_days=110, kc=(0.30, 1.20, 0.50),
              root_m=(1.0, 1.7), fao_water_mm=(500, 800), removal=(15, 6.5, 4.5), ref_yield=5.5, residue_ratio=1.5,
              diseases=["Continuous maize favours leaf blights, stalk rots and stem borers",
                        "Fall armyworm pressure in many tropical regions"],
              benefits=["High residue carbon input when stover is retained", "Deep fibrous root system"],
              season_note="Warm season; sensitive to drought at tasselling/silking")),
    "wheat": ("Wheat, common", dict(name="Wheat", family="Poaceae", category="cereal", typical_days=120,
              kc=(0.30, 1.15, 0.30), root_m=(1.0, 1.8), fao_water_mm=(450, 650), removal=(21, 8, 5), ref_yield=3.5,
              residue_ratio=1.5, diseases=["Take-all and leaf rusts increase with cereal-after-cereal"],
              benefits=["Cool-season cereal that breaks warm-season pest cycles"],
              season_note="Cool season; terminal heat above ~30 °C during grain fill reduces yield")),
    "sorghum": ("Sorghum (low altitude)", dict(name="Sorghum", family="Poaceae", category="cereal", typical_days=110,
                kc=(0.30, 1.05, 0.55), root_m=(1.0, 2.0), fao_water_mm=(450, 650), removal=(16, 7, 4.5),
                ref_yield=1.5, residue_ratio=2.0, diseases=["Shoot fly and grain mould in humid conditions"],
                benefits=["Drought tolerant", "Deep roots scavenge subsoil nutrients"],
                season_note="Warm season; tolerates intermittent drought")),
    "pearl_millet": ("Pearl millet", dict(name="Pearl millet", family="Poaceae", category="cereal", typical_days=85,
                     kc=(0.30, 1.00, 0.30), root_m=(1.0, 2.0), fao_water_mm=(450, 650), removal=(18, 7, 5),
                     ref_yield=1.2, residue_ratio=2.0, diseases=["Downy mildew where grown repeatedly"],
                     benefits=["Among the most drought- and heat-tolerant cereals", "Short duration"],
                     season_note="Warm, semi-arid season; suited to light soils")),
    "finger_millet": ("Finger millet", dict(name="Finger millet", family="Poaceae", category="cereal",
                      typical_days=110, kc=(0.30, 1.00, 0.30), root_m=(1.0, 2.0), fao_water_mm=(450, 650),
                      removal=(15, 6, 5), ref_yield=1.5, residue_ratio=1.8, diseases=["Blast in humid seasons"],
                      benefits=["Tolerates low-fertility soils"], season_note="Warm season, moderate rainfall")),
    "green_gram": ("Mung bean", dict(name="Green gram (mung bean)", family="Fabaceae", category="legume",
                   typical_days=70, kc=(0.40, 1.05, 0.60), root_m=(0.6, 1.0), fao_water_mm=(300, 500),
                   removal=(40, 9, 13), ref_yield=0.7, residue_ratio=1.1, ndfa=0.5, n_credit=(0, 15),
                   diseases=["Yellow mosaic virus (whitefly-vectored)", "Root rots with consecutive pulses"],
                   benefits=["Short duration fits between main crops", "Biological N fixation"],
                   season_note="Warm season or short pre-/post-monsoon window")),
    "black_gram": ("Urd bean", dict(name="Black gram (urd bean)", family="Fabaceae", category="legume",
                   typical_days=80, kc=(0.40, 1.05, 0.60), root_m=(0.6, 1.0), fao_water_mm=(300, 500),
                   removal=(40, 9, 13), ref_yield=0.7, residue_ratio=1.1, ndfa=0.5, n_credit=(0, 15),
                   diseases=["Yellow mosaic virus", "Powdery mildew"],
                   benefits=["Biological N fixation", "Tolerates heavier soils than mung bean"],
                   season_note="Warm season; also grown on residual moisture after rice")),
    "chickpea": ("Chick pea", dict(name="Chickpea", family="Fabaceae", category="legume", typical_days=110,
                 kc=(0.40, 1.00, 0.35), root_m=(0.6, 1.0), fao_water_mm=(350, 500), removal=(35, 8, 15),
                 ref_yield=1.2, residue_ratio=1.1, ndfa=0.5, n_credit=(0, 15),
                 diseases=["Fusarium wilt and Ascochyta blight build up with short rotations",
                           "Shares Sclerotinia with oilseed brassicas and sunflower"],
                 benefits=["Grown on stored soil moisture", "Biological N fixation"],
                 season_note="Cool, dry season on residual moisture")),
    "soybean": ("Soyabean", dict(name="Soybean", family="Fabaceae", category="legume", typical_days=105,
                kc=(0.40, 1.15, 0.50), root_m=(0.6, 1.3), fao_water_mm=(450, 700), removal=(60, 13, 20),
                ref_yield=2.5, residue_ratio=1.5, ndfa=0.6, n_credit=(-5, 10),
                diseases=["Sclerotinia stem rot shared with sunflower and brassicas", "Cyst nematode in short rotations"],
                benefits=["Biological N fixation (high grain N removal limits net soil gain)"],
                season_note="Warm season")),
    "cowpea": ("Cowpea", dict(name="Cowpea", family="Fabaceae", category="legume", typical_days=80,
               kc=(0.40, 1.05, 0.60), root_m=(0.6, 1.0), fao_water_mm=(300, 500), removal=(38, 10, 15),
               ref_yield=0.8, residue_ratio=1.2, ndfa=0.6, n_credit=(0, 20),
               diseases=["Root-knot nematodes", "Aphid-borne mosaic viruses"],
               benefits=["Drought tolerant legume", "Good ground cover reduces erosion"],
               season_note="Warm season; tolerates low rainfall")),
    "groundnut": ("Groundnut", dict(name="Groundnut", family="Fabaceae", category="legume", typical_days=115,
                  kc=(0.40, 1.15, 0.60), root_m=(0.5, 1.0), fao_water_mm=(500, 700), removal=(35, 7, 10),
                  ref_yield=1.8, residue_ratio=2.0, ndfa=0.6, n_credit=(0, 15), min_self_break=2,
                  diseases=["Leaf spots, stem rot and aflatoxin risk rise without a 2+ season break"],
                  benefits=["Biological N fixation", "Haulms are valuable fodder"],
                  season_note="Warm season; prefers light, well-drained soils")),
    "lentil": ("Lentil", dict(name="Lentil", family="Fabaceae", category="legume", typical_days=110,
               kc=(0.40, 1.10, 0.30), root_m=(0.6, 0.8), fao_water_mm=(350, 500), removal=(40, 10, 14),
               ref_yield=1.0, residue_ratio=1.2, ndfa=0.6, n_credit=(0, 15),
               diseases=["Fusarium wilt with short legume rotations"],
               benefits=["Cool-season legume with low water need"], season_note="Cool season")),
    "pigeonpea": ("Pigeon Pea", dict(name="Pigeon pea", family="Fabaceae", category="legume", typical_days=180,
                  kc=(0.40, 1.05, 0.50), kc_assumed=True, root_m=(0.9, 1.5), root_assumed=True, fao_water_mm=None,
                  removal=(35, 8, 14), ref_yield=0.9, residue_ratio=2.5, ndfa=0.6, n_credit=(5, 25),
                  diseases=["Fusarium wilt", "Pod borers"],
                  benefits=["Deep taproot", "Substantial leaf litter returns organic matter"],
                  season_note="Long-duration warm-season crop")),
    "sesame": ("Sesame seed", dict(name="Sesame", family="Pedaliaceae", category="oilseed", typical_days=90,
               kc=(0.35, 1.10, 0.25), root_m=(1.0, 1.5), fao_water_mm=None, removal=(35, 15, 10), ref_yield=0.5,
               residue_ratio=1.5, diseases=["Phyllody and Macrophomina root rot"],
               benefits=["Low water requirement", "Different family breaks cereal and legume pest cycles"],
               season_note="Warm season; sensitive to waterlogging")),
    "sunflower": ("Sunflower", dict(name="Sunflower", family="Asteraceae", category="oilseed", typical_days=100,
                  kc=(0.35, 1.05, 0.35), root_m=(0.8, 1.5), fao_water_mm=(600, 1000), removal=(25, 11, 7),
                  ref_yield=1.5, residue_ratio=2.0, diseases=["Sclerotinia shared with soybean, brassicas, chickpea"],
                  benefits=["Deep taproot extracts subsoil water"], season_note="Warm or mild season")),
    "mustard": ("Leaf mustard", dict(name="Mustard (Indian/brown)", family="Brassicaceae", category="oilseed",
                typical_days=110, kc=(0.35, 1.05, 0.35), root_m=(1.0, 1.5), fao_water_mm=None, removal=(32, 14, 9),
                ref_yield=1.2, residue_ratio=1.8, min_family_break=2,
                diseases=["Alternaria blight, white rust; clubroot persists for years in soil",
                          "Shares Sclerotinia with sunflower and soybean"],
                benefits=["Cool-season oilseed with modest water needs", "Taproot improves soil structure"],
                season_note="Cool season")),
    "cotton": ("Cotton, American upland", dict(name="Cotton", family="Malvaceae", category="fibre",
               typical_days=170, kc=(0.35, 1.18, 0.60), root_m=(1.0, 1.7), fao_water_mm=(700, 1300),
               removal=(25, 10, 13), ref_yield=1.8, residue_ratio=3.0,
               diseases=["Pink bollworm and whitefly; Verticillium/Fusarium wilt in continuous cotton"],
               benefits=["Deep taproot"], season_note="Long warm season")),
    "sugarcane": ("Sugarcane", dict(name="Sugarcane", family="Poaceae", category="cash", typical_days=365,
                  kc=(0.40, 1.25, 0.75), root_m=(1.2, 2.0), fao_water_mm=(1500, 2500), removal=(1.0, 0.5, 1.5),
                  ref_yield=70, residue_ratio=0.15, diseases=["Red rot and smut carry over in ratoons"],
                  benefits=["Long ground cover"], season_note="Occupies the field for a full year or more")),
    "tomato": ("Tomato", dict(name="Tomato", family="Solanaceae", category="vegetable", typical_days=120,
               kc=(0.60, 1.15, 0.80), root_m=(0.7, 1.5), fao_water_mm=(400, 800), removal=(1.6, 0.6, 3.0),
               ref_yield=30, residue_ratio=0.1, min_family_break=4,
               diseases=["Bacterial wilt, late blight and root-knot nematodes shared with potato"],
               benefits=["High value where markets exist"], season_note="Mild season")),
    "onion": ("Onion", dict(name="Onion", family="Amaryllidaceae", category="vegetable", typical_days=130,
              kc=(0.70, 1.05, 0.75), root_m=(0.3, 0.6), fao_water_mm=(350, 550), removal=(2.0, 0.8, 2.0),
              ref_yield=20, residue_ratio=0.05, min_family_break=4, diseases=["White rot and thrips"],
              benefits=["Different family from most field crops"], season_note="Cool, dry season")),
    "cabbage": ("Cabbage", dict(name="Cabbage", family="Brassicaceae", category="vegetable", typical_days=90,
                kc=(0.70, 1.05, 0.95), root_m=(0.5, 0.8), fao_water_mm=(350, 500), removal=(2.5, 0.8, 3.0),
                ref_yield=30, residue_ratio=0.2, min_family_break=4,
                diseases=["Clubroot and black rot shared with mustard"], benefits=["Short duration"],
                season_note="Cool season")),
    "potato": ("Potato", dict(name="Potato", family="Solanaceae", category="vegetable", typical_days=105,
               kc=(0.50, 1.15, 0.75), root_m=(0.4, 0.6), fao_water_mm=(500, 700), removal=(3.5, 1.4, 5.5),
               ref_yield=20, residue_ratio=0.2, min_family_break=4,
               diseases=["Late blight, bacterial wilt, cyst and root-knot nematodes shared with tomato"],
               benefits=["High value where markets exist"], season_note="Cool season")),
    "sunn_hemp": ("Sunn hemp", dict(name="Sunn hemp (green manure)", family="Fabaceae", category="cover_crop",
                  typical_days=60, kc=(0.40, 1.05, 0.50), kc_assumed=True, root_m=(1.0, 1.5), root_assumed=True,
                  fao_water_mm=None, removal=(0, 0, 0), ref_yield=4.0, residue_ratio=1.0, green_manure=True,
                  ndfa=0.7, n_credit=(40, 70), diseases=["Generally low; can host some root-knot nematode races"],
                  benefits=["Incorporated at flowering as green manure", "Rapid ground cover suppresses weeds"],
                  season_note="Short warm-season fallow window")),
    "dhaincha": ("Danicha *", dict(name="Dhaincha (Sesbania, green manure)", family="Fabaceae", category="cover_crop",
                 typical_days=50, kc=(0.40, 1.05, 0.50), kc_assumed=True, root_m=(0.8, 1.2), root_assumed=True,
                 fao_water_mm=None, removal=(0, 0, 0), ref_yield=4.0, residue_ratio=1.0, green_manure=True, ndfa=0.7,
                 n_credit=(40, 70), standing_water_tolerant=True, diseases=["Generally low"],
                 benefits=["Tolerates waterlogging and moderate salinity", "Green manure before rice"],
                 season_note="Short warm-season window, often before transplanted rice")),
}

TEXTURE_CODES = {"H": "heavy", "M": "medium", "L": "light", "O": "organic", "W": "wide"}
DRAINAGE_CODES = {"P": "poorly", "I": "imperfectly", "W": "well", "E": "excessively"}

SOURCES = {
    "ecocrop": "FAO ECOCROP database via Recocrop R package (Hijmans) – temperature, rainfall, pH, texture, drainage",
    "fao56": "Allen et al. (1998) FAO Irrigation & Drainage Paper 56, Tables 12 (Kc) and 22 (rooting depth)",
    "fao_iwm3": "Brouwer & Heibloem (1986) FAO Irrigation Water Management Training Manual 3 – seasonal crop water needs",
    "indicative": "Indicative model coefficients (nutrient removal: IPNI/IFA removal tables; residue ratios; %Ndfa: "
                  "Herridge et al. 2008; residual N credits: Peoples et al. 2009) – calibrate locally",
}


def codes(s: str, table: dict) -> list[str]:
    return [table[c] for c in str(s).split() if c in table]


def n_demand(c: dict, ndfa) -> str:
    if ndfa is not None:
        return "low"
    per_ha = c["removal"][0] * c["ref_yield"]
    return "low" if per_ha < 35 else ("medium" if per_ha <= 70 else "high")


def build(rds_path: str) -> list[dict]:
    df = rdata.read_rds(rds_path)
    crops = []
    for slug, (eco_name, c) in CURATED.items():
        row = df[df["NAME"] == eco_name].iloc[0]
        ndfa = c.get("ndfa")
        credit = c.get("n_credit")
        record = {
            "slug": slug,
            "crop_name": c["name"],
            "scientific_name": str(row["SCIENTNAME"]),
            "crop_family": c["family"],
            "category": c["category"],
            "duration": {"typical_days": c["typical_days"], "ecocrop_min_days": int(row["GMIN"]),
                         "ecocrop_max_days": int(row["GMAX"])},
            "planting_season": c["season_note"],
            "harvest_period": f"About {c['typical_days']} days after sowing (variety dependent)",
            "climate_requirements": {
                "temperature_c": {"absolute_min": float(row["TMIN"]), "optimal_min": float(row["TOPMN"]),
                                  "optimal_max": float(row["TOPMX"]), "absolute_max": float(row["TMAX"])},
                "killing_temperature_c": float(row["KTMP"]),
                "annual_rainfall_mm": {"absolute_min": float(row["RMIN"]), "optimal_min": float(row["ROPMN"]),
                                       "optimal_max": float(row["ROPMX"]), "absolute_max": float(row["RMAX"])},
            },
            "water_requirement": {
                "fao_seasonal_mm": ({"min": c["fao_water_mm"][0], "max": c["fao_water_mm"][1]}
                                    if c.get("fao_water_mm") else None),
                "kc": {"ini": c["kc"][0], "mid": c["kc"][1], "end": c["kc"][2]},
                "kc_source": "assumed (generic legume values)" if c.get("kc_assumed") else "FAO-56 Table 12",
                "requires_standing_water": bool(c.get("standing_water")),
            },
            "soil_preferences": {
                "ph": {"absolute_min": float(row["PHMIN"]), "optimal_min": float(row["PHOPMN"]),
                       "optimal_max": float(row["PHOPMX"]), "absolute_max": float(row["PHMAX"])},
                "texture_optimal": codes(row["TEXT"], TEXTURE_CODES),
                "texture_range": codes(row["TEXTR"], TEXTURE_CODES),
                "drainage_optimal": codes(row["DRA"], DRAINAGE_CODES),
                "drainage_range": codes(row["DRAR"], DRAINAGE_CODES),
                "fertility_requirement": {"H": "high", "M": "moderate", "L": "low"}.get(str(row["FER"]).strip(),
                                                                                        "unknown"),
                "salinity_tolerance": {"H": "high", "M": "moderate", "L": "low"}.get(str(row["SALR"]).split()[-1].upper(),
                                                                                     "unknown"),
            },
            "nutrient_requirements": {
                "removal_kg_per_t": {"N": c["removal"][0], "P2O5": c["removal"][1], "K2O": c["removal"][2]},
                "nitrogen_demand": n_demand(c, ndfa),
                "nitrogen_demand_basis": "Legumes: low (largely self-supplied by fixation). Others: N removed in "
                                         "harvested product at the reference yield (<35 low, 35–70 medium, "
                                         ">70 kg N/ha high)",
                "reference_yield_t_ha": c["ref_yield"],
                "coefficients_status": "indicative",
            },
            "nitrogen_fixation": ndfa is not None,
            "fixation": ({"ndfa_fraction": ndfa,
                          "residual_n_credit_kg_ha": {"residue_removed": credit[0], "residue_retained": credit[1]}}
                         if ndfa is not None else None),
            "root_characteristics": {
                "max_depth_m": {"min": c["root_m"][0], "max": c["root_m"][1]},
                "depth_class": "deep" if c["root_m"][1] >= 1.5 else ("medium" if c["root_m"][1] >= 0.9 else "shallow"),
                "type": "fibrous" if c["family"] == "Poaceae" else ("bulb/shallow fibrous"
                                                                    if c["family"] == "Amaryllidaceae" else "taproot"),
                "source": "assumed" if c.get("root_assumed") else "FAO-56 Table 22",
            },
            "residue": {"residue_to_product_ratio": c["residue_ratio"], "green_manure": bool(c.get("green_manure")),
                        "carbon_fraction": 0.45},
            "rotation": {
                "potential_benefits": c["benefits"],
                "min_break_seasons_same_crop": c.get("min_self_break", 1 if c["category"] != "cereal" else 0),
                "min_break_seasons_same_family": c.get("min_family_break", 1 if c["family"] == "Fabaceae" else 0),
            },
            "pest_disease_considerations": c["diseases"],
            "geographic_suitability": "Global ECOCROP ranges; actual suitability is assessed per farm from local "
                                      "climate, soil and water conditions.",
            "sources": [SOURCES["ecocrop"], SOURCES["fao56"]]
                       + ([SOURCES["fao_iwm3"]] if c.get("fao_water_mm") else []) + [SOURCES["indicative"]],
            "ecocrop_entry": eco_name,
        }
        crops.append(record)
    return crops


if __name__ == "__main__":
    data = build(sys.argv[1])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"version": "1.0", "sources": SOURCES, "crops": data}, indent=2, ensure_ascii=False))
    print(f"Wrote {len(data)} crops to {OUT}")
