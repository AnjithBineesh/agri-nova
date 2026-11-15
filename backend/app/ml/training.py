"""Train, compare and evaluate the Agri Nova machine-learning models.

Run:  python -m app.ml.train

Models
------
1. crop_model  – recommends a crop from soil N, P, K, pH and season temperature, humidity and rainfall
                 (crop_recommendation.csv, 2,200 rows, 22 crops).
2. soil_model  – recommends a crop from a full soil test incl. micronutrients
                 (soil_nutrients_crop.csv, 620 rows, 6 crops).
3. yield data  – india_rainfall_crop_yield_2014_2024.csv is evaluated for yield prediction. A model is only
                 deployed if it beats a constant baseline on cross-validation.

For every classifier, several algorithms are compared with stratified 5-fold cross-validation on an 80 %
training split; the best (by macro-F1) is evaluated once on the untouched 20 % test split, then refit on
all rows for deployment.
"""
import json
import time
import warnings
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (ExtraTreesClassifier, HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestClassifier, RandomForestRegressor)
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score, cross_validate, train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from .features import (ARTIFACT_DIR, CROP_FEATURES, DISPLAY_NAMES, SOIL_FEATURES, WEATHER_REFERENCE, YIELD_DATA,
                       load_crop_data, load_soil_data, monthly_climatology, read_daily_weather_csv, season_months)

SEED = 42


def candidates() -> dict:
    return {
        "Logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000)),
        "k-nearest neighbours": make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=7)),
        "Support vector machine": make_pipeline(StandardScaler(), SVC(C=10, probability=True, random_state=SEED)),
        "Random forest": RandomForestClassifier(n_estimators=400, random_state=SEED, n_jobs=-1),
        "Extra trees": ExtraTreesClassifier(n_estimators=400, random_state=SEED, n_jobs=-1),
        "Gradient boosting": HistGradientBoostingClassifier(random_state=SEED),
    }


def _profiles(df: pd.DataFrame, features: list[str], label: str) -> dict:
    """Typical (10th–90th percentile) range of each feature for every crop, used to explain predictions."""
    out = {}
    for crop, g in df.groupby(label):
        out[crop] = {f: {"p10": round(float(g[f].quantile(0.1)), 2), "median": round(float(g[f].median()), 2),
                         "p90": round(float(g[f].quantile(0.9)), 2)} for f in features}
    return out


def train_classifier(df: pd.DataFrame, features, label: str, name: str) -> tuple[object, dict]:
    keys = [f.key for f in features]
    X, y = df[keys].astype(float), df[label].astype(str)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    comparison = []
    for algo, model in candidates().items():
        t0 = time.time()
        s = cross_validate(model, X_tr, y_tr, cv=cv, scoring=["accuracy", "f1_macro"], n_jobs=1)
        comparison.append({"algorithm": algo, "cv_accuracy_mean": round(float(s["test_accuracy"].mean()), 4),
                           "cv_accuracy_std": round(float(s["test_accuracy"].std()), 4),
                           "cv_macro_f1_mean": round(float(s["test_f1_macro"].mean()), 4),
                           "cv_macro_f1_std": round(float(s["test_f1_macro"].std()), 4),
                           "seconds": round(time.time() - t0, 2)})
    comparison.sort(key=lambda r: (-r["cv_macro_f1_mean"], r["cv_macro_f1_std"]))
    best_name = comparison[0]["algorithm"]
    best = candidates()[best_name].fit(X_tr, y_tr)
    pred = best.predict(X_te)
    classes = sorted(y.unique())
    report = classification_report(y_te, pred, output_dict=True, zero_division=0)
    per_class = [{"crop": c, "name": DISPLAY_NAMES.get(c, c), "precision": round(report[c]["precision"], 3),
                  "recall": round(report[c]["recall"], 3), "f1": round(report[c]["f1-score"], 3),
                  "support": int(report[c]["support"])} for c in classes]
    perm = permutation_importance(best, X_te, y_te, n_repeats=10, random_state=SEED, scoring="f1_macro")
    importance = sorted([{"feature": k, "label": f.label, "importance": round(float(m), 4), "std": round(float(s), 4)}
                         for k, f, m, s in zip(keys, features, perm.importances_mean, perm.importances_std)],
                        key=lambda r: -r["importance"])
    cm = confusion_matrix(y_te, pred, labels=classes)
    confusions = []
    for i, a in enumerate(classes):
        for j, b in enumerate(classes):
            if i != j and cm[i, j]:
                confusions.append({"actual": DISPLAY_NAMES.get(a, a), "predicted": DISPLAY_NAMES.get(b, b),
                                   "count": int(cm[i, j])})
    final = candidates()[best_name].fit(X, y)  # deploy a model refit on all rows
    card = {
        "name": name, "rows": int(len(df)), "classes": [{"key": c, "name": DISPLAY_NAMES.get(c, c),
                                                          "rows": int((y == c).sum())} for c in classes],
        "features": [{"key": f.key, "label": f.label, "unit": f.unit, "help": f.help,
                      "min": round(float(X[f.key].min()), 2), "max": round(float(X[f.key].max()), 2),
                      "median": round(float(X[f.key].median()), 2)} for f in features],
        "algorithm_comparison": comparison, "selected_algorithm": best_name,
        "test_split": {"rows": int(len(X_te)), "accuracy": round(float(accuracy_score(y_te, pred)), 4),
                       "macro_f1": round(float(f1_score(y_te, pred, average="macro")), 4)},
        "per_class": per_class, "confusions": sorted(confusions, key=lambda r: -r["count"])[:10],
        "feature_importance": importance, "profiles": _profiles(df, keys, label),
    }
    return final, card


