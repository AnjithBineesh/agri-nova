"""Loads the trained models and turns inputs into explained crop predictions."""
import json
import logging
import threading
import warnings

import joblib
import numpy as np
import pandas as pd
import sklearn

from .features import ARTIFACT_DIR, CROP_DB_SLUG, DISPLAY_NAMES

log = logging.getLogger("agrinova.ml")
_lock = threading.Lock()
_state: dict = {}


class ModelUnavailable(RuntimeError):
    pass


def _load() -> dict:
    with _lock:
        if _state:
            return _state
        card_path = ARTIFACT_DIR / "model_card.json"
        if not card_path.exists():
            log.info("No trained models found; training now (one-off, about two minutes)")
            from .training import train_all
            train_all(verbose=False)
        card = json.loads(card_path.read_text(encoding="utf-8"))
        models = {}
        try:
            if card.get("sklearn_version") != sklearn.__version__:
                raise RuntimeError(f"models saved with scikit-learn {card.get('sklearn_version')}, "
                                   f"running {sklearn.__version__}")
            with warnings.catch_warnings():
                warnings.simplefilter("error", category=UserWarning)
                for key in ("crop_model", "soil_model"):
                    models[key] = joblib.load(ARTIFACT_DIR / f"{key}.joblib")
        except Exception as exc:  # version mismatch or missing file: refit the selected algorithms on the same data
            log.warning("Refitting models (%s)", exc)
            from .training import fit_deployed
            models = fit_deployed({k: card[k]["selected_algorithm"] for k in ("crop_model", "soil_model")})
            card["sklearn_version"] = sklearn.__version__
            (ARTIFACT_DIR / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
        _state.update(card=card, **models)
        return _state


def model_card() -> dict:
    return _load()["card"]


def _confidence(p_top: float, margin: float) -> str:
    if p_top >= 0.7 and margin >= 0.3:
        return "high"
    if p_top >= 0.4:
        return "moderate"
    return "low"


def predict(model_key: str, inputs: dict, top_k: int = 5) -> dict:
    state = _load()
    card = state["card"][model_key]
    model = state[model_key]
    features = card["features"]
    missing = [f["label"] for f in features if inputs.get(f["key"]) is None]
    if missing:
        raise ValueError(f"Missing inputs: {', '.join(missing)}")
    row = pd.DataFrame([{f["key"]: float(inputs[f["key"]]) for f in features}])
    proba = model.predict_proba(row)[0]
    order = np.argsort(proba)[::-1]
    out_of_range = []
    for f in features:
        v = float(inputs[f["key"]])
        if v < f["min"] or v > f["max"]:
            out_of_range.append({"feature": f["key"], "label": f["label"], "value": v, "min": f["min"], "max": f["max"],
                                 "message": f"{f['label']} {v:g} is outside the range the model learned from "
                                            f"({f['min']:g}–{f['max']:g} {f['unit']})."})
    results = []
    for rank, idx in enumerate(order[:top_k], 1):
        crop = model.classes_[idx]
        profile = card["profiles"][crop]
        checks = []
        for f in features:
            v, pr = float(inputs[f["key"]]), profile[f["key"]]
            status = "typical" if pr["p10"] <= v <= pr["p90"] else ("below" if v < pr["p10"] else "above")
            checks.append({"feature": f["key"], "label": f["label"], "unit": f["unit"], "value": v,
                           "typical_low": pr["p10"], "typical_high": pr["p90"], "status": status})
        n_typical = sum(c["status"] == "typical" for c in checks)
        results.append({
            "rank": rank, "crop": crop, "name": DISPLAY_NAMES.get(crop, crop),
            "probability": round(float(proba[idx]), 4), "crop_db_slug": CROP_DB_SLUG.get(crop),
            "matching_conditions": n_typical, "total_conditions": len(checks), "checks": checks,
            "summary": f"{n_typical} of {len(checks)} of your conditions are typical for {DISPLAY_NAMES.get(crop, crop).lower()}.",
        })
    p_top = results[0]["probability"]
    margin = p_top - (results[1]["probability"] if len(results) > 1 else 0)
    conf = _confidence(p_top, margin)
    if out_of_range and conf == "high":
        conf = "moderate"
    return {
        "model": card["name"], "algorithm": card["selected_algorithm"], "predictions": results,
        "confidence": conf, "out_of_range": out_of_range,
        "advice": ("Clear match." if conf == "high" else
                   "Several crops match your conditions similarly; compare them in the rotation planner." if conf == "moderate"
                   else "No crop matches strongly. Check the inputs, or consider crops outside this model's list."),
    }


def probability_for(model_key: str, inputs: dict) -> dict[str, float]:
    """Probability for every class (used to show an AI match next to rule-based suitability)."""
    state = _load()
    card = state["card"][model_key]
    row = pd.DataFrame([{f["key"]: float(inputs[f["key"]]) for f in card["features"]}])
    proba = state[model_key].predict_proba(row)[0]
    return {c: float(p) for c, p in zip(state[model_key].classes_, proba)}


def warm_up() -> None:
    try:
        _load()
    except Exception as exc:  # never block the API from starting
        log.error("Could not load ML models: %s", exc)
