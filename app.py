# app.py
import io
from pathlib import Path

import pandas as pd
import streamlit as st


# ======================================================
# Configuración de página y búsqueda de logo
# ======================================================
HERE = Path(__file__).parent
LOGO_CANDIDATES = [
    HERE / "assets" / "logo.png",
    HERE / "assets" / "logo.jpg",
    HERE / "logo.png",
    HERE / "logo.jpg",
]
LOGO_PATH = next((p for p in LOGO_CANDIDATES if p.exists()), None)

st.set_page_config(
    page_title="Asignador de Matches",
    page_icon=str(LOGO_PATH) if LOGO_PATH else "👥",
    layout="wide",
)

# ======================================================
# Utilidades
# ======================================================
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
    if not disponibles:
        return []
    s = series[disponibles].astype(float)
    candidatos = list(zip(s.index.tolist(), s.values.tolist()))
    candidatos.sort(key=lambda x: x[1], reverse=True)
    return candidatos[:min(n, len(candidatos))]


def inicializar_estado():
    st.session_state.df = None                 # matriz completa
    st.session_state.disponibles = []          # columnas aún libres
    st.session_state.row_idx = 0               # índice de fila actual
    st.session_state.asignaciones = []         # [{"Pasada","Peruano","Extranjero","Score"}]
    st.session_state.sheet_name = "0"          # hoja por defecto (texto, se castea luego)
    st.session_state.pass_num = 1              # pasada actual
    st.session_state.max_passes = 1            # número de pasadas (configurable)


def reiniciar_y_cargar(df: pd.DataFrame):
    st.session_state.df = df
    st.session_state.disponibles = df.columns.tolist()
    st.session_state.row_idx = 0
    st.session_state.asignaciones = []
    st.session_state.pass_num = 1


def exportar_excel(asignaciones, disponibles):
    """Genera un Excel en memoria con asignaciones y no asignados."""
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        asign_df = pd.DataFrame(asignaciones, columns=["Pasada", "Peruano", "Extranjero", "Score"])
        asign_df.to_excel(writer, sheet_name="Asignaciones", index=False)
        no_asignados = pd.DataFrame(sorted(disponibles), columns=["Extranjero_no_asignado"])
        no_asignados.to_excel(writer, sheet_name="No_asignados", index=False)
    out.seek(0)
    return out


# ======================================================
# Interfaz
# ======================================================
st.title("👥 Asignador de Matches (Peruanos ↔ Extranjeros)")

with st.sidebar:
    if LOGO_PATH:
        # Coloca el logo arriba de la barra lateral
        st.image(str(LOGO_PATH), use_container_width=True)

    st.header("⚙️ Configuración")

    # Estado inicial
    if "df" not in st.session_state:
        inicializar_estado()

    uploaded = st.file_uploader(
        "Sube la matriz (Excel). Fila = Peruano, Columnas = Extranjeros, celdas = score 0–1",
        type=["xlsx", "xls"],
    )

    st.session_state.sheet_name = st.text_input(
        "Nombre/índice de hoja (opcional)",
        value=st.session_state.sheet_name,
        help="Puedes escribir el nombre de la hoja o su índice (0, 1, ...).",
    )

    if uploaded:
        try:
            # Convierte la entrada a índice si es dígito; en otro caso usa nombre
            sn = int(st.session_state.sheet_name) if str(st.session_state.sheet_name).isdigit() else st.session_state.sheet_name
            df_loaded = cargar_matriz_excel(uploaded, sheet_name=sn)
            st.success(f"Matriz cargada: {df_loaded.shape[0]} peruanos × {df_loaded.shape[1]} extranjeros")

            # Selector de número de pasadas
            st.session_state.max_passes = st.number_input(
                "Número de pasadas",
                min_value=1, max_value=5, value=2, step=1,
                help="Cantidad de vueltas por todas las filas. En cada pasada solo se asignan extranjeros aún disponibles."
            )

            if st.button("🔄 Iniciar / Reiniciar asignaciones", use_container_width=True):
                reiniciar_y_cargar(df_loaded)
                st.rerun()
        except Exception as e:
            st.error(f"Error cargando Excel: {e}")

    if st.session_state.df is not None:
        st.caption(f"Peruanos: {len(st.session_state.df.index)} | Extranjeros disponibles: {len(st.session_state.disponibles)}")
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

# ======================================================
# Lógica principal de asignación
# ======================================================
df = st.session_state.df
disponibles = st.session_state.disponibles
row_idx = st.session_state.row_idx
asignaciones = st.session_state.asignaciones

# ¿Terminó la vuelta actual o no quedan disponibles?
if row_idx >= len(df.index) or len(disponibles) == 0:
    # ¿Quedan extranjeros y aún podemos hacer más pasadas?
    if len(disponibles) > 0 and st.session_state.pass_num < st.session_state.max_passes:
        st.info(f"Completada la pasada {st.session_state.pass_num}. "
                f"Iniciando pasada {st.session_state.pass_num + 1}…")
        st.session_state.row_idx = 0
        st.session_state.pass_num += 1
        st.rerun()
    else:
        # Final definitivo
        st.success("Proceso finalizado.")
        col1, col2 = st.columns([2, 1])
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
st.subheader(f"[Pasada {st.session_state.pass_num}/{st.session_state.max_passes}] "
             f"[{row_idx+1}/{len(df.index)}] Peruano: **{peruano}**")

# Panel de selección (N + propuesta)
cols_panel = st.columns([1, 2])
with cols_panel[0]:
    max_n = len(disponibles)
    n = st.number_input(
        f"¿Cuántos matches asignar a {peruano}?",
        min_value=0,
        max_value=max_n,
        value=min(2, max_n),
        step=1,
        help="Define cuántos extranjeros quieres asignar a esta persona en esta pasada."
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

# Selección manual (multiselect) sobre una lista ampliada
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
c1, c2 = st.columns([1, 1])
confirmar = c1.button("✅ Confirmar y continuar")
omitir = c2.button("⏭️ Omitir fila")

if confirmar:
    if n == 0:
        # Nada que asignar: avanzar a la siguiente fila
        st.session_state.row_idx += 1
        st.rerun()

    if not seleccion:
        st.warning("No seleccionaste ningún extranjero. Ajusta N o selecciona manualmente.")
        st.stop()

    if len(seleccion) > n:
        st.warning(f"Seleccionaste {len(seleccion)} > N ({n}). Reduce la selección.")
        st.stop()

    # Registra asignaciones y bloquea columnas
    registros = []
    for ext in seleccion:
        score = float(scores_map.get(ext, df.loc[peruano, ext]))
        registros.append({
            "Pasada": st.session_state.pass_num,
            "Peruano": peruano,
            "Extranjero": ext,
            "Score": round(score, 4),
        })
    st.session_state.asignaciones.extend(registros)

    for ext in seleccion:
        if ext in st.session_state.disponibles:
            st.session_state.disponibles.remove(ext)

    # Avanza a la siguiente fila
    st.session_state.row_idx += 1
    st.rerun()

if omitir:
    st.session_state.row_idx += 1
    st.rerun()

# Vista rápida del estado actual
st.markdown("---")
c4, c5 = st.columns([2, 1])
with c4:
    st.write("**Asignaciones ya confirmadas:**")
    if asignaciones:
        st.dataframe(pd.DataFrame(asignaciones), use_container_width=True, height=250)
    else:
        st.caption("Aún no hay asignaciones confirmadas.")
with c5:
    st.write("**Extranjeros disponibles:**")
    st.write(len(disponibles))
