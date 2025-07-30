import io
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image

# --- Rutas a assets ---
ASSETS = Path(__file__).parent / "assets"
FAVICON = ASSETS / "logo.jpg"   # pon tu archivo aquí

# --- Page config (favicon y título) ---
try:
    icon_img = Image.open(FAVICON)
    st.set_page_config(
        page_title="Asignador de Matches",
        page_icon=icon_img,      # también puedes usar un emoji: "👥"
        layout="wide"
    )
except Exception:
    # Fallback si no encuentra el archivo
    st.set_page_config(page_title="Asignador de Matches", page_icon="👥", layout="wide")


st.set_page_config(page_title="Asignador de Matches", layout="wide")

# =========================
# Utilidades
# =========================
def cargar_matriz_excel(file, sheet_name=0) -> pd.DataFrame:
    """Lee la matriz desde Excel. Primera columna es el índice (peruanos)."""
    df = pd.read_excel(file, sheet_name=sheet_name, index_col=0)
    df.index = df.index.astype(str).str.strip()
    df.columns = df.columns.astype(str).str.strip()
    # Asegura numérico
    df = df.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return df

def top_n_disponibles(series: pd.Series, disponibles: list, n: int):
    """Devuelve lista [(extranjero, score)] ordenada desc para columnas disponibles."""
    s = series[disponibles].astype(float)
    candidatos = list(zip(s.index.tolist(), s.values.tolist()))
    candidatos.sort(key=lambda x: x[1], reverse=True)
    return candidatos[:min(n, len(candidatos))]

def inicializar_estado():
    st.session_state.df = None                 # matriz completa
    st.session_state.disponibles = []          # columnas aún libres
    st.session_state.row_idx = 0               # índice de fila actual
    st.session_state.asignaciones = []         # [{"Peruano","Extranjero","Score"}]
    st.session_state.sheet_name = 0            # hoja

def reiniciar_y_cargar(df: pd.DataFrame):
    st.session_state.df = df
    st.session_state.disponibles = df.columns.tolist()
    st.session_state.row_idx = 0
    st.session_state.asignaciones = []

def exportar_excel(asignaciones, disponibles):
    """Genera un Excel en memoria con asignaciones y no asignados."""
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        asign_df = pd.DataFrame(asignaciones, columns=["Peruano", "Extranjero", "Score"])
        asign_df.to_excel(writer, sheet_name="Asignaciones", index=False)
        no_asignados = pd.DataFrame(sorted(disponibles), columns=["Extranjero_no_asignado"])
        no_asignados.to_excel(writer, sheet_name="No_asignados", index=False)
    out.seek(0)
    return out

# =========================
# Interfaz
# =========================
st.title("👥 Asignador de Matches (Peruanos ↔ Extranjeros)")

with st.sidebar:
    st.header("⚙️ Configuración")
    if "df" not in st.session_state:
        inicializar_estado()

    uploaded = st.file_uploader(
        "Sube la matriz (Excel). Fila = Peruano, Columnas = Extranjeros, celdas = score 0–1",
        type=["xlsx", "xls"],
    )
    sheet_name = st.text_input("Nombre/índice de hoja (opcional)", value=str(st.session_state.sheet_name))
    if uploaded:
        try:
            # Si escribieron un número, úsalo como índice; si no, como nombre.
            sn = int(sheet_name) if sheet_name.isdigit() else sheet_name
            df_loaded = cargar_matriz_excel(uploaded, sheet_name=sn)
            st.success(f"Matriz cargada: {df_loaded.shape[0]} peruanos × {df_loaded.shape[1]} extranjeros")
            if st.button("🔄 Iniciar / Reiniciar asignaciones", use_container_width=True):
                reiniciar_y_cargar(df_loaded)
                st.rerun()
        except Exception as e:
            st.error(f"Error cargando Excel: {e}")

    if st.session_state.df is not None:
        st.caption(f"Peruanos: {len(st.session_state.df.index)} | Extranjeros: {len(st.session_state.disponibles)}")
        if st.button("🧹 Reiniciar (manteniendo el archivo)", use_container_width=True):
            reiniciar_y_cargar(st.session_state.df)
            st.rerun()