def evaluate_yield_dataset() -> dict:
    df = pd.read_csv(YIELD_DATA)
    cat = ["State", "District", "Season", "Crop_Type", "Soil_Type", "Irrigation_Type"]
    num = ["Year", "Rainfall_mm", "Avg_Temperature_C", "Humidity_percent", "Fertilizer_Used_kg", "Pesticide_Used_kg",
           "Cultivated_Area_hectares"]
    X = pd.get_dummies(df[cat + num], columns=cat).astype(float)
    y = df["Yield_ton_per_hectare"]
    cv = KFold(n_splits=5, shuffle=True, random_state=SEED)
    results = []
    for algo, model in [("Constant baseline (mean yield)", DummyRegressor()),
                        ("Ridge regression", make_pipeline(StandardScaler(), Ridge())),
                        ("Random forest", RandomForestRegressor(n_estimators=300, min_samples_leaf=5,
                                                                random_state=SEED, n_jobs=-1)),
                        ("Gradient boosting", HistGradientBoostingRegressor(random_state=SEED))]:
        r2 = cross_val_score(model, X, y, cv=cv, scoring="r2")
        mae = -cross_val_score(model, X, y, cv=cv, scoring="neg_mean_absolute_error")
        results.append({"algorithm": algo, "cv_r2_mean": round(float(r2.mean()), 4), "cv_r2_std": round(float(r2.std()), 4),
                        "cv_mae_t_ha": round(float(mae.mean()), 3)})
    best_r2 = max(r["cv_r2_mean"] for r in results if not r["algorithm"].startswith("Constant"))
    by_crop = df.groupby("Crop_Type")["Yield_ton_per_hectare"].agg(["mean", "std"]).round(2)
    corr = df[num + ["Yield_ton_per_hectare"]].corr()["Yield_ton_per_hectare"].drop("Yield_ton_per_hectare").round(3)
    deploy = best_r2 > 0.1
    return {
        "rows": int(len(df)), "target": "Yield_ton_per_hectare", "models": results, "best_cv_r2": best_r2,
        "deployed": deploy,
        "verdict": ("A yield model was deployed." if deploy else
                    "Not deployed: no model predicts yield better than simply using the average yield "
                    f"(best cross-validated R² = {best_r2:.3f}). Every crop has nearly the same yield distribution "
                    f"(means {by_crop['mean'].min()}–{by_crop['mean'].max()} t/ha) and yield shows no correlation "
                    f"with rainfall, temperature, fertiliser or irrigation (|r| ≤ {corr.abs().max():.3f}). "
                    "The dataset appears to be randomly generated, so any yield 'prediction' from it would be "
                    "meaningless."),
        "yield_by_crop": by_crop.reset_index().to_dict("records"),
        "correlation_with_yield": corr.to_dict(),
    }


