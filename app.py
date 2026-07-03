import io
import os
import re
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.colors as mcolors
import matplotlib.font_manager as font_manager
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib.path import Path
from matplotlib.patches import PathPatch

try:
    import openpyxl
except ImportError:
    openpyxl = None


# =========================
# BASIC SETUP
# =========================

st.set_page_config(
    page_title="Generátor grafov",
    page_icon="📈",
    layout="wide"
)

DEFAULT_DATA = """label;value
Jun 2021;-0.5
Dec 2021;-0.5
Mar 2022;-0.5
Jun 2022;-0.5
Sep 2022;0.75
Dec 2022;2.0
Mar 2023;3.0
Jun 2023;3.5
Sep 2023;4.0
Dec 2023;4.0
Mar 2024;4.0
Jun 2024;3.75
Sep 2024;3.5
Dec 2024;3.0
Mar 2025;2.5
Jun 2025;2.0
Sep 2025;2.0
Dec 2025;2.0
Mar 2026;2.0
Jun 2026;2.2
"""

JULI_FONT_FILES = {
    "Light": "JuliSans-Light.otf",
    "Regular": "JuliSans-Regular.otf",
    "Medium": "JuliSans-Medium.otf",
    "Bold": "JuliSans-Bold.otf",
    "Black": "JuliSans-Black.otf",
}


# =========================
# RESOURCE HELPERS
# =========================

def get_base_path():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS

    return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(relative_path):
    return os.path.join(get_base_path(), relative_path)


def get_fonts_dir():
    return get_resource_path("fonts")


def get_juli_font_path(weight_label):
    filename = JULI_FONT_FILES.get(weight_label)

    if not filename:
        return None

    font_path = os.path.join(get_fonts_dir(), filename)

    if os.path.exists(font_path):
        return font_path

    return None


def get_missing_juli_fonts():
    missing_fonts = []

    for filename in JULI_FONT_FILES.values():
        font_path = os.path.join(get_fonts_dir(), filename)

        if not os.path.exists(font_path):
            missing_fonts.append(filename)

    return missing_fonts


def register_juli_fonts():
    for filename in JULI_FONT_FILES.values():
        font_path = os.path.join(get_fonts_dir(), filename)

        if os.path.exists(font_path):
            try:
                font_manager.fontManager.addfont(font_path)
            except Exception:
                pass


def make_font_properties(font_path, size, fallback_weight="normal"):
    if font_path and os.path.exists(font_path):
        return font_manager.FontProperties(
            fname=font_path,
            size=size
        )

    return font_manager.FontProperties(
        size=size,
        weight=fallback_weight
    )


# =========================
# DATA HELPERS
# =========================

def normalize_number(value):
    if pd.isna(value):
        return np.nan

    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)

    text = str(value).strip()
    text = text.replace("\u00a0", "")
    text = text.replace(" ", "")
    text = text.replace("%", "")

    if "," in text and "." not in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return np.nan


def format_axis_label(value):
    if pd.isna(value):
        return ""

    if isinstance(value, pd.Timestamp):
        return value.strftime("%b %Y")

    if hasattr(value, "strftime") and not isinstance(value, str):
        try:
            return value.strftime("%b %Y")
        except Exception:
            pass

    text = str(value).strip()

    if text.endswith(" 00:00:00"):
        text = text.replace(" 00:00:00", "")

    return text


def clean_dataframe(df):
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")

    cleaned_columns = []

    for index, col in enumerate(df.columns):
        column_name = str(col).strip()

        if column_name == "" or column_name.lower().startswith("unnamed"):
            column_name = f"Stĺpec {index + 1}"

        cleaned_columns.append(column_name)

    df.columns = cleaned_columns

    return df


def read_table_from_text(text):
    text = text.strip()

    if not text:
        return pd.DataFrame()

    try:
        df = pd.read_csv(io.StringIO(text), sep=None, engine="python", dtype=str)
    except Exception:
        df = pd.read_csv(io.StringIO(text), sep=";", dtype=str)

    if len(df.columns) < 2:
        df = pd.read_csv(io.StringIO(text), sep="\t", header=None, dtype=str)

    return clean_dataframe(df)


