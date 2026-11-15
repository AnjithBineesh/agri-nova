"""PDF farm reports: a plain-language farmer report and a detailed scientific report."""
import io
from datetime import date

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

FOREST = colors.HexColor("#123d2b")
GREEN = colors.HexColor("#2f7d4f")
BLUE = colors.HexColor("#2563a8")
ORANGE = colors.HexColor("#c2710c")
MUTED = colors.HexColor("#5b6b62")
LIGHT = colors.HexColor("#eef3ef")
SERIES = [colors.HexColor(c) for c in ("#2f7d4f", "#2563a8", "#c2710c", "#7a4fa3", "#8a8f2a", "#b0413e")]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

styles = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=FOREST, fontSize=18, spaceAfter=6)
H2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=FOREST, fontSize=13, spaceBefore=10, spaceAfter=4)
BODY = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=13, alignment=TA_LEFT)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=10.5, textColor=MUTED)
WARN = ParagraphStyle("warn", parent=BODY, textColor=colors.HexColor("#8a4b08"), backColor=colors.HexColor("#fff4e5"),
                      borderPadding=6, spaceBefore=4, spaceAfter=6)


def _p(text, style=BODY):
    return Paragraph(str(text), style)


def _table(rows, widths=None, header=True, font=8.5):
    data = [[_p(c, ParagraphStyle("c", parent=BODY, fontSize=font, leading=font + 2.5)) if isinstance(c, str) else c
             for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9d5cc")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), LIGHT)]
    t.setStyle(TableStyle(style))
    return t


def _climate_chart(monthly):
    d = Drawing(170 * mm, 62 * mm)
    ch = VerticalBarChart()
    ch.x, ch.y, ch.width, ch.height = 12 * mm, 10 * mm, 150 * mm, 44 * mm
    ch.data = [[m["precip_mm"] or 0 for m in monthly], [m["et0_mm"] or 0 for m in monthly]]
    ch.categoryAxis.categoryNames = MONTHS
    ch.categoryAxis.labels.fontSize = 7
    ch.valueAxis.labels.fontSize = 7
    ch.valueAxis.valueMin = 0
    ch.bars[0].fillColor, ch.bars[1].fillColor = BLUE, ORANGE
    ch.bars.strokeColor = None
    ch.groupSpacing = 4
    d.add(ch)
    lg = Legend()
    lg.x, lg.y, lg.fontSize = 120 * mm, 60 * mm, 7
    lg.colorNamePairs = [(BLUE, "Rainfall (mm)"), (ORANGE, "Reference ET0 (mm)")]
    lg.columnMaximum = 2
    lg.alignment = "right"
    d.add(lg)
    return d


def _soc_chart(series: dict[str, list[float]]):
    d = Drawing(170 * mm, 62 * mm)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 14 * mm, 10 * mm, 110 * mm, 46 * mm
    lp.data = [list(enumerate(v, 0)) for v in series.values()]
    for i in range(len(series)):
        lp.lines[i].strokeColor = SERIES[i % len(SERIES)]
        lp.lines[i].strokeWidth = 1.6
    lp.xValueAxis.labels.fontSize = 7
    lp.yValueAxis.labels.fontSize = 7
    d.add(lp)
    lg = Legend()
    lg.x, lg.y, lg.fontSize = 130 * mm, 56 * mm, 6.5
    lg.colorNamePairs = [(SERIES[i % len(SERIES)], n[:30]) for i, n in enumerate(series)]
    lg.columnMaximum = 8
    lg.deltay = 9
    lg.alignment = "right"
    d.add(lg)
    d.add(String(14 * mm, 2 * mm, "Season number", fontSize=7, fillColor=MUTED))
    return d


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(15 * mm, 10 * mm, "Agri Nova – Earth intelligence for crop rotation decisions. Decision support "
                                        "only; consult local agricultural extension officers for major decisions.")
    canvas.drawRightString(195 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_report(kind: str, farm, ctx, datasets: list[dict], suitability: list[dict], strategies: list[dict],
                 sims: dict[str, dict], ai: dict | None = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                            bottomMargin=18 * mm, title=f"Agri Nova report – {farm.farm_name}")
    sci = kind == "scientific"
    el = []
    el.append(_p("AGRI NOVA", ParagraphStyle("brand", parent=SMALL, textColor=GREEN, fontSize=9)))
    el.append(_p(f"{'Scientific' if sci else 'Farm'} report: {farm.farm_name}", H1))
    el.append(_p(f"Generated {date.today().isoformat()} · {farm.region or ''} {farm.state or ''} {farm.country}", SMALL))
    if ctx.profile.is_demo:
        el.append(_p("<b>DEMONSTRATION DATA.</b> Some environmental values in this report are synthetic "
                     "demonstration values, not real observations. Do not use for real decisions.", WARN))

    # 1–2. Farm profile and location
    el.append(_p("1. Farm profile and location", H2))
    loc = (f"{farm.latitude:.5f}, {farm.longitude:.5f} (selected by {farm.location_source}); boundary: "
           f"{'user-drawn polygon' if farm.boundary_status == 'user_drawn' else ('verified polygon' if farm.boundary_status == 'verified' else 'not provided – a point location only')}")
    el.append(_table([["Item", "Value"], ["Location", loc],
                      ["Area", f"{farm.area_ha:.2f} ha ({farm.area_source})" if farm.area_ha else "not provided"],
                      ["Irrigation", farm.irrigation_type + (f", ~{farm.irrigation_capacity_mm:.0f} mm/season"
                                                             if farm.irrigation_capacity_mm else "")],
                      ["Current crop", farm.current_crop or "not provided"],
                      ["Growing seasons", "; ".join(f"{s['name']} ({MONTHS[s['start_month'] - 1]}–"
                                                    f"{MONTHS[s['end_month'] - 1]})" for s in ctx.seasons)
                       + f" – {ctx.seasons_source}"],
                      ["Residue management", farm.residue_management]], widths=[40 * mm, 140 * mm]))

    # 3–4. Environment & sources
    el.append(_p("2. Environmental conditions", H2))
    p = ctx.profile
    if p.has_climate:
        t_ann = sum(m["t_mean"] for m in p.monthly) / 12
        et0 = sum(m["et0_mm"] or 0 for m in p.monthly)
        el.append(_p(f"Average temperature about <b>{t_ann:.1f} °C</b>; average annual rainfall about "
                     f"<b>{p.annual_precip_mean:.0f} mm</b> against a reference evapotranspiration of about "
                     f"<b>{et0:.0f} mm</b> per year. "
                     + (f"Rainfall varies by about {p.annual_precip_cv * 100:.0f}% from year to year. "
                        if p.annual_precip_cv else "")
                     + (f"Observed temperature trend: {p.temp_trend_c_per_decade:+.2f} °C per decade." if
                        p.temp_trend_c_per_decade is not None else "")))
        el.append(_climate_chart(p.monthly))
    else:
        el.append(_p("Climate data has not been retrieved for this farm yet.", WARN))
    if p.soil_moisture.get("surface"):
        sm = p.soil_moisture["surface"]
        el.append(_p(f"Surface soil moisture (~0–5 cm, 9 km grid): mean {sm['mean']:.2f} m³/m³; latest "
                     f"{sm['latest']:.2f} on {sm['latest_date']}. This is a regional satellite value, not a field "
                     "measurement."))
    if p.vegetation:
        el.append(_p(f"Latest cloud-free NDVI: {p.vegetation['ndvi_latest']:.2f} on {p.vegetation['ndvi_latest_date']} "
                     f"({p.vegetation['source_label']} resolution)."))
    if p.terrain.get("slope_deg") is not None:
        el.append(_p(f"Terrain (30 m elevation model): elevation {p.terrain['elevation_m']:.0f} m, slope {p.terrain['slope_deg']:.1f}°."))
    el.append(_p("Data sources used", ParagraphStyle("h3", parent=BODY, fontName="Helvetica-Bold")))
    rows = [["Dataset", "Status", "Resolution", "Coverage / records"]]
    for d in datasets:
        if d["status"] in ("not_requested",) and not sci:
            continue
        rows.append([d["display_name"] + (" (DEMO)" if d["is_demo"] else ""), d["status"].replace("_", " "),
                     d["display_resolution"],
                     (f"{d['coverage_start']} – {d['coverage_end']}, {d['record_count']} values"
                      if d["coverage_start"] else d["display_message"])])
    el.append(_table(rows, widths=[38 * mm, 25 * mm, 40 * mm, 77 * mm], font=7.5))

    # 5–6. Soil
    el.append(_p("3. Soil profile and assessment", H2))
    sa = ctx.soil_assessment
    if sa.get("available"):
        srows = [["Parameter", "Value", "Rating", "What it means"]]
        for it in sa["items"]:
            srows.append([it["parameter"], f"{it['value']} {it['unit'] or ''}", str(it["class"]),
                          it["explanation"] if sci else it["explanation"].split(". ")[0] + "."])
        el.append(_table(srows, widths=[34 * mm, 25 * mm, 25 * mm, 96 * mm], font=7.5))
        src = (ctx.soil or {}).get("data_source")
        el.append(_p(f"Source: {'confirmed laboratory report' if src == 'lab_report_confirmed' else 'farmer-entered values'}"
                     f"; rating system: {sa['rating_system']}. {sa['methodology']}", SMALL))
    else:
        el.append(_p(sa.get("message", "No soil data."), WARN))

    # 7. Suitability
    el.append(_p("4. Crop suitability", H2))
    for season in ctx.seasons:
        rs = [r for r in suitability if r["season"] == season["name"]]
        good = [r for r in rs if r["class"] == "suitable"][:8]
        mod = [r for r in rs if r["class"] == "moderately_suitable"][:6]
        good_txt = ", ".join("%s (%.0f)" % (r["crop_name"], r["score"]) for r in good) or "none"
        mod_txt = ", ".join(r["crop_name"] for r in mod) or "none"
        el.append(_p(f"<b>{season['name']}</b>: suitable – {good_txt}; moderately suitable – {mod_txt}."))
        if sci:
            rows = [["Crop", "Score", "Class", "Data", "Main limitation / constraint"]]
            for r in rs[:14]:
                lim = (r["critical_constraints"] or r["limitations"] or ["—"])[0]
                rows.append([r["crop_name"], f"{r['score']:.0f}" if r["score"] is not None else "–",
                             r["class"].replace("_", " "), f"{r['data_completeness'] * 100:.0f}%", lim[:260]])
            el.append(_table(rows, widths=[32 * mm, 14 * mm, 28 * mm, 20 * mm, 86 * mm], font=7))

    # AI crop prediction
    if ai:
        el.append(_p("AI crop prediction", H2))
        for s in ai["seasons"]:
            if s.get("result"):
                top = ", ".join("%s (%.0f%%)" % (p["name"], p["probability"] * 100) for p in s["result"]["predictions"][:3])
                el.append(_p(f"<b>{s['label']}</b>: {top}. Confidence: {s['result']['confidence']}."))
                for w in s["result"]["out_of_range"][:3]:
                    el.append(_p("Note: " + w["message"], SMALL))
            else:
                missing = [k for k, v in s["inputs"].items() if v is None]
                el.append(_p(f"<b>{s['label']}</b>: not available (missing {', '.join(missing)}).", SMALL))
        el.append(_p("Machine-learning model trained on recorded crop, soil and climate conditions. Probabilities show "
                     "how closely your conditions resemble those of each crop in the training data.", SMALL))

    # 8–12. Rotations & simulation
    el.append(PageBreak())
    el.append(_p("5. Crop rotation strategies", H2))
    if strategies:
        w = strategies[0]["priority_weights"]
        el.append(_p("Priority weights: " + ", ".join(f"{k.replace('_', ' ')} {v}%" for k, v in w.items()), SMALL))
        rows = [["Rank", "Strategy", "Sequence", "Priority score", "Irrigation need / yr", "SOC change (5 yr)",
                 "N balance"]]
        for s in sorted(strategies, key=lambda s: s["scores"].get("rank") or 99):
            sm = s["scores"]["simulation_summary"]
            d_soc = (sm.get("soc_change_t_ha") or {}).get("central")
            rows.append([str(s["scores"].get("rank") or "–"), s["strategy_name"], s["explanation"]["sequence_text"],
                         f"{s['scores']['priority_score']:.0f}" if s["scores"]["priority_score"] is not None else "–",
                         f"{s['explanation']['water']['average_annual_irrigation_need_mm']} mm",
                         f"{d_soc:+.2f} t C/ha" if d_soc is not None else "–",
                         f"{sm['n_balance_cum_kg_ha']:+.0f} kg N/ha"])
        el.append(_table(rows, widths=[11 * mm, 30 * mm, 50 * mm, 17 * mm, 24 * mm, 24 * mm, 24 * mm], font=7))
        for s in strategies:
            ex = s["explanation"]
            block = [_p(f"<b>{s['strategy_name']}</b>: {ex['sequence_text']}"), _p(ex["reason"], SMALL)]
            for label, items in (("Soil", ex["soil_health"][:3]), ("Nutrients", ex["nutrients"][:2]),
                                 ("Climate", ex["climate_risks"][:2]), ("Rotation notes", ex["rotation_warnings"][:2])):
                if items:
                    block.append(_p(f"<i>{label}:</i> " + " ".join(items), SMALL))
            block.append(_p(f"<i>Economics:</i> {ex['economics']}", SMALL))
            el.append(KeepTogether(block + [Spacer(1, 4)]))
        el.append(_p("The highest-scoring rotation reflects the stated priorities; it is not universally best.", SMALL))
    else:
        el.append(_p("No rotation strategies have been generated yet.", WARN))

    if sims:
        el.append(_p("6. Five-year simulation (illustrative)", H2))
        series = {n: [sim["summary"]["soc_initial_t_ha"]] + [r["soc_t_ha"]["central"] for r in sim["seasons"]
                                                             if not r["continuation"]]
                  for n, sim in sims.items()}
        el.append(_p("Projected topsoil organic carbon stock (t C/ha, 0–30 cm), central estimate; season 0 is the "
                     "starting stock:", SMALL))
        el.append(_soc_chart(series))
        first = next(iter(sims.values()))
        if sci:
            rows = [["Yr", "Season", "Crop", "ETc mm", "Irrig. need mm", "N bal. cum", "SOC (low–high)",
                     "Vulnerability", "Erosion"]]
            for r in first["seasons"]:
                if r["continuation"]:
                    continue
                rows.append([str(r["year"]), r["season"], r["crop_name"], str(r["water"]["etc_mm"]),
                             str(r["water"]["irrigation_need_mm"]), f"{r['n_balance_cum']:+.0f}",
                             f"{r['soc_t_ha']['central']:.1f} ({r['soc_t_ha']['low']:.1f}–{r['soc_t_ha']['high']:.1f})",
                             r["climate_vulnerability_class"], r["erosion_class"]])
            el.append(_p(f"Season-by-season results for: {next(iter(sims))}", SMALL))
            el.append(_table(rows, widths=[8 * mm, 22 * mm, 36 * mm, 14 * mm, 17 * mm, 17 * mm, 30 * mm, 20 * mm,
                                           16 * mm], font=6.8))
        el.append(_p("Assumptions", ParagraphStyle("h3", parent=BODY, fontName="Helvetica-Bold")))
        for k, v in first["assumptions"].items():
            el.append(_p(f"<b>{k.replace('_', ' ').capitalize()}:</b> {v}", SMALL))

    el.append(_p("7. Risks and limitations", H2))
    for t in ["Satellite and climate datasets describe areas from 30 m to tens of kilometres; they are not "
              "field-level measurements.", "Satellites do not measure soil pH or available N, P, K; soil "
              "values come only from soil tests.", "Simulations show directional, comparative outcomes under stated "
              "assumptions. They do not guarantee yields or soil improvement.",
              "Agronomic coefficients marked 'indicative' should be calibrated with local research.",
              "For high-impact decisions, consult local agricultural extension officers and qualified agronomists."] \
            + [f"Data gap: {g}" for g in ctx.profile.gaps]:
        el.append(_p("• " + t, BODY))
    if sci:
        el.append(_p("8. Methodology", H2))
        for t in [
            "Climate: monthly weather climatology (10 complete years) and daily data for the current year; "
            "reference ET0 by FAO-56 Penman–Monteith (Hargreaves fallback). Rainfall from satellite daily "
            "totals when ≥12 complete months are available.",
            "Suitability: ECOCROP trapezoidal ranges for temperature, annual rainfall and pH; FAO-56 seasonal water "
            "balance with FAO/AGLW effective rainfall; season fit; texture/drainage; nutrients; salinity. Weighted sum "
            "over available factors; critical constraints override scores.",
            "Rotation generation: beam search over suitable crop options per season, scored by agronomic rotation rules "
            "and multi-objective indices; finalists evaluated with the simulator under baseline and a stress test "
            "(+1.5 °C, −15% rainfall).",
            "Simulation: state-based seasonal model – single-pool SOC with ICBM humification and Q10 decomposition; "
            "partial N/P/K balances with legume %Ndfa and residual credits; FAO-56 water balance; qualitative erosion "
            "index.",
            "Crop database sources: FAO ECOCROP (via Recocrop), FAO-56, FAO Irrigation Water Management Manual 3, "
            "indicative nutrient coefficients (IPNI/IFA; Herridge et al. 2008; Peoples et al. 2009)."]:
            el.append(_p("• " + t, BODY))
    doc.build(el, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
