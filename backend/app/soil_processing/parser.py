"""Identify soil parameters, values and units in extracted soil-report text.

Extraction is heuristic. Results are *candidates* shown to the user for confirmation; they are
never stored as measurements until the user confirms them.
"""
import re
from datetime import date

NUM = r"(-?\d+(?:[.,]\d+)?)"
UNIT = r"(%|kg\s*/\s*ha|kg\s*ha-1|mg\s*/\s*kg|ppm|ds\s*/\s*m|ms\s*/\s*cm|meq\s*/\s*100\s*g|cmol\(?\+?\)?\s*/\s*kg)?"

I = re.IGNORECASE
# (pattern, flags) – single-letter symbols (N, P, K) are matched case-sensitively.
PATTERNS: dict[str, list[tuple[str, int]]] = {
    "ph": [(r"\bp\s*h\b(?:\s*\(?\s*1\s*:\s*2(?:\.5)?\s*\)?)?(?:\s*value)?\s*[:=\-]?\s*" + NUM, I)],
    "electrical_conductivity": [(r"\b(?:e\.?\s*c\.?|electrical\s+conductivity)(?![a-z])[^0-9\n]{0,25}" + NUM + r"\s*" + UNIT, I)],
    "organic_carbon": [(r"\b(?:organic\s+carbon|o\.\s*c\.?|OC)(?![a-z])[^0-9\n]{0,25}" + NUM + r"\s*" + UNIT, I)],
    "organic_matter": [(r"\b(?:organic\s+matter|o\.\s*m\.?|OM)(?![a-z])[^0-9\n]{0,25}" + NUM + r"\s*" + UNIT, I)],
    "nitrogen": [(r"\bnitrogen\b[^0-9\n]{0,25}" + NUM + r"\s*" + UNIT, I),
                 (r"(?<![A-Za-z])N(?![A-Za-z0-9])[^0-9\n]{0,15}" + NUM + r"\s*" + UNIT, 0)],
    "phosphorus": [(r"\b(?:phosphorus|phosphorous|p2o5)\b[^0-9\n]{0,25}" + NUM + r"\s*" + UNIT, I),
                   (r"(?<![A-Za-z])P(?![A-Za-z0-9])[^0-9\n]{0,15}" + NUM + r"\s*" + UNIT, 0)],
    "potassium": [(r"\b(?:potassium|k2o)\b[^0-9\n]{0,25}" + NUM + r"\s*" + UNIT, I),
                  (r"(?<![A-Za-z])K(?![A-Za-z0-9])[^0-9\n]{0,15}" + NUM + r"\s*" + UNIT, 0)],
}
TEXTURES = ["silty clay loam", "sandy clay loam", "silty clay", "sandy clay", "clay loam", "silt loam", "sandy loam",
            "loamy sand", "loam", "clay", "sand", "silt"]
PLAUSIBLE = {"ph": (2.5, 11.5), "electrical_conductivity": (0, 60), "organic_carbon": (0, 60), "organic_matter": (0, 100),
             "nitrogen": (0, 5000), "phosphorus": (0, 2000), "potassium": (0, 10000)}
DATE_PATTERNS = [
    (r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", "dmy"),
    (r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", "ymd"),
]


def _norm_unit(u: str | None) -> str | None:
    if not u:
        return None
    u = re.sub(r"\s+", "", u.lower())
    return {"kgha-1": "kg/ha", "kg/ha": "kg/ha", "mg/kg": "mg/kg", "ppm": "ppm", "%": "%", "ds/m": "dS/m",
            "ms/cm": "dS/m"}.get(u, u)


def _find_date(text: str, keywords: tuple[str, ...]) -> date | None:
    for line in text.splitlines():
        if any(k in line.lower() for k in keywords):
            for pat, order in DATE_PATTERNS:
                m = re.search(pat, line)
                if m:
                    a, b, c = (int(x) for x in m.groups())
                    try:
                        return date(c, b, a) if order == "dmy" else date(a, b, c)
                    except ValueError:
                        continue
    return None


def parse_report(text: str) -> dict:
    found: dict[str, dict] = {}
    lowered = text.lower()
    for key, pats in PATTERNS.items():
        for pat, flags in pats:
            for m in re.finditer(pat, text, flags | re.MULTILINE):
                try:
                    value = float(m.group(1).replace(",", "."))
                except (ValueError, IndexError):
                    continue
                lo, hi = PLAUSIBLE[key]
                if not lo <= value <= hi:
                    continue
                unit = "pH" if key == "ph" else (_norm_unit(m.group(2)) if m.lastindex and m.lastindex >= 2 else None)
                context = text[max(0, m.start() - 10):m.end() + 10].replace("\n", " ").strip()
                found[key] = {"value": value, "unit": unit, "context": context,
                              "confidence": "medium" if (unit or key == "ph") and flags else "low"}
                break
            if key in found:
                break
    for tex in TEXTURES:
        if re.search(r"\b" + tex + r"\b", lowered):
            found["soil_texture"] = {"value": tex, "unit": None, "context": tex, "confidence": "medium"}
            break
    if "phosphorus" in found:
        method = "olsen" if "olsen" in lowered else ("bray1" if "bray" in lowered else
                                                     ("mehlich3" if "mehlich" in lowered else "unknown"))
        found["phosphorus"]["method"] = method
    lab = None
    for line in text.splitlines()[:15]:
        if re.search(r"laborator|soil\s+testing|analytical", line, re.IGNORECASE):
            lab = line.strip()[:200]
            break
    report_date = _find_date(text, ("date", "tested", "report", "analysed", "analyzed"))
    return {"parameters": found, "laboratory": lab, "report_date": report_date.isoformat() if report_date else None,
            "parameter_count": len(found)}