def get_excel_sheet_names(uploaded_file):
    if uploaded_file is None:
        return []

    if openpyxl is None:
        raise ImportError(
            "Chýba balík openpyxl. Nainštaluj ho cez: "
            "./buildenv/bin/python -m pip install openpyxl"
        )

    uploaded_file.seek(0)
    excel_file = pd.ExcelFile(uploaded_file, engine="openpyxl")
    return excel_file.sheet_names


def read_table_from_excel(uploaded_file, sheet_name, header_row_number):
    if uploaded_file is None:
        return pd.DataFrame()

    if openpyxl is None:
        raise ImportError(
            "Chýba balík openpyxl. Nainštaluj ho cez: "
            "./buildenv/bin/python -m pip install openpyxl"
        )

    uploaded_file.seek(0)

    header_index = max(0, int(header_row_number) - 1)

    df = pd.read_excel(
        uploaded_file,
        sheet_name=sheet_name,
        header=header_index,
        engine="openpyxl"
    )

    return clean_dataframe(df)


def slugify_filename(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9áäčďéíĺľňóôŕšťúýž]+", "-", text)
    text = text.strip("-")
    return text or "graf"


def remove_duplicate_ticks(minor_ticks, major_ticks, tolerance=1e-9):
    cleaned = []

    for minor_value in minor_ticks:
        if not any(abs(minor_value - major_value) < tolerance for major_value in major_ticks):
            cleaned.append(minor_value)

    return np.array(cleaned)


def unique_sorted_values(values, min_value, max_value):
    cleaned = []

    for value in values:
        if value < min_value - 1e-9 or value > max_value + 1e-9:
            continue

        rounded_value = round(float(value), 10)

        if rounded_value not in cleaned:
            cleaned.append(rounded_value)

    return sorted(cleaned)


def draw_manual_grid(
    ax,
    x_grid_positions,
    y_grid_positions,
    grid_color,
    grid_line_width,
    grid_alpha,
    show_vertical_grid,
    show_horizontal_grid
):
    if show_horizontal_grid:
        for y_value in y_grid_positions:
            ax.axhline(
                y=y_value,
                color=grid_color,
                linewidth=grid_line_width,
                alpha=grid_alpha,
                zorder=0
            )

    if show_vertical_grid:
        for x_value in x_grid_positions:
            ax.axvline(
                x=x_value,
                color=grid_color,
                linewidth=grid_line_width,
                alpha=grid_alpha,
                zorder=0
            )


# =========================
# CHART EXPORT
# =========================

