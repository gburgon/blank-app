"""
Dashboard OMU 2025 — Streamlit
Requisitos: pip install streamlit pandas plotly geopandas requests openpyxl
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import json

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================
st.set_page_config(
    page_title="OMU 2025 — Dashboard",
    page_icon="🏆",
    layout="wide",
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .metric-label { font-size: 13px; color: #888; }
    .metric-value { font-size: 28px; font-weight: 600; }
    .sidebar-title { font-size: 16px; font-weight: 600; margin-bottom: 0.5rem; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# CARREGAMENTO DOS DADOS
# ============================================================
@st.cache_data
def carregar_dados(fonte, sheet_id=None, arquivo=None):
    if fonte == "Google Sheets":
        url = f"https://docs.google.com/spreadsheets/d/1w5XuOrbl5XlOgV5pAt96Rw0zj-tGXlYe8P23ASnMGh0/edit?usp=sharing"
        abas = pd.read_excel(url, sheet_name=None)
    else:
        abas = pd.read_excel(arquivo, sheet_name=None)
    return abas


@st.cache_data
def processar_dados(abas):
    escolas       = abas["Escolas"]
    equipes       = abas["Equipes"]
    participantes = abas["Participantes"]

    # Juntar equipes com UF via escolas
    eq = equipes.merge(
        escolas[["Hash", "UF", "Cidade", "Região", "Tipo"]],
        left_on="Escola", right_on="Hash", how="left"
    )

    # Resumo por UF
    resumo = eq.groupby("UF").agg(
        total_equipes  = ("ID", "count"),
        equipes_final  = ("Final", "sum"),
        equipes_fem    = ("Fem", "sum"),
        premiadas      = ("Prem", lambda x: x.notna().sum()),
        ouro           = ("Prem", lambda x: (x == "Ouro").sum()),
        prata          = ("Prem", lambda x: (x == "Prata").sum()),
        bronze         = ("Prem", lambda x: (x == "Bronze").sum()),
        mencao         = ("Prem", lambda x: (x == "Menção").sum()),
        privadas       = ("Tipo Escola", lambda x: (x == "Privada").sum()),
        publicas       = ("Tipo Escola", lambda x: (x == "Pública").sum()),
    ).reset_index()

    resumo["tx_final"]   = (resumo["equipes_final"] / resumo["total_equipes"] * 100).round(1)
    resumo["tx_fem"]     = (resumo["equipes_fem"]   / resumo["total_equipes"] * 100).round(1)
    resumo["tx_privada"] = (resumo["privadas"]      / resumo["total_equipes"] * 100).round(1)
    resumo["tx_publica"] = (resumo["publicas"]      / resumo["total_equipes"] * 100).round(1)

    return eq, resumo, participantes


@st.cache_data
def carregar_geojson():
    url = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
    try:
        r = requests.get(url, timeout=10)
        geo = r.json()
        # Garantir que a propriedade de sigla esteja acessível
        for f in geo["features"]:
            if "sigla" not in f["properties"] and "SIGLA" in f["properties"]:
                f["properties"]["sigla"] = f["properties"]["SIGLA"]
        return geo
    except Exception:
        return None


# ============================================================
# SIDEBAR — FONTE DE DADOS E FILTROS
# ============================================================
with st.sidebar:
    st.title("⚙️ Configuração")

    fonte = st.radio("Fonte dos dados", ["Google Sheets", "Arquivo local"])

    if fonte == "Google Sheets":
        sheet_id = st.text_input(
            "ID da planilha",
            help="A parte longa da URL: docs.google.com/spreadsheets/d/**ID**/edit"
        )
        carregar = st.button("Carregar dados", type="primary")
        arquivo_up = None
    else:
        arquivo_up = st.file_uploader("Upload do arquivo .xlsx", type=["xlsx"])
        carregar = bool(arquivo_up)
        sheet_id = None

    st.divider()

    if (fonte == "Google Sheets" and sheet_id and carregar) or arquivo_up:
        try:
            abas = carregar_dados(fonte, sheet_id=sheet_id, arquivo=arquivo_up)
            eq, resumo, participantes = processar_dados(abas)
            dados_ok = True
        except Exception as e:
            st.error(f"Erro ao carregar: {e}")
            dados_ok = False
    else:
        dados_ok = False

    if dados_ok:
        st.markdown("### 🗂️ Filtros")

        categorias = ["Todas"] + sorted(
            [c for c in eq["Categoria"].dropna().unique() if c != "☒"]
        )
        cat_sel = st.selectbox("Categoria", categorias)

        tipos = ["Todos", "Privada", "Pública"]
        tipo_sel = st.selectbox("Tipo de escola", tipos)

        fases = st.multiselect(
            "Fase",
            ["Participaram", "Foram à final", "Premiadas"],
            default=["Participaram"]
        )


# ============================================================
# CONTEÚDO PRINCIPAL
# ============================================================
if not dados_ok:
    st.title("🏆 Dashboard OMU 2025")
    st.info("Configure a fonte de dados na barra lateral para começar.")
    st.stop()


# Filtrar equipes conforme seleção
eq_filtrado = eq.copy()
if cat_sel != "Todas":
    eq_filtrado = eq_filtrado[eq_filtrado["Categoria"] == cat_sel]
if tipo_sel != "Todos":
    eq_filtrado = eq_filtrado[eq_filtrado["Tipo Escola"] == tipo_sel]
if "Foram à final" in fases and "Premiadas" not in fases:
    eq_filtrado = eq_filtrado[eq_filtrado["Final"] == True]
if "Premiadas" in fases:
    eq_filtrado = eq_filtrado[eq_filtrado["Prem"].notna()]

# Recalcular resumo com filtros
resumo_f = eq_filtrado.groupby("UF").agg(
    total_equipes = ("ID", "count"),
    equipes_final = ("Final", "sum"),
    equipes_fem   = ("Fem", "sum"),
    premiadas     = ("Prem", lambda x: x.notna().sum()),
    privadas      = ("Tipo Escola", lambda x: (x == "Privada").sum()),
    publicas      = ("Tipo Escola", lambda x: (x == "Pública").sum()),
).reset_index()
resumo_f["tx_privada"] = (resumo_f["privadas"] / resumo_f["total_equipes"] * 100).round(1)


# ============================================================
# MÉTRICAS GERAIS
# ============================================================
st.title("🏆 OMU 2025 — Dashboard")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total de equipes",     f"{eq_filtrado['ID'].nunique():,}")
c2.metric("Estados participantes", f"{eq_filtrado['UF'].nunique()}")
c3.metric("Foram à final",        f"{eq_filtrado['Final'].sum():,}")
c4.metric("Premiadas",            f"{eq_filtrado['Prem'].notna().sum():,}")
c5.metric("Equipes femininas",    f"{eq_filtrado['Fem'].sum():,}")

st.divider()


# ============================================================
# MAPA + PAINEL LATERAL
# ============================================================
opcao_mapa = st.radio(
    "Visualizar no mapa:",
    ["Total de equipes", "Equipes premiadas", "Público vs Privado"],
    horizontal=True
)

geo = carregar_geojson()

col_mapa, col_painel = st.columns([2, 1])

with col_mapa:
    if geo is None:
        st.warning("Não foi possível carregar o GeoJSON. Verifique a conexão.")
    else:
        if opcao_mapa == "Total de equipes":
            cor_col, titulo_cor = "total_equipes", "Equipes"
            label_hover = "Total"
        elif opcao_mapa == "Equipes premiadas":
            cor_col, titulo_cor = "premiadas", "Premiadas"
            label_hover = "Premiadas"
        else:
            cor_col, titulo_cor = "tx_privada", "% Privadas"
            label_hover = "% Privadas"

        fig_mapa = px.choropleth(
            resumo_f,
            geojson=geo,
            locations="UF",
            featureidkey="properties.sigla",
            color=cor_col,
            color_continuous_scale="Blues",
            hover_name="UF",
            hover_data={
                "total_equipes": True,
                "premiadas": True,
                "tx_privada": True,
                cor_col: False,
            },
            labels={
                "total_equipes": "Total de equipes",
                "premiadas": "Premiadas",
                "tx_privada": "% Privadas",
            },
            title=f"{opcao_mapa} por estado"
        )

        fig_mapa.update_geos(
            fitbounds="locations",
            visible=False,
            bgcolor="rgba(0,0,0,0)"
        )
        fig_mapa.update_layout(
            margin={"r": 0, "t": 40, "l": 0, "b": 0},
            height=520,
            coloraxis_colorbar=dict(title=titulo_cor),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_mapa, use_container_width=True)
        st.caption("💡 Use o seletor abaixo para explorar um estado específico.")


# ============================================================
# PAINEL LATERAL — ANÁLISE POR ESTADO
# ============================================================
with col_painel:
    ufs_disponiveis = sorted(resumo_f["UF"].dropna().unique())
    uf_sel = st.selectbox("🔍 Selecione um estado", ["— escolha —"] + list(ufs_disponiveis))

    if uf_sel == "— escolha —":
        st.info("Selecione um estado para ver a análise detalhada.")
    else:
        eq_uf = eq_filtrado[eq_filtrado["UF"] == uf_sel]
        total_uf = len(eq_uf)

        st.markdown(f"### {uf_sel}")
        st.caption(f"{total_uf} equipes no filtro atual")

        m1, m2 = st.columns(2)
        m1.metric("Final",     f"{eq_uf['Final'].sum()}")
        m2.metric("Premiadas", f"{eq_uf['Prem'].notna().sum()}")

        m3, m4 = st.columns(2)
        m3.metric("Femininas", f"{eq_uf['Fem'].sum()}")
        m4.metric("Públicas",  f"{(eq_uf['Tipo Escola'] == 'Pública').sum()}")

        # Gráfico — Premiações
        prem_uf = eq_uf["Prem"].value_counts().reset_index()
        prem_uf.columns = ["Premiação", "Equipes"]
        ordem = ["Ouro", "Prata", "Bronze", "Menção"]
        cores = {"Ouro": "#f4c430", "Prata": "#aaa9ad", "Bronze": "#cd7f32", "Menção": "#7B68EE"}
        prem_uf = prem_uf[prem_uf["Premiação"].isin(ordem)]

        if not prem_uf.empty:
            fig_prem = px.bar(
                prem_uf, x="Premiação", y="Equipes",
                color="Premiação",
                color_discrete_map=cores,
                title="Premiações",
                category_orders={"Premiação": ordem},
            )
            fig_prem.update_layout(
                height=220, showlegend=False,
                margin={"t": 40, "b": 10, "l": 10, "r": 10},
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_prem, use_container_width=True)

        # Gráfico — Público vs Privado
        tipo_uf = eq_uf["Tipo Escola"].value_counts().reset_index()
        tipo_uf.columns = ["Tipo", "Equipes"]
        tipo_uf = tipo_uf[tipo_uf["Tipo"].isin(["Privada", "Pública"])]
        fig_tipo = px.pie(
            tipo_uf, names="Tipo", values="Equipes",
            color="Tipo",
            color_discrete_map={"Privada": "#4C78A8", "Pública": "#72B7B2"},
            title="Tipo de escola",
            hole=0.45,
        )
        fig_tipo.update_layout(
            height=220, showlegend=True,
            margin={"t": 40, "b": 10, "l": 10, "r": 10},
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_tipo, use_container_width=True)

        # Tabela de equipes
        with st.expander("📋 Ver equipes deste estado"):
            cols_tabela = ["Nome da Equipe", "Categoria", "Cidade", "Tipo Escola", "Final", "Prem"]
            cols_existentes = [c for c in cols_tabela if c in eq_uf.columns]
            tabela = eq_uf[cols_existentes].copy()
            tabela["Final"] = tabela["Final"].map({True: "✅", False: "—"})
            tabela["Prem"] = tabela["Prem"].fillna("—")
            tabela = tabela.rename(columns={
                "Nome da Equipe": "Equipe",
                "Tipo Escola": "Tipo",
                "Prem": "Premiação"
            })
            st.dataframe(tabela, use_container_width=True, hide_index=True)


# ============================================================
# SEÇÃO INFERIOR — ANÁLISES GERAIS
# ============================================================
st.divider()
st.subheader("📊 Análises gerais")

tab1, tab2, tab3 = st.tabs(["Ranking de estados", "Gênero", "Categorias"])

with tab1:
    top_n = st.slider("Top N estados", 5, 27, 10)
    top_uf = resumo_f.nlargest(top_n, "total_equipes")
    fig_rank = px.bar(
        top_uf, x="UF", y="total_equipes",
        color="premiadas",
        color_continuous_scale="Blues",
        labels={"total_equipes": "Equipes", "premiadas": "Premiadas", "UF": "Estado"},
        title=f"Top {top_n} estados por número de equipes"
    )
    fig_rank.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_rank, use_container_width=True)

with tab2:
    genero_geral = pd.DataFrame({
        "Gênero": ["Masculino", "Feminino", "Não informado"],
        "Participantes": [
            (participantes["Gênero"] == "Masculino").sum(),
            (participantes["Gênero"] == "Feminino").sum(),
            (participantes["Gênero"] == "Preferiu não responder").sum(),
        ]
    })
    fig_gen = px.pie(
        genero_geral, names="Gênero", values="Participantes",
        color="Gênero",
        color_discrete_map={"Masculino": "#4C78A8", "Feminino": "#E45756", "Não informado": "#aaa"},
        hole=0.45,
        title="Distribuição de gênero — participantes"
    )
    fig_gen.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_gen, use_container_width=True)

with tab3:
    cat_geral = eq_filtrado["Categoria"].value_counts().reset_index()
    cat_geral.columns = ["Categoria", "Equipes"]
    cat_geral = cat_geral[~cat_geral["Categoria"].isin(["☒"])]
    fig_cat = px.bar(
        cat_geral, x="Categoria", y="Equipes",
        color="Categoria",
        color_discrete_map={"Alfa": "#72B7B2", "Beta": "#4C78A8"},
        title="Equipes por categoria"
    )
    fig_cat.update_layout(
        height=350, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig_cat, use_container_width=True)
