from pathlib import Path

from bokeh.document import Document
from bokeh.embed import file_html
from bokeh.events import DocumentReady
from bokeh.layouts import column, row, Spacer
from bokeh.models import (
    CheckboxGroup,
    ColumnDataSource,
    CustomJS,
    Div,
    GlobalInlineStyleSheet,
    InlineStyleSheet,
    PointDrawTool,
    Select,
    Slider,
    Spinner,
)
from bokeh.plotting import figure
from bokeh.resources import INLINE


TITLE = "Linear Elasticity — 3D Volume Element"

# Same visual language as the Mohr-circle classroom app.
BG = "#0B1020"
PANEL = "#121A2B"
PANEL_2 = "#172033"
TEXT = "#EDF2F7"
MUTED = "#9FB0C7"
GRID = "#2A3852"
BLUE = "#64B5F6"
CYAN = "#62E3D5"
ORANGE = "#FFB86B"
RED = "#FF6B6B"
GREEN = "#64D98B"
WHITE = "#FFFFFF"

GLOBAL_CSS = GlobalInlineStyleSheet(css=f"""
html, body {{
    margin: 0 !important;
    background: {BG} !important;
    color: {TEXT} !important;
    font-family: Inter, Segoe UI, Arial, sans-serif !important;
}}
""")

WIDGET_CSS = InlineStyleSheet(css=f"""
:host {{
    color: {TEXT};
    font-family: Inter, Segoe UI, Arial, sans-serif;
}}
input, select {{
    background: {BG} !important;
    color: {TEXT} !important;
    border: 1px solid {GRID} !important;
    border-radius: 7px !important;
}}
label, .bk-slider-title, .bk-input-group label {{ color: {MUTED} !important; }}
.noUi-target {{ background: {GRID} !important; border: 0 !important; box-shadow: none !important; }}
.noUi-connect {{ background: {CYAN} !important; }}
.noUi-handle {{
    background: {TEXT} !important;
    border: 2px solid {CYAN} !important;
    box-shadow: none !important;
}}
""")


def apply_widget_style(*widgets):
    for w in widgets:
        w.stylesheets = [WIDGET_CSS]


def slider_input(label, start, end, step, value, unit, width=225, spin_width=88):
    """Compact slider + numerical input pair with continuous browser-side updates."""
    label_div = Div(
        text=f"<b style='color:{TEXT}'>{label}</b>",
        width=92,
        height=32,
        styles={"color": TEXT},
    )
    slider = Slider(
        start=start,
        end=end,
        step=step,
        value=value,
        show_value=False,
        width=width,
        height=32,
        margin=(0, 4, 0, 0),
    )
    spinner = Spinner(
        low=start,
        high=end,
        step=step,
        value=value,
        width=spin_width,
        height=32,
        margin=(0, 4, 0, 0),
    )
    unit_div = Div(
        text=f"<span style='color:{MUTED}'>{unit}</span>",
        width=62,
        height=32,
        styles={"color": MUTED},
    )
    apply_widget_style(slider, spinner)
    layout = row(label_div, slider, spinner, unit_div, height=36)

    slider.js_on_change(
        "value",
        CustomJS(args=dict(other=spinner), code="if (other.value !== cb_obj.value) other.value = cb_obj.value;"),
    )
    spinner.js_on_change(
        "value",
        CustomJS(args=dict(other=slider), code="if (other.value !== cb_obj.value) other.value = cb_obj.value;"),
    )
    return slider, spinner, layout