def create_chart_png(
    df,
    x_col,
    y_col,
    title,
    line_color,
    grid_color,
    text_color,
    title_font_path,
    axis_font_path,
    width_px,
    height_px,
    dpi,
    y_min,
    y_max,
    y_major_step,
    y_minor_step,
    x_label_every,
    x_grid_every,
    point_every,
    x_label_rotation,
    x_label_pad,
    use_gradient,
    gradient_bottom_alpha,
    gradient_top_alpha,
    line_width,
    point_size,
    title_size,
    axis_label_size,
    grid_line_width,
    grid_alpha,
    show_vertical_grid,
    show_horizontal_grid,
    transparent_background
):
    labels = df[x_col].apply(format_axis_label).astype(str).tolist()
    values = df[y_col].apply(normalize_number).to_numpy(dtype=float)

    valid_mask = ~np.isnan(values)
    labels = [label for label, is_valid in zip(labels, valid_mask) if is_valid]
    values = values[valid_mask]

    if len(labels) < 2:
        raise ValueError("Na graf sú potrebné aspoň dva platné dátové body.")

    x = np.arange(len(labels))
    y = values

    fig_w = width_px / dpi
    fig_h = height_px / dpi

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)

    if transparent_background:
        fig.patch.set_alpha(0)
        ax.set_facecolor("none")
    else:
        fig.patch.set_facecolor("white")
        ax.set_facecolor("white")

    fig.subplots_adjust(
        left=0.13,
        right=0.93,
        top=0.78,
        bottom=0.30
    )

    ax.set_xlim(x[0] - 0.3, x[-1] + 0.3)

    # Dôležité:
    # spodok grafu je presne y_min, aby X labels ostali pod grafom,
    # nie v priestore gradientu.
    ax.set_ylim(y_min, y_max + 0.45)

    title_font_properties = make_font_properties(
        font_path=title_font_path,
        size=title_size,
        fallback_weight="bold"
    )

    axis_font_properties = make_font_properties(
        font_path=axis_font_path,
        size=axis_label_size,
        fallback_weight="normal"
    )

    x_axis_font_properties = make_font_properties(
        font_path=axis_font_path,
        size=axis_label_size * 0.75,
        fallback_weight="normal"
    )

    ax.set_title(
        title,
        fontproperties=title_font_properties,
        color=line_color,
        pad=42
    )

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_axisbelow(True)

    major_y_ticks = np.arange(y_min, y_max + 0.001, y_major_step)
    all_minor_y_ticks = np.arange(y_min, y_max + 0.001, y_minor_step)
    minor_y_ticks = remove_duplicate_ticks(all_minor_y_ticks, major_y_ticks)

    ax.set_yticks(major_y_ticks)
    ax.set_yticklabels(
        [f"{tick:g}" for tick in major_y_ticks],
        fontproperties=axis_font_properties,
        color=text_color
    )

    if len(minor_y_ticks) > 0:
        ax.set_yticks(minor_y_ticks, minor=True)

    x_label_every = max(1, int(x_label_every))
    x_grid_every = max(1, int(x_grid_every))
    point_every = max(1, int(point_every))

    label_positions = x[::x_label_every]
    grid_positions = x[::x_grid_every]

    ax.set_xticks(label_positions)
    ax.set_xticklabels(
        [labels[i] for i in label_positions],
        rotation=x_label_rotation,
        ha="center",
        va="top",
        fontproperties=x_axis_font_properties,
        color=text_color
    )

    y_grid_positions = unique_sorted_values(
        values=list(major_y_ticks) + list(minor_y_ticks),
        min_value=y_min,
        max_value=y_max
    )

    draw_manual_grid(
        ax=ax,
        x_grid_positions=grid_positions,
        y_grid_positions=y_grid_positions,
        grid_color=grid_color,
        grid_line_width=grid_line_width,
        grid_alpha=grid_alpha,
        show_vertical_grid=show_vertical_grid,
        show_horizontal_grid=show_horizontal_grid
    )

    ax.tick_params(axis="both", which="both", length=0)
    ax.tick_params(axis="y", pad=20)
    ax.tick_params(axis="x", pad=x_label_pad)

    if use_gradient:
        base = y_min
        rgba = mcolors.to_rgba(line_color)
        gradient_height = 512

        alpha_gradient = np.linspace(
            gradient_bottom_alpha,
            gradient_top_alpha,
            gradient_height
        ).reshape(gradient_height, 1)

        gradient = np.zeros((gradient_height, 1, 4))
        gradient[:, :, 0] = rgba[0]
        gradient[:, :, 1] = rgba[1]
        gradient[:, :, 2] = rgba[2]
        gradient[:, :, 3] = alpha_gradient

        image = ax.imshow(
            gradient,
            aspect="auto",
            origin="lower",
            extent=[x[0], x[-1], base, y_max],
            zorder=1
        )

        verts = [(x[0], base)] + list(zip(x, y)) + [(x[-1], base), (x[0], base)]
        codes = [Path.MOVETO] + [Path.LINETO] * len(x) + [Path.LINETO, Path.CLOSEPOLY]

        path = Path(verts, codes)
        patch = PathPatch(path, facecolor="none", edgecolor="none")
        ax.add_patch(patch)
        image.set_clip_path(patch)

    ax.plot(
        x,
        y,
        color=line_color,
        linewidth=line_width,
        zorder=3
    )

    point_positions = x[::point_every]
    point_values = y[::point_every]

    if point_size > 0:
        ax.scatter(
            point_positions,
            point_values,
            s=point_size,
            color=line_color,
            edgecolor=line_color,
            linewidth=0,
            zorder=4
        )

    buffer = io.BytesIO()

    fig.savefig(
        buffer,
        format="png",
        dpi=dpi,
        facecolor=fig.get_facecolor(),
        transparent=transparent_background
    )

    plt.close(fig)

    buffer.seek(0)
    return buffer.getvalue()


# =========================
# UI
# =========================

register_juli_fonts()

st.title("Generátor grafov")
st.caption("Deterministický export grafov do PNG bez AI generovania.")

missing_juli_fonts = get_missing_juli_fonts()