# Si no hay matriz cargada, muestra instrucciones
if st.session_state.df is None:
    st.info(
        "Sube tu archivo Excel desde la barra lateral. "
        "La primera columna debe contener los **peruanos** (índice) y las columnas restantes a los **extranjeros**. "
        "Las celdas son las probabilidades (0 a 1)."
    )
    st.stop()

df = st.session_state.df
disponibles = st.session_state.disponibles
row_idx = st.session_state.row_idx
asignaciones = st.session_state.asignaciones

# Estado finalizado
if row_idx >= len(df.index) or len(disponibles) == 0:
    st.success("Proceso finalizado.")
    col1, col2 = st.columns([2,1])
    with col1:
        st.write("**Resumen de asignaciones:**")
        if asignaciones:
            st.dataframe(pd.DataFrame(asignaciones), use_container_width=True, height=350)
        else:
            st.write("No se generaron asignaciones.")
    with col2:
        xls_bytes = exportar_excel(asignaciones, disponibles)
        st.download_button(
            "⬇️ Descargar Excel de salida",
            xls_bytes,
            file_name="asignaciones_buddies.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    st.stop()

# Fila actual
peruano = df.index[row_idx]
st.subheader(f"[{row_idx+1}/{len(df.index)}] Peruano: **{peruano}**")

# Panel de selección
cols_panel = st.columns([1, 2])
with cols_panel[0]:
    max_n = len(disponibles)
    n = st.number_input(
        f"¿Cuántos matches asignar a {peruano}?",
        min_value=0,
        max_value=max_n,
        value=min(2, max_n),  # por defecto 2 si se puede
        step=1,
    )

with cols_panel[1]:
    # Propuesta top-N
    propuesta = top_n_disponibles(df.loc[peruano], disponibles, max(1, n))
    st.write("**Propuesta top-N** (ordenada por score):")
    st.dataframe(
        pd.DataFrame(propuesta[:n], columns=["Extranjero", "Score"]),
        use_container_width=True,
        height=200,
    )

# Selección manual con multiselect (por defecto propone top-N)
lista_ampliada = top_n_disponibles(df.loc[peruano], disponibles, 20)
opts = [c for c, _ in lista_ampliada]
scores_map = {c: s for c, s in lista_ampliada}
preseleccion = [c for c, _ in propuesta[:n]]

seleccion = st.multiselect(
    f"Selecciona hasta {n} extranjero(s) (puedes ajustar la propuesta):",
    options=opts,
    default=preseleccion[:n],
    max_selections=n if n > 0 else None,
)

# Botones de acción
c1, c2, c3 = st.columns([1,1,2])
confirmar = c1.button("✅ Confirmar y continuar")
omitir = c2.button("⏭️ Omitir fila")

if confirmar:
    if n == 0:
        # Nada que asignar, avanzar fila
        st.session_state.row_idx += 1
        st.rerun()

    if not seleccion:
        st.warning("No seleccionaste ningún extranjero. Ajusta N o selecciona manualmente.")
        st.stop()

    if len(seleccion) > n:
        st.warning(f"Seleccionaste {len(seleccion)} > N ({n}). Reduce la selección.")
        st.stop()

    # Registra asignaciones y bloquea columnas
    for ext in seleccion:
        score = float(scores_map.get(ext, df.loc[peruano, ext]))
        asignaciones.append({"Peruano": peruano, "Extranjero": ext, "Score": round(score, 4)})
        if ext in disponibles:
            disponibles.remove(ext)

    st.session_state.row_idx += 1
    st.session_state.asignaciones = asignaciones
    st.session_state.disponibles = disponibles
    st.rerun()

if omitir:
    st.session_state.row_idx += 1
    st.rerun()

# Vista rápida del estado actual
st.markdown("---")
c4, c5 = st.columns([2,1])
with c4:
    st.write("**Asignaciones ya confirmadas:**")
    if asignaciones:
        st.dataframe(pd.DataFrame(asignaciones), use_container_width=True, height=250)
    else:
        st.caption("Aún no hay asignaciones confirmadas.")
with c5:
    st.write("**Extranjeros disponibles:**")
    st.write(len(disponibles))