def build_app():
    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    case_select = Select(
        title="Loading / constraint case",
        value="Plane Stress",
        options=[
            "Uniaxial Stress",
            "Uniaxial Strain",
            "Plane Stress",
            "Plane Strain",
            "Pure Shear",
            "Isotropic Stress",
        ],
        width=300,
    )

    material_mode = Select(
        title="Material parameters",
        value="Young / Poisson",
        options=["Young / Poisson", "Lamé"],
        width=300,
    )

    shear_driver = Select(
        title="Pure shear controlled by",
        value="Stress τxy",
        options=["Stress τxy", "Strain γxy"],
        width=300,
        visible=False,
    )

    color_mode = Select(
        title="Stress color scale",
        value="Auto",
        options=["Auto", "Lock current", "Lock 2× current", "Manual"],
        width=220,
    )
    manual_color_max = Spinner(
        title="Manual ± max [MPa]",
        low=1.0,
        high=2000.0,
        step=5.0,
        value=100.0,
        width=180,
        visible=False,
    )
    apply_widget_style(case_select, material_mode, shear_driver, color_mode, manual_color_max)

    E_s, E_n, E_row = slider_input("E", 1.0, 250.0, 1.0, 70.0, "GPa")
    nu_s, nu_n, nu_row = slider_input("ν", 0.0, 0.49, 0.01, 0.25, "")
    lam_s, lam_n, lam_row = slider_input("λ", 0.0, 500.0, 1.0, 28.0, "GPa")
    mu_s, mu_n, mu_row = slider_input("μ", 0.5, 200.0, 0.5, 28.0, "GPa")
    lam_row.visible = False
    mu_row.visible = False

    sx_s, sx_n, sx_row = slider_input("σxx", -250.0, 250.0, 1.0, 60.0, "MPa")
    sy_s, sy_n, sy_row = slider_input("σyy", -250.0, 250.0, 1.0, 20.0, "MPa")
    txy_s, txy_n, txy_row = slider_input("τxy", -250.0, 250.0, 1.0, 20.0, "MPa")
    siso_s, siso_n, siso_row = slider_input("σm", -250.0, 250.0, 1.0, -60.0, "MPa")

    ex_s, ex_n, ex_row = slider_input("εxx", -5.0, 5.0, 0.05, 1.0, "×10⁻³")
    ey_s, ey_n, ey_row = slider_input("εyy", -5.0, 5.0, 0.05, -0.3, "×10⁻³")
    gxy_s, gxy_n, gxy_row = slider_input("γxy", -10.0, 10.0, 0.1, 1.0, "×10⁻³")

    def_s, def_n, def_row = slider_input("Visual scale", 1.0, 200.0, 1.0, 60.0, "×")

    options = CheckboxGroup(
        labels=["Stress arrows", "Undeformed reference", "Drag strain handles"],
        active=[0, 1, 2],
        width=350,
    )
    apply_widget_style(options)

    # Initial visibility corresponds to Plane Stress.
    sx_row.visible = True
    sy_row.visible = True
    txy_row.visible = True
    siso_row.visible = False
    ex_row.visible = False
    ey_row.visible = False
    gxy_row.visible = False

    # Stores the captured color scale for the two lock modes.
    color_state = ColumnDataSource(data=dict(locked=[100.0], prev_mode=["Auto"]))

    # ------------------------------------------------------------------
    # Plot and data sources
    # ------------------------------------------------------------------
    p = figure(
        width=700,
        height=540,
        x_range=(-2.05, 2.05),
        y_range=(-1.80, 1.70),
        tools="",
        toolbar_location=None,
        match_aspect=True,
        title="Deformation and stress state",
    )
    p.axis.visible = False
    p.grid.visible = False
    p.outline_line_color = GRID
    p.outline_line_alpha = 0.7
    p.background_fill_color = PANEL
    p.border_fill_color = PANEL
    p.title.text_color = TEXT
    p.title.text_font = "Inter"
    p.title.text_font_size = "16px"

    ghost_source = ColumnDataSource(data=dict(xs=[], ys=[], alpha=[]))
    arrow_source = ColumnDataSource(
        data=dict(x0=[], y0=[], x1=[], y1=[], angle=[], alpha=[], size=[], color=[])
    )
    face_source = ColumnDataSource(data=dict(xs=[], ys=[], color=[], alpha=[]))
    handle_source = ColumnDataSource(
        data=dict(x=[0.0, 0.0, 0.0], y=[0.0, 0.0, 0.0], alpha=[0.0, 0.0, 0.0], size=[0, 0, 0])
    )

    p.multi_line(
        xs="xs",
        ys="ys",
        source=ghost_source,
        line_color=MUTED,
        line_alpha="alpha",
        line_width=1.35,
        line_dash="dashed",
    )

    p.patches(
        xs="xs",
        ys="ys",
        source=face_source,
        fill_color="color",
        fill_alpha="alpha",
        line_color=TEXT,
        line_alpha=0.85,
        line_width=1.5,
    )

    p.segment(
        x0="x0",
        y0="y0",
        x1="x1",
        y1="y1",
        source=arrow_source,
        line_color="color",
        line_alpha="alpha",
        line_width=2.35,
    )
    p.scatter(
        x="x1",
        y="y1",
        source=arrow_source,
        marker="triangle",
        angle="angle",
        size="size",
        fill_color="color",
        line_color="color",
        fill_alpha="alpha",
        line_alpha="alpha",
    )

    handles = p.scatter(
        x="x",
        y="y",
        source=handle_source,
        marker="circle",
        size="size",
        fill_color=PANEL_2,
        line_color=CYAN,
        line_width=2,
        fill_alpha="alpha",
        line_alpha="alpha",
    )
    draw_tool = PointDrawTool(renderers=[handles], add=False)
    p.add_tools(draw_tool)
    p.toolbar.active_drag = draw_tool

    # Small fixed coordinate triad in the upper right.
    triad = ColumnDataSource(
        data=dict(
            x0=[1.48, 1.48, 1.48],
            y0=[1.23, 1.23, 1.23],
            x1=[1.72, 1.24, 1.48],
            y1=[1.09, 1.09, 1.56],
        )
    )
    p.segment("x0", "y0", "x1", "y1", source=triad, line_width=1.6, line_color=MUTED)
    p.text(
        x=[1.77, 1.18, 1.51],
        y=[1.05, 1.05, 1.60],
        text=["x", "y", "z"],
        text_font_size="9pt",
        text_color=MUTED,
    )

    # ------------------------------------------------------------------
    # Readouts
    # ------------------------------------------------------------------
    stress_tensor = Div(width=235, height=205)
    strain_tensor = Div(width=235, height=205)
    color_legend = Div(width=80, height=540)
    state_summary = Div(width=220, height=205)
    case_info = Div(width=430, height=112)

    intro = Div(
        text=f"""
        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
          <div>
            <div style="font-size:28px;font-weight:750;letter-spacing:-0.5px;color:{TEXT};">Linear elasticity</div>
            <div style="font-size:14px;color:{MUTED};margin-top:4px;">Interactive isotropic 3-D volume element</div>
          </div>
          <div style="padding:6px 10px;border-radius:999px;background:{PANEL_2};border:1px solid {GRID};font-size:12px;color:{MUTED};">
            tension +
          </div>
        </div>
        """,
        width=1280,
        height=68,
        styles={"background": BG, "color": TEXT},
        stylesheets=[GLOBAL_CSS],
    )

    drag_note = Div(
        text=f"""
        <div style="font-size:12px;color:{MUTED};line-height:1.45;margin-top:3px;">
          <b style="color:{TEXT}">Arrow convention:</b> blue = normal traction, orange = shear traction.
          With tension positive, tensile arrows point outward and compressive arrows point inward.
          White/cyan handles prescribe strain in the strain-driven cases.
        </div>
        """,
        width=430,
        height=48,
    )

    # ------------------------------------------------------------------
    # Main browser-side constitutive + geometry update
    # ------------------------------------------------------------------
    update = CustomJS(
        args=dict(
            case_select=case_select,
            material_mode=material_mode,
            shear_driver=shear_driver,
            color_mode=color_mode,
            manual_color_max=manual_color_max,
            color_state=color_state,
            E=E_n,
            nu=nu_n,
            lam=lam_n,
            mu=mu_n,
            E_slider=E_s,
            nu_slider=nu_s,
            lam_slider=lam_s,
            mu_slider=mu_s,
            sx=sx_n,
            sy=sy_n,
            txy=txy_n,
            siso=siso_n,
            ex=ex_n,
            ey=ey_n,
            gxy=gxy_n,
            defscale=def_n,
            sx_row=sx_row,
            sy_row=sy_row,
            txy_row=txy_row,
            siso_row=siso_row,
            ex_row=ex_row,
            ey_row=ey_row,
            gxy_row=gxy_row,
            lam_row=lam_row,
            mu_row=mu_row,
            E_row=E_row,
            nu_row=nu_row,
            options=options,
            ghost_source=ghost_source,
            arrow_source=arrow_source,
            face_source=face_source,
            handle_source=handle_source,
            stress_tensor=stress_tensor,
            strain_tensor=strain_tensor,
            state_summary=state_summary,
            case_info=case_info,
            color_legend=color_legend,
        ),
        code=rf"""
function __runElasticUpdate() {{
const BG = "{BG}", PANEL = "{PANEL}", PANEL2 = "{PANEL_2}", TEXT = "{TEXT}", MUTED = "{MUTED}", GRID = "{GRID}";
const BLUE = "{BLUE}", CYAN = "{CYAN}", ORANGE = "{ORANGE}", RED = "{RED}";

// ---------- small linear algebra helpers ----------
function zeros3() {{ return [[0,0,0],[0,0,0],[0,0,0]]; }}
function trace3(A) {{ return A[0][0] + A[1][1] + A[2][2]; }}
function matVec(A, v) {{
    return [
        A[0][0]*v[0] + A[0][1]*v[1] + A[0][2]*v[2],
        A[1][0]*v[0] + A[1][1]*v[1] + A[1][2]*v[2],
        A[2][0]*v[0] + A[2][1]*v[1] + A[2][2]*v[2],
    ];
}}
function stressFromStrain(eps, la, muv) {{
    const tr = trace3(eps);
    const s = zeros3();
    for (let i=0; i<3; i++) {{
        for (let j=0; j<3; j++) s[i][j] = 2*muv*eps[i][j];
        s[i][i] += la*tr;
    }}
    return s;
}}
function strainFromStress(sig, Ev, nuv) {{
    const tr = trace3(sig);
    const e = zeros3();
    for (let i=0; i<3; i++) {{
        for (let j=0; j<3; j++) e[i][j] = ((1+nuv)/Ev)*sig[i][j];
        e[i][i] -= (nuv/Ev)*tr;
    }}
    return e;
}}
function project(v) {{ return [0.8660254037844386*(v[0]-v[1]), v[2]-0.5*(v[0]+v[1])]; }}
function clamp(v, lo, hi) {{ return Math.max(lo, Math.min(hi, v)); }}
function fmt(v, digits=3) {{
    if (!Number.isFinite(v)) return "—";
    const a = Math.abs(v);
    if (a !== 0 && (a >= 1e4 || a < 1e-3)) return v.toExponential(2);
    return v.toFixed(digits);
}}
function setPair(spinner, slider, value) {{
    const v = clamp(value, slider.start, slider.end);
    if (Math.abs(spinner.value-v) > 1e-12) spinner.value = v;
    if (Math.abs(slider.value-v) > 1e-12) slider.value = v;
}}
function hexRGB(hex) {{
    const h=hex.replace('#','');
    return [parseInt(h.substring(0,2),16), parseInt(h.substring(2,4),16), parseInt(h.substring(4,6),16)];
}}
function mix(a,b,t) {{ return Math.round(a + (b-a)*t); }}
function stressColor(v, vmax) {{
    const neutral = hexRGB("{GRID}");
    const comp = hexRGB("{BLUE}");
    const tens = hexRGB("{RED}");
    if (vmax < 1e-12 || Math.abs(v) < 1e-12) return `rgb(${{neutral[0]}},${{neutral[1]}},${{neutral[2]}})`;
    const q = clamp(v/vmax, -1, 1);
    const target = q < 0 ? comp : tens;
    const t = Math.pow(Math.abs(q), 0.82);
    return `rgb(${{mix(neutral[0],target[0],t)}},${{mix(neutral[1],target[1],t)}},${{mix(neutral[2],target[2],t)}})`;
}}
function maxAbsMatrix(A) {{
    let m=0;
    for (let i=0;i<3;i++) for (let j=0;j<3;j++) m=Math.max(m,Math.abs(A[i][j]));
    return m;
}}

// ---------- material parameters ----------
let Ev, nuv, la, muv;
if (material_mode.value === "Young / Poisson") {{
    E_row.visible = true; nu_row.visible = true; lam_row.visible = false; mu_row.visible = false;
    Ev = E.value*1000.0;
    nuv = nu.value;
    muv = Ev/(2*(1+nuv));
    la = Ev*nuv/((1+nuv)*(1-2*nuv));
    setPair(mu, mu_slider, muv/1000.0);
    setPair(lam, lam_slider, la/1000.0);
}} else {{
    E_row.visible = false; nu_row.visible = false; lam_row.visible = true; mu_row.visible = true;
    la = lam.value*1000.0;
    muv = mu.value*1000.0;
    Ev = muv*(3*la + 2*muv)/(la + muv);
    nuv = la/(2*(la + muv));
    setPair(E, E_slider, Ev/1000.0);
    setPair(nu, nu_slider, nuv);
}}
const K = la + 2*muv/3;

// ---------- case-specific inputs and constitutive response ----------
const c = case_select.value;
let sig = zeros3();
let eps = zeros3();
let description = "";
let constraints = "";

sx_row.visible = false; sy_row.visible = false; txy_row.visible = false; siso_row.visible = false;
ex_row.visible = false; ey_row.visible = false; gxy_row.visible = false;
shear_driver.visible = (c === "Pure Shear");

if (c === "Uniaxial Stress") {{
    sx_row.visible = true;
    sig[0][0] = sx.value;
    eps = strainFromStress(sig, Ev, nuv);
    description = "One normal stress is prescribed; the transverse faces are traction-free.";
    constraints = "σyy = σzz = τxy = τxz = τyz = 0";
}} else if (c === "Uniaxial Strain") {{
    ex_row.visible = true;
    eps[0][0] = ex.value*1e-3;
    sig = stressFromStrain(eps, la, muv);
    description = "Axial strain is prescribed while lateral strain is prevented, so transverse stresses develop.";
    constraints = "εyy = εzz = γxy = γxz = γyz = 0";
}} else if (c === "Plane Stress") {{
    sx_row.visible = true; sy_row.visible = true; txy_row.visible = true;
    sig[0][0] = sx.value; sig[1][1] = sy.value; sig[0][1] = sig[1][0] = txy.value;
    eps = strainFromStress(sig, Ev, nuv);
    description = "The z faces are traction-free, but thickness strain εzz is generally non-zero.";
    constraints = "σzz = τxz = τyz = 0";
}} else if (c === "Plane Strain") {{
    ex_row.visible = true; ey_row.visible = true; gxy_row.visible = true;
    eps[0][0] = ex.value*1e-3; eps[1][1] = ey.value*1e-3;
    eps[0][1] = eps[1][0] = 0.5*gxy.value*1e-3;
    sig = stressFromStrain(eps, la, muv);
    description = "Out-of-plane deformation is suppressed, so a restraining σzz generally develops.";
    constraints = "εzz = γxz = γyz = 0";
}} else if (c === "Pure Shear") {{
    if (shear_driver.value === "Stress τxy") {{
        txy_row.visible = true;
        sig[0][1] = sig[1][0] = txy.value;
        eps = strainFromStress(sig, Ev, nuv);
        description = "Only τxy is prescribed; the element changes angle without volumetric strain.";
        constraints = "σxx = σyy = σzz = τxz = τyz = 0";
    }} else {{
        gxy_row.visible = true;
        eps[0][1] = eps[1][0] = 0.5*gxy.value*1e-3;
        sig = stressFromStrain(eps, la, muv);
        description = "Engineering shear strain γxy is prescribed with no normal strain.";
        constraints = "εxx = εyy = εzz = γxz = γyz = 0";
    }}
}} else if (c === "Isotropic Stress") {{
    siso_row.visible = true;
    sig[0][0] = sig[1][1] = sig[2][2] = siso.value;
    eps = strainFromStress(sig, Ev, nuv);
    description = "Equal normal stress in all three directions produces purely volumetric deformation.";
    constraints = "σxx = σyy = σzz = σm; all shear stresses = 0";
}}

// ---------- symmetric stress color scale ----------
const autoColorMax = Math.max(maxAbsMatrix(sig), 1.0);
const mode = color_mode.value;
manual_color_max.visible = (mode === "Manual");
let state = color_state.data;
const prevMode = (state.prev_mode && state.prev_mode.length) ? state.prev_mode[0] : "Auto";
let locked = (state.locked && state.locked.length) ? state.locked[0] : autoColorMax;
if (mode !== prevMode) {{
    if (mode === "Lock current") locked = autoColorMax;
    if (mode === "Lock 2× current") locked = 2*autoColorMax;
    color_state.data = {{locked:[locked], prev_mode:[mode]}};
}}
let colorMax = autoColorMax;
if (mode === "Lock current" || mode === "Lock 2× current") colorMax = Math.max(locked, 1e-9);
if (mode === "Manual") colorMax = Math.max(manual_color_max.value, 1e-9);

// ---------- visual deformation ----------
const requestedScale = defscale.value;
const maxEps = maxAbsMatrix(eps);
const effectiveScale = maxEps > 0 ? Math.min(requestedScale, 0.65/maxEps) : requestedScale;
const capped = effectiveScale < requestedScale - 1e-9;

const V = [
    [-0.5,-0.5,-0.5], [ 0.5,-0.5,-0.5], [ 0.5, 0.5,-0.5], [-0.5, 0.5,-0.5],
    [-0.5,-0.5, 0.5], [ 0.5,-0.5, 0.5], [ 0.5, 0.5, 0.5], [-0.5, 0.5, 0.5]
];
function deform(v) {{
    const eV = matVec(eps,v);
    return [v[0] + effectiveScale*eV[0], v[1] + effectiveScale*eV[1], v[2] + effectiveScale*eV[2]];
}}
const D = V.map(deform);
const P = D.map(project);
const P0 = V.map(project);

const edges = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
const ghostOn = options.active.includes(1);
ghost_source.data = {{
    xs: edges.map(e => [P0[e[0]][0],P0[e[1]][0]]),
    ys: edges.map(e => [P0[e[0]][1],P0[e[1]][1]]),
    alpha: edges.map(_ => ghostOn ? 0.42 : 0.0),
}};

const faces = [
    {{idx:[0,3,7,4], axis:0, sign:-1}}, {{idx:[1,5,6,2], axis:0, sign: 1}},
    {{idx:[0,4,5,1], axis:1, sign:-1}}, {{idx:[3,2,6,7], axis:1, sign: 1}},
    {{idx:[0,1,2,3], axis:2, sign:-1}}, {{idx:[4,7,6,5], axis:2, sign: 1}},
];
const faceData = faces.map(f => {{
    const worldCenter = [0,0,0];
    for (const i of f.idx) {{ worldCenter[0]+=D[i][0]/4; worldCenter[1]+=D[i][1]/4; worldCenter[2]+=D[i][2]/4; }}
    const depth = worldCenter[0]+worldCenter[1]+worldCenter[2];
    return {{
        xs:f.idx.map(i=>P[i][0]), ys:f.idx.map(i=>P[i][1]),
        color:stressColor(sig[f.axis][f.axis],colorMax),
        alpha:f.sign>0 ? 0.91 : 0.70,
        depth:depth,
    }};
}});
faceData.sort((a,b)=>a.depth-b.depth);
face_source.data = {{
    xs:faceData.map(f=>f.xs), ys:faceData.map(f=>f.ys),
    color:faceData.map(f=>f.color), alpha:faceData.map(f=>f.alpha),
}};

// ---------- separate normal and shear traction arrows ----------
const arrowOn = options.active.includes(0);
let maxArrowStress = Math.max(maxAbsMatrix(sig), 1e-12);
const x0=[],y0=[],x1=[],y1=[],angle=[],alpha=[],size=[],color=[];
function pushArrow(a0, a1, col, a) {{
    const dx=a1[0]-a0[0], dy=a1[1]-a0[1];
    const L=Math.hypot(dx,dy);
    x0.push(a0[0]); y0.push(a0[1]); x1.push(a1[0]); y1.push(a1[1]);
    angle.push(Math.atan2(dy,dx)-Math.PI/2);
    alpha.push(arrowOn && L>1e-8 ? a : 0.0);
    size.push(arrowOn && L>1e-8 ? 9 : 0);
    color.push(col);
}}
for (const f of faces) {{
    let wc=[0,0,0];
    for (const i of f.idx) {{ wc[0]+=D[i][0]/4; wc[1]+=D[i][1]/4; wc[2]+=D[i][2]/4; }}
    const pc=project(wc);
    const n=[0,0,0]; n[f.axis]=f.sign;
    const t=matVec(sig,n);
    const sn=sig[f.axis][f.axis];
    const normal=[sn*n[0],sn*n[1],sn*n[2]];
    const shear=[t[0]-normal[0],t[1]-normal[1],t[2]-normal[2]];
    const visAlpha = f.sign>0 ? 0.98 : 0.46;

    // Normal arrow: tension begins at the face and points outward.
    // Compression begins outside and points inward to the face, keeping the arrow visible.
    if (Math.abs(sn)>1e-10) {{
        const r=Math.sqrt(Math.abs(sn)/maxArrowStress);
        const L=0.18+0.38*r;
        const d=[Math.sign(sn)*n[0],Math.sign(sn)*n[1],Math.sign(sn)*n[2]];
        const pv=project([L*d[0],L*d[1],L*d[2]]);
        if (sn>0) pushArrow(pc,[pc[0]+pv[0],pc[1]+pv[1]],BLUE,visAlpha);
        else pushArrow([pc[0]-pv[0],pc[1]-pv[1]],pc,BLUE,visAlpha);
    }}

    const smag=Math.hypot(shear[0],shear[1],shear[2]);
    if (smag>1e-10) {{
        const L=0.18+0.38*Math.sqrt(smag/maxArrowStress);
        const d=[shear[0]/smag,shear[1]/smag,shear[2]/smag];
        const pv=project([L*d[0],L*d[1],L*d[2]]);
        // Tangential arrow centred on the face.
        pushArrow([pc[0]-0.5*pv[0],pc[1]-0.5*pv[1]],[pc[0]+0.5*pv[0],pc[1]+0.5*pv[1]],ORANGE,visAlpha);
    }}
}}
arrow_source.data={{x0,y0,x1,y1,angle,alpha,size,color}};

// ---------- drag handles ----------
const dragOn = options.active.includes(2);
function deformedFaceCenter(axis) {{
    const v=[0,0,0]; v[axis]=0.5;
    return project(deform(v));
}}
const hx=deformedFaceCenter(0), hy=deformedFaceCenter(1);
let hxs=[hx[0],hy[0],hx[0]], hys=[hx[1],hy[1],hx[1]];
let ha=[0,0,0], hs=[0,0,0];
if (dragOn && c === "Uniaxial Strain") {{ ha[0]=0.96; hs[0]=13; }}
if (dragOn && c === "Plane Strain") {{ ha[0]=0.96; ha[1]=0.96; hs[0]=13; hs[1]=13; }}
if (dragOn && c === "Pure Shear" && shear_driver.value === "Strain γxy") {{ ha[2]=0.96; hs[2]=13; }}
handle_source.data={{x:hxs,y:hys,alpha:ha,size:hs}};

// ---------- text panels ----------
function stressMatrixHTML(A) {{
    const rows=A.map(r=>`<tr>${{r.map(v=>`<td style="padding:6px 7px;text-align:right;background:${{stressColor(v,colorMax)}};border:2px solid ${{PANEL}};border-radius:4px;color:${{TEXT}};min-width:46px;">${{fmt(v,2)}}</td>`).join("")}}</tr>`).join("");
    return `<table style="border-collapse:separate;border-spacing:2px;margin-top:8px;">${{rows}}</table>`;
}}
function strainMatrixHTML(A) {{
    const rows=A.map(r=>`<tr>${{r.map(v=>`<td style="padding:6px 7px;text-align:right;background:${{PANEL2}};border:1px solid ${{GRID}};border-radius:4px;color:${{TEXT}};min-width:46px;">${{fmt(v*1e3,3)}}</td>`).join("")}}</tr>`).join("");
    return `<table style="border-collapse:separate;border-spacing:2px;margin-top:8px;">${{rows}}</table>`;
}}
const panelStyle=`background:${{PANEL}};border:1px solid ${{GRID}};border-radius:12px;padding:10px 10px;height:176px;box-sizing:border-box;`;
stress_tensor.text = `
<div style="${{panelStyle}}">
  <div style="font-size:14px;font-weight:700;color:${{TEXT}};">Stress tensor σ</div>
  ${{stressMatrixHTML(sig)}}
  <div style="font-size:10px;color:${{MUTED}};margin-top:4px;">MPa · shared stress colors</div>
</div>`;
strain_tensor.text = `
<div style="${{panelStyle}}">
  <div style="font-size:14px;font-weight:700;color:${{TEXT}};text-align:right;">Strain tensor ε</div>
  ${{strainMatrixHTML(eps)}}
  <div style="font-size:10px;color:${{MUTED}};margin-top:4px;text-align:right;">×10⁻³ · εxy = γxy/2</div>
</div>`;

color_legend.text = `
<div style="position:relative;width:78px;height:538px;box-sizing:border-box;">
  <div style="position:absolute;right:4px;top:8px;bottom:8px;width:20px;background:linear-gradient(to top,{BLUE} 0%,{GRID} 50%,{RED} 100%);border:1px solid ${{GRID}};border-radius:5px;"></div>
  <div style="position:absolute;right:30px;top:3px;font-size:10px;color:${{MUTED}};white-space:nowrap;">+${{fmt(colorMax,1)}}</div>
  <div style="position:absolute;right:30px;top:50%;transform:translateY(-50%);font-size:10px;color:${{MUTED}};">0</div>
  <div style="position:absolute;right:30px;bottom:3px;font-size:10px;color:${{MUTED}};white-space:nowrap;">−${{fmt(colorMax,1)}}</div>
  <div style="position:absolute;left:0;top:50%;transform:translate(-13px,-50%) rotate(-90deg);font-size:10px;font-weight:700;color:${{TEXT}};white-space:nowrap;">σ [MPa] · ${{mode}}</div>
</div>`;

state_summary.text = `
<div style="background:${{PANEL}};border:1px solid ${{GRID}};border-radius:12px;padding:10px 12px;height:176px;box-sizing:border-box;color:${{MUTED}};font-size:11px;line-height:1.4;">
  <div style="font-size:14px;font-weight:700;color:${{TEXT}};margin-bottom:9px;text-align:center;">Material</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;column-gap:10px;row-gap:9px;">
    <div><span style="color:${{TEXT}};font-weight:650;">E</span><br>${{fmt(Ev/1000,2)}} GPa</div>
    <div><span style="color:${{TEXT}};font-weight:650;">ν</span><br>${{fmt(nuv,3)}}</div>
    <div><span style="color:${{TEXT}};font-weight:650;">λ</span><br>${{fmt(la/1000,2)}} GPa</div>
    <div><span style="color:${{TEXT}};font-weight:650;">μ = G</span><br>${{fmt(muv/1000,2)}} GPa</div>
    <div style="grid-column:1 / span 2;text-align:center;"><span style="color:${{TEXT}};font-weight:650;">K</span><br>${{fmt(K/1000,2)}} GPa</div>
  </div>
</div>`;

case_info.text = `
<div style="font-size:13px;line-height:1.42;padding:10px 12px;border:1px solid ${{GRID}};border-radius:11px;background:${{PANEL2}};color:${{MUTED}};">
  <b style="color:${{TEXT}};font-size:14px;">${{c}}</b><br>${{description}}<br>
  <span><b style="color:${{TEXT}};">Constraint:</b> ${{constraints}}</span>
</div>`;
}}
window.__elastic_update = __runElasticUpdate;
__runElasticUpdate();
""",
    )

    # ------------------------------------------------------------------
    # Drag callback
    # ------------------------------------------------------------------
    drag_cb = CustomJS(
        args=dict(
            handle_source=handle_source,
            case_select=case_select,
            shear_driver=shear_driver,
            ex=ex_n,
            ey=ey_n,
            gxy=gxy_n,
            ex_slider=ex_s,
            ey_slider=ey_s,
            gxy_slider=gxy_s,
            defscale=def_n,
            options=options,
        ),
        code=r"""
if (!options.active.includes(2)) return;
const c=case_select.value;
if (!(c === "Uniaxial Strain" || c === "Plane Strain" || (c === "Pure Shear" && shear_driver.value === "Strain γxy"))) return;

function project(v){ return [0.8660254037844386*(v[0]-v[1]), v[2]-0.5*(v[0]+v[1])]; }
function dot2(a,b){ return a[0]*b[0]+a[1]*b[1]; }
function clamp(v,lo,hi){ return Math.max(lo,Math.min(hi,v)); }
function currentEps(){
    const e=[[0,0,0],[0,0,0],[0,0,0]];
    if (c === "Uniaxial Strain") e[0][0]=ex.value*1e-3;
    if (c === "Plane Strain") {
        e[0][0]=ex.value*1e-3; e[1][1]=ey.value*1e-3;
        e[0][1]=e[1][0]=0.5*gxy.value*1e-3;
    }
    if (c === "Pure Shear") e[0][1]=e[1][0]=0.5*gxy.value*1e-3;
    return e;
}
function maxAbs(A){ let m=0; for(let i=0;i<3;i++)for(let j=0;j<3;j++)m=Math.max(m,Math.abs(A[i][j])); return m; }
function deformCenter(axis,e,s){
    const v=[0,0,0]; v[axis]=0.5;
    const u=[
        e[0][0]*v[0]+e[0][1]*v[1]+e[0][2]*v[2],
        e[1][0]*v[0]+e[1][1]*v[1]+e[1][2]*v[2],
        e[2][0]*v[0]+e[2][1]*v[1]+e[2][2]*v[2]
    ];
    return project([v[0]+s*u[0],v[1]+s*u[1],v[2]+s*u[2]]);
}
const e=currentEps();
const me=maxAbs(e);
const s=me>0 ? Math.min(defscale.value,0.65/me) : defscale.value;
const expectedX=deformCenter(0,e,s), expectedY=deformCenter(1,e,s);
const actual=[[handle_source.data.x[0],handle_source.data.y[0]], [handle_source.data.x[1],handle_source.data.y[1]], [handle_source.data.x[2],handle_source.data.y[2]]];
const expected=[expectedX,expectedY,expectedX];
let best=-1, bestD=0;
for(let i=0;i<3;i++){
    const dx=actual[i][0]-expected[i][0], dy=actual[i][1]-expected[i][1];
    const d=dx*dx+dy*dy;
    if(d>bestD){bestD=d;best=i;}
}
if(bestD<1e-12) return;
const delta=[actual[best][0]-expected[best][0], actual[best][1]-expected[best][1]];
const px=[0.8660254037844386,-0.5], py=[-0.8660254037844386,-0.5];

if(best===0 && (c==="Uniaxial Strain" || c==="Plane Strain")){
    const de=dot2(delta,px)/(0.5*s*dot2(px,px));
    const val=clamp(ex.value + de*1e3, ex_slider.start, ex_slider.end);
    ex.value=val; ex_slider.value=val;
} else if(best===1 && c==="Plane Strain"){
    const de=dot2(delta,py)/(0.5*s*dot2(py,py));
    const val=clamp(ey.value + de*1e3, ey_slider.start, ey_slider.end);
    ey.value=val; ey_slider.value=val;
} else if(best===2 && c==="Pure Shear" && shear_driver.value==="Strain γxy"){
    const dg=dot2(delta,py)/(0.25*s*dot2(py,py));
    const val=clamp(gxy.value + dg*1e3, gxy_slider.start, gxy_slider.end);
    gxy.value=val; gxy_slider.value=val;
}
// PointDrawTool updates the source continuously in BokehJS. Redraw the full
// state immediately so deformation, arrows and tensor values track the cursor.
if (window.__elastic_update) window.__elastic_update();
""",
    )
    handle_source.js_on_change("data", drag_cb)

    for w in [E_n, nu_n, lam_n, mu_n, sx_n, sy_n, txy_n, siso_n, ex_n, ey_n, gxy_n, def_n, manual_color_max]:
        w.js_on_change("value", update)
    for w in [case_select, material_mode, shear_driver, color_mode]:
        w.js_on_change("value", update)
    options.js_on_change("active", update)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    section_title = lambda s: Div(
        text=f"<b style='font-size:15px;color:{TEXT}'>{s}</b>",
        height=25,
        styles={"color": TEXT},
    )

    material_panel = column(
        section_title("Material"), material_mode, E_row, nu_row, lam_row, mu_row,
        width=465,
    )
    load_panel = column(
        section_title("Applied loading / strain"), case_select, shear_driver,
        sx_row, sy_row, txy_row, siso_row, ex_row, ey_row, gxy_row,
        width=465,
    )
    view_panel = column(
        section_title("Display"), def_row, options,
        row(color_mode, manual_color_max),
        width=465,
    )

    controls = column(
        material_panel,
        Div(text=f"<div style='height:1px;background:{GRID};margin:5px 0 9px'></div>", height=15),
        load_panel,
        Div(text=f"<div style='height:1px;background:{GRID};margin:5px 0 9px'></div>", height=15),
        view_panel,
        case_info,
        drag_note,
        width=470,
        height=745,
        styles={
            "background": PANEL,
            "border": f"1px solid {GRID}",
            "border-radius": "14px",
            "padding": "16px",
            "box-sizing": "border-box",
        },
    )

    # Full-height stress scale directly beside the cube. The lower readout row
    # begins at the cube plot's left edge: stress tensor left, material card
    # centered, strain tensor right.
    visual_row = row(color_legend, p, spacing=0, width=780, height=540)
    tensor_content = row(
        stress_tensor,
        state_summary,
        strain_tensor,
        spacing=5,
        width=700,
        height=205,
    )
    tensor_row = row(
        Spacer(width=80, height=205),
        tensor_content,
        spacing=0,
        width=780,
        height=205,
    )
    left = column(visual_row, tensor_row, spacing=0, width=780, height=745)

    layout = column(
        intro,
        row(left, controls, spacing=16, height=745),
        width=1320,
        styles={"background": BG, "padding": "20px", "box-sizing": "border-box"},
    )

    return layout, update


def main():
    layout, update = build_app()
    out = Path(__file__).with_name("linear_elasticity_visualizer_v4.html")
    doc = Document()
    doc.add_root(layout)
    doc.js_on_event(DocumentReady, update)
    out.write_text(file_html(doc, INLINE, TITLE), encoding="utf-8")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