if missing_juli_fonts:
    st.warning(
        "Chýbajú font súbory v priečinku `fonts`: "
        + ", ".join(missing_juli_fonts)
        + ". Appka bude fungovať, ale použije fallback font."
    )

left_col, right_col = st.columns([0.42, 0.58])

with left_col:
    st.subheader("1. Dáta")

    input_mode = st.radio(
        "Zdroj dát",
        ["Nahrať XLSX", "Vložiť tabuľku"],
        horizontal=True
    )

    raw_df = pd.DataFrame()

    if input_mode == "Nahrať XLSX":
        uploaded_file = st.file_uploader(
            "Nahraj Excel súbor",
            type=["xlsx", "xlsm"]
        )

        if uploaded_file is None:
            st.info("Nahraj `.xlsx` alebo `.xlsm` súbor.")
            st.stop()

        try:
            sheet_names = get_excel_sheet_names(uploaded_file)

            selected_sheet = st.selectbox(
                "Sheet",
                sheet_names,
                index=0
            )

            header_row_number = st.number_input(
                "Riadok s názvami stĺpcov",
                min_value=1,
                max_value=50,
                value=1,
                step=1,
                help="Ak má Excel nad tabuľkou nadpisy alebo prázdne riadky, nastav riadok, kde sú názvy stĺpcov."
            )

            raw_df = read_table_from_excel(
                uploaded_file=uploaded_file,
                sheet_name=selected_sheet,
                header_row_number=header_row_number
            )

        except Exception as error:
            st.error(f"Excel sa nepodarilo načítať: {error}")
            st.stop()

    else:
        pasted_data = st.text_area(
            "Vlož dáta",
            value=DEFAULT_DATA,
            height=360,
            help="Odporúčaný formát: label;value"
        )

        raw_df = read_table_from_text(pasted_data)

    if raw_df.empty or len(raw_df.columns) < 2:
        st.warning("Vlož alebo nahraj tabuľku aspoň s dvoma stĺpcami.")
        st.stop()

    st.subheader("2. Stĺpce")

    columns = list(raw_df.columns)

    x_col = st.selectbox(
        "Stĺpec pre X os",
        columns,
        index=0
    )

    y_col = st.selectbox(
        "Stĺpec pre hodnoty",
        columns,
        index=1 if len(columns) > 1 else 0
    )

    preview_df = raw_df[[x_col, y_col]].copy()
    preview_df[x_col] = preview_df[x_col].apply(format_axis_label)
    preview_df[y_col] = preview_df[y_col].apply(normalize_number)
    preview_df = preview_df.dropna()

    if len(preview_df) < 2:
        st.error("V stĺpci hodnôt nie sú aspoň dve platné čísla.")
        st.stop()

    st.dataframe(
        preview_df,
        use_container_width=True,
        height=220,
        hide_index=True
    )