def weather_reference(crop_model, crop_card: dict) -> dict:
    """Apply the crop model to the bundled daily weather record (Kochi, Kerala, 2020–2025)."""
    daily = read_daily_weather_csv(WEATHER_REFERENCE)
    clim = monthly_climatology(daily)
    medians = {f["key"]: f["median"] for f in crop_card["features"]}
    seasons = [("Kharif (Jun–Oct)", 6, 10), ("Rabi (Nov–Mar)", 11, 3), ("Summer (Mar–May)", 3, 5)]
    examples = []
    for label, s, e in seasons:
        ms = season_months(s, e)
        feats = {"temperature": round(float(clim.loc[ms, "temperature"].mean()), 1),
                 "humidity": round(float(clim.loc[ms, "humidity"].mean()), 1),
                 "rainfall": round(float(clim.loc[ms, "rainfall"].mean()), 1)}
        row = pd.DataFrame([{**{k: medians[k] for k in ("N", "P", "K", "ph")}, **feats}])[
            [f["key"] for f in crop_card["features"]]]
        proba = crop_model.predict_proba(row)[0]
        top = np.argsort(proba)[::-1][:3]
        examples.append({"season": label, "climate": feats,
                         "top_crops": [{"crop": DISPLAY_NAMES.get(crop_model.classes_[k], crop_model.classes_[k]),
                                        "probability": round(float(proba[k]), 3)} for k in top]})
    return {
        "location": "Kochi, Kerala (9.93° N, 76.27° E)", "period": f"{daily['date'].min().date()} to {daily['date'].max().date()}",
        "days": int(len(daily)),
        "monthly_climatology": [{"month": int(m), "temperature": round(float(r.temperature), 1),
                                 "humidity": round(float(r.humidity), 1), "rainfall": round(float(r.rainfall), 1)}
                                for m, r in clim.iterrows()],
        "annual_rainfall_mm": round(float(clim["rainfall"].sum())),
        "examples": examples,
        "note": "Season climate features are computed from the daily weather record; soil values are set to the "
                "dataset medians, so these examples show the effect of climate alone.",
    }


def fit_deployed(selected: dict) -> dict:
    """Refit the already-selected algorithms on all rows (used when saved models can't be loaded)."""
    out = {}
    for key, df, features in (("crop_model", load_crop_data(), CROP_FEATURES), ("soil_model", load_soil_data(), SOIL_FEATURES)):
        keys = [f.key for f in features]
        out[key] = candidates()[selected[key]].fit(df[keys].astype(float), df["label"].astype(str))
        joblib.dump(out[key], ARTIFACT_DIR / f"{key}.joblib", compress=3)
    return out


def train_all(verbose: bool = True) -> dict:
    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", category=UserWarning)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    crop_model, crop_card = train_classifier(load_crop_data(), CROP_FEATURES, "label", "Crop prediction model")
    soil_model, soil_card = train_classifier(load_soil_data(), SOIL_FEATURES, "label", "Soil test crop model")
    joblib.dump(crop_model, ARTIFACT_DIR / "crop_model.joblib", compress=3)
    joblib.dump(soil_model, ARTIFACT_DIR / "soil_model.joblib", compress=3)
    card = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "crop_model": crop_card, "soil_model": soil_card,
        "yield_dataset": evaluate_yield_dataset(),
        "weather_reference": weather_reference(crop_model, crop_card),
        "limitations": [
            "Accuracy is measured on held-out rows of the same datasets. Real fields vary more than these "
            "datasets, so real-world accuracy will be lower.",
            "The crop dataset's units for N, P and K are soil-test values; your laboratory's units may differ. "
            "Inputs outside the training range are flagged and make predictions less reliable.",
            "Rainfall is interpreted as the average monthly rainfall during the growing season.",
            "Predictions suggest crops whose recorded conditions resemble yours. They don't account for market "
            "prices, labour, pests or water rights. Discuss major decisions with a local agronomist.",
        ],
        "training_seconds": round(time.time() - t0, 1),
    }
    (ARTIFACT_DIR / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False))
    if verbose:
        for key in ("crop_model", "soil_model"):
            c = card[key]
            print(f"{c['name']}: {c['selected_algorithm']} – test accuracy {c['test_split']['accuracy']:.3f}, "
                  f"macro-F1 {c['test_split']['macro_f1']:.3f} on {c['test_split']['rows']} held-out rows")
        print("Yield dataset:", card["yield_dataset"]["verdict"])
        print(f"Done in {card['training_seconds']} s → {ARTIFACT_DIR}")
    return card