with right_col:
    st.subheader("3. Nastavenia grafu")

    title = st.text_input(
        "Názov grafu",
        value="Depozitná sadzba ECB v %"
    )

    settings_col_1, settings_col_2, settings_col_3 = st.columns(3)

    with settings_col_1:
        width_px = st.number_input("Šírka PNG", min_value=800, max_value=8000, value=1920, step=100)
        height_px = st.number_input("Výška PNG", min_value=600, max_value=8000, value=1080, step=100)
        dpi = st.number_input("DPI", min_value=72, max_value=600, value=200, step=10)

    with settings_col_2:
        auto_y = st.checkbox("Automatický rozsah Y", value=True)

        data_min = float(preview_df[y_col].min())
        data_max = float(preview_df[y_col].max())

        if auto_y:
            y_min_default = np.floor(data_min)
            y_max_default = np.ceil(data_max)
        else:
            y_min_default = -1.0
            y_max_default = 5.0

        y_min = st.number_input("Y min", value=float(y_min_default), step=0.5)
        y_max = st.number_input("Y max", value=float(y_max_default), step=0.5)

        y_major_step = st.number_input("Hlavný krok Y osi", min_value=0.1, value=1.0, step=0.1)
        y_minor_step = st.number_input("Jemný krok Y gridu", min_value=0.1, value=0.5, step=0.1)

    with settings_col_3:
        x_label_every = st.number_input("Popis X každých N bodov", min_value=1, value=1, step=1)
        x_grid_every = st.number_input("X grid každých N bodov", min_value=1, value=1, step=1)
        point_every = st.number_input("Bodka každých N bodov", min_value=1, value=1, step=1)

    st.subheader("4. Vizuál")

    visual_col_1, visual_col_2, visual_col_3 = st.columns(3)

    with visual_col_1:
        line_color = st.text_input("Farba krivky HEX", value="#0097DB")
        grid_color = st.text_input("Farba gridu HEX", value="#E8E8E8")
        text_color = st.text_input("Farba textu HEX", value="#8A8A8A")

        use_gradient = st.checkbox("Gradient pod krivkou", value=True)
        gradient_bottom_alpha = st.slider("Gradient intenzita dole", 0.0, 1.0, 0.35, 0.01)
        gradient_top_alpha = st.slider("Gradient intenzita hore", 0.0, 1.0, 0.06, 0.01)
        transparent_background = st.checkbox("Transparentné pozadie", value=False)

    with visual_col_2:
        line_width = st.slider("Hrúbka krivky", min_value=0.5, max_value=8.0, value=2.2, step=0.1)
        point_size = st.slider("Veľkosť bodiek", min_value=0, max_value=200, value=48, step=2)
        grid_line_width = st.slider("Hrúbka gridu", min_value=0.1, max_value=3.0, value=0.35, step=0.05)
        grid_alpha = st.slider("Jemnosť gridu", min_value=0.05, max_value=1.0, value=0.35, step=0.05)

        show_horizontal_grid = st.checkbox("Horizontálny grid", value=True)
        show_vertical_grid = st.checkbox("Vertikálny grid", value=True)

    with visual_col_3:
        title_size = st.slider("Veľkosť nadpisu", min_value=16, max_value=90, value=44, step=1)
        axis_label_size = st.slider("Veľkosť textov osí", min_value=8, max_value=40, value=17, step=1)

        title_font_weight_label = st.selectbox(
            "Rez fontu nadpisu",
            ["Light", "Regular", "Medium", "Bold", "Black"],
            index=3
        )

        axis_font_weight_label = st.selectbox(
            "Rez fontu osí",
            ["Light", "Regular", "Medium", "Bold", "Black"],
            index=1
        )

        x_label_rotation = st.selectbox(
            "Rotácia textov X osi",
            [90, 270],
            index=1
        )

        x_label_pad = st.slider(
            "Odsadenie X labelov",
            min_value=0,
            max_value=80,
            value=18,
            step=1
        )

    title_font_path = get_juli_font_path(title_font_weight_label)
    axis_font_path = get_juli_font_path(axis_font_weight_label)

    if y_max <= y_min:
        st.error("Y max musí byť vyššie ako Y min.")
        st.stop()

    try:
        png_bytes = create_chart_png(
            df=preview_df,
            x_col=x_col,
            y_col=y_col,
            title=title,
            line_color=line_color,
            grid_color=grid_color,
            text_color=text_color,
            title_font_path=title_font_path,
            axis_font_path=axis_font_path,
            width_px=int(width_px),
            height_px=int(height_px),
            dpi=int(dpi),
            y_min=float(y_min),
            y_max=float(y_max),
            y_major_step=float(y_major_step),
            y_minor_step=float(y_minor_step),
            x_label_every=int(x_label_every),
            x_grid_every=int(x_grid_every),
            point_every=int(point_every),
            x_label_rotation=int(x_label_rotation),
            x_label_pad=int(x_label_pad),
            use_gradient=bool(use_gradient),
            gradient_bottom_alpha=float(gradient_bottom_alpha),
            gradient_top_alpha=float(gradient_top_alpha),
            line_width=float(line_width),
            point_size=float(point_size),
            title_size=int(title_size),
            axis_label_size=int(axis_label_size),
            grid_line_width=float(grid_line_width),
            grid_alpha=float(grid_alpha),
            show_vertical_grid=bool(show_vertical_grid),
            show_horizontal_grid=bool(show_horizontal_grid),
            transparent_background=bool(transparent_background)
        )

        st.subheader("5. Náhľad")
        st.image(png_bytes, use_container_width=True)

        filename = f"{slugify_filename(title)}.png"

        st.download_button(
            label="Stiahnuť PNG",
            data=png_bytes,
            file_name=filename,
            mime="image/png"
        )

    except Exception as error:
        st.error(f"Graf sa nepodarilo vytvoriť: {error}")