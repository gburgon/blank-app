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
    page_title="OMU 2025 — Dashboard Planilhão",
    layout="wide",
)

def estilizar_fig(fig):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#faf2b2",
        font=dict(color="black"),
        title_font=dict(color="black"),
        legend_font=dict(color="black"),
        xaxis=dict(
            gridcolor="#faf2b2",
            zerolinecolor="#faf2b2",
            tickfont=dict(color="black"),
            title_font=dict(color="black")
        ),
        yaxis=dict(
            gridcolor="#faf2b2",
            zerolinecolor="#faf2b2",
            tickfont=dict(color="black"),
            title_font=dict(color="black")
        )
    )
    return fig


st.markdown("""
<style>
    header[data-testid="stHeader"] {
        height: 100px;
        background-color: #facf61 !important;
    }
    .stApp { 
        background-color: #fcf7cf; 
    }

    /* Logo OMU à esquerda */
    header[data-testid="stHeader"]::before {
        content: "";
        display: block;
        background-image: url("https://www.olimpiada.ime.unicamp.br/elementos_visuais/logos/logo-omu-completo.png");
        background-repeat: no-repeat;
        background-position: left center;
        background-size: contain;
        height: 90px;
        width: 180px;
        margin: 5px 0 0 16px;
    }

    /* Faixa decorativa à direita do logo */
    header[data-testid="stHeader"]::after {
        content: "";
        position: absolute;
        top: 0;
        right: 0;
        height: 100px;
        width: calc(50% - 210px);
        background-image: url("https://www.olimpiada.ime.unicamp.br/elementos_visuais/logos/faixa-exemplo.svg");
        background-repeat: no-repeat;
        background-position: center;
        background-size: cover;
        pointer-events: none;
    }

    /* Botões do st.radio maiores */
    div[role="radiogroup"] label {
        font-size: 1.25rem !important;
        padding: 10px 22px !important;
        border-radius: 8px !important;
        cursor: pointer;
    }
    div[role="radiogroup"] label:hover {
        background-color: #f4c430 !important;
    }
    div[role="radiogroup"] {
        gap: 12px !important;
        display: flex;
        flex-wrap: wrap;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# CARREGAMENTO DOS DADOS
# ============================================================
@st.cache_data
def carregar_dados(fonte, sheet_id=None, arquivo=None):
    if fonte == "Google Sheets":
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        abas = pd.read_excel(url, sheet_name=None)
    else:
        abas = pd.read_excel(arquivo, sheet_name=None)
    return abas


@st.cache_data
def processar_dados(abas):
    escolas       = abas["Escolas"]
    equipes       = abas["Equipes"]
    participantes = abas["Participantes"]

    eq = equipes.merge(
        escolas[["Hash", "UF", "Cidade", "Região", "Tipo"]],
        left_on="Escola", right_on="Hash", how="left"
    )

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
        for f in geo["features"]:
            if "sigla" not in f["properties"] and "SIGLA" in f["properties"]:
                f["properties"]["sigla"] = f["properties"]["SIGLA"]
        return geo
    except Exception:
        return None


# ============================================================
# INICIALIZAÇÃO DE VARIÁVEIS GLOBAIS
# ============================================================
eq = None
resumo = None
participantes = None
abas = None
dados_ok = False

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
        carregar = False
        sheet_id = None

    st.divider()

    if (fonte == "Google Sheets" and sheet_id and carregar) or (fonte == "Arquivo local" and arquivo_up):
        try:
            abas = carregar_dados(fonte, sheet_id=sheet_id, arquivo=arquivo_up)
            eq, resumo, participantes = processar_dados(abas)
            dados_ok = True
        except Exception as e:
            st.error(f"Erro ao carregar: {e}")
            dados_ok = False

    if dados_ok and eq is not None:
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
    else:
        cat_sel = "Todas"
        tipo_sel = "Todos"
        fases = ["Participaram"]


# ============================================================
# CONTEÚDO PRINCIPAL
# ============================================================
if not dados_ok or eq is None:
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
resumo_f["tx_privada"] = (resumo_f["privadas"]      / resumo_f["total_equipes"] * 100).round(1)
resumo_f["tx_final"]   = (resumo_f["equipes_final"] / resumo_f["total_equipes"] * 100).round(1)
resumo_f["tx_fem"]     = (resumo_f["equipes_fem"]   / resumo_f["total_equipes"] * 100).round(1)


# ============================================================
# MÉTRICAS GERAIS
# ============================================================
st.title("OMU 2025 - Dashboard Planilhão")

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

col_mapa, col_painel = st.columns([3.5, 1])

with col_mapa:
    if geo is None:
        st.warning("Não foi possível carregar o GeoJSON. Verifique a conexão.")
    else:
        if opcao_mapa == "Total de equipes":
            cor_col, titulo_cor = "total_equipes", "Equipes"
        elif opcao_mapa == "Equipes premiadas":
            cor_col, titulo_cor = "premiadas", "Premiadas"
        else:
            cor_col, titulo_cor = "tx_privada", "% Privadas"

        fig_mapa = px.choropleth(
            resumo_f,
            geojson=geo,
            locations="UF",
            featureidkey="properties.sigla",
            color=cor_col,
            color_continuous_scale="Pinkyl",
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
        fig_mapa.update_traces(
            marker_line_width=0.2,
            marker_line_color="black"
        )
        fig_mapa.update_layout(
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            height=1000,
            width=200,
            coloraxis_colorbar=dict(title=titulo_cor, thickness=20, len=0.8),
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
                height=320, showlegend=False,
                margin={"t": 40, "b": 10, "l": 10, "r": 10},
                paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(estilizar_fig(fig_prem), use_container_width=True)

        # Gráfico — Público vs Privado
        tipo_uf = eq_uf["Tipo Escola"].value_counts().reset_index()
        tipo_uf.columns = ["Tipo", "Equipes"]
        tipo_uf = tipo_uf[tipo_uf["Tipo"].isin(["Privada", "Pública"])]
        fig_tipo = px.pie(
            tipo_uf, names="Tipo", values="Equipes",
            color="Tipo",
            color_discrete_map={"Privada": "#f89eda", "Pública": "#3856f8"},
            title="Tipo de escola",
            hole=0.6,
        )
        fig_tipo.update_layout(
            height=320, showlegend=True,
            margin={"t": 40, "b": 10, "l": 10, "r": 10},
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(estilizar_fig(fig_tipo), use_container_width=True)

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

# Preparar dados de notas (usado em múltiplas abas)
notas_df = abas["Notas"].copy()
notas_df["nota_final"] = pd.to_numeric(notas_df["nota_final"], errors="coerce")
eq_notas = eq_filtrado.merge(notas_df[["Equipe", "nota_final"]], left_on="ID", right_on="Equipe", how="left")

# Mapa de regiões
regioes_map = {
    1.0: "Norte", 2.0: "Nordeste I", 3.0: "Nordeste II",
    4.0: "Centro-Oeste", 5.0: "Sudeste I", 6.0: "Sudeste II",
    7.0: "Sudeste III", 8.0: "Sul I", 9.0: "Sul II", 10.0: "Sul III"
}

st.divider()
st.subheader("📊 Análises gerais")

tab1, tab2, tab3 = st.tabs(["🏅 Ranking de estados", "👥 Gênero", "📚 Categorias"])

# ============================================================
# TAB 1 — RANKING DE ESTADOS
# ============================================================
with tab1:
    top_n = st.slider("Top N estados", 5, 27, 10)

    col_r1, col_r2 = st.columns(2)

    with col_r1:
        top_uf = resumo_f.nlargest(top_n, "total_equipes")[["UF", "total_equipes", "equipes_final", "premiadas"]].copy()

        fig_rank = go.Figure()
        fig_rank.add_trace(go.Bar(
            name="Premiadas", x=top_uf["UF"], y=top_uf["premiadas"],
            marker_color="#f4c430",
        ))
        fig_rank.add_trace(go.Bar(
            name="Final (não premiadas)", x=top_uf["UF"],
            y=(top_uf["equipes_final"] - top_uf["premiadas"]).clip(lower=0),
            marker_color="#4C78A8",
        ))
        fig_rank.add_trace(go.Bar(
            name="Não chegaram à final", x=top_uf["UF"],
            y=(top_uf["total_equipes"] - top_uf["equipes_final"]).clip(lower=0),
            marker_color="#d0cfc8",
        ))
        fig_rank.update_layout(
            barmode="stack",
            height=420,
            title=f"Top {top_n} estados — funil de participação",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin={"t": 60, "b": 40, "l": 40, "r": 10},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#faf2b2",
        )
        st.plotly_chart(estilizar_fig(fig_rank), use_container_width=True)

    with col_r2:
        resumo_taxa = resumo_f[resumo_f["total_equipes"] >= 5].copy()
        resumo_taxa = resumo_taxa.nlargest(top_n, "tx_final")   # <- segue o mesmo N
        fig_taxa = px.bar(
            resumo_taxa, x="tx_final", y="UF", orientation="h",
            color="tx_final", color_continuous_scale="Greens",
            labels={"tx_final": "% na final", "UF": "Estado"},
            title=f"Taxa de classificação à final — top {top_n} (mín. 5 equipes)",
            text="tx_final",
        )
        fig_taxa.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_taxa.update_layout(
            height=420,
            showlegend=False,
            margin={"t": 60, "b": 40, "l": 40, "r": 60},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#faf2b2",
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(estilizar_fig(fig_taxa), use_container_width=True)

    # Scatter nota média vs volume
    nota_uf = eq_notas.groupby("UF").agg(
        total=("ID", "count"),
        nota_media=("nota_final", "mean"),
        premiadas=("Prem", lambda x: x.notna().sum()),
    ).reset_index()
    nota_uf = nota_uf[nota_uf["total"] >= 5]
    nota_uf["nota_media"] = nota_uf["nota_media"].round(2)

    fig_scatter = px.scatter(
        nota_uf, x="total", y="nota_media",
        size="premiadas", color="nota_media",
        color_continuous_scale="RdYlGn",
        text="UF",
        labels={"total": "Total de equipes", "nota_media": "Nota média", "premiadas": "Premiadas"},
        title="Nota média vs volume de equipes por estado",
        size_max=35,
    )
    fig_scatter.update_traces(textposition="top center")
    fig_scatter.update_layout(
        height=420,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#faf2b2",
        margin={"t": 50, "b": 40, "l": 40, "r": 20},
    )
    st.plotly_chart(estilizar_fig(fig_scatter), use_container_width=True)


# ============================================================
# TAB 2 — GÊNERO
# ============================================================
with tab2:
    # Dados de gênero geral vs finalistas
    p_filtrado = participantes[participantes["Equipe"].isin(eq_filtrado["ID"])]

    gen_geral  = p_filtrado["Gênero"].value_counts().rename("Geral")
    gen_final  = p_filtrado[p_filtrado["Final"] == True]["Gênero"].value_counts().rename("Finalistas")
    gen_comp   = pd.concat([gen_geral, gen_final], axis=1).fillna(0).reset_index()
    gen_comp.columns = ["Gênero", "Geral", "Finalistas"]
    gen_comp = gen_comp[gen_comp["Gênero"] != "Preferiu não responder"]
    gen_comp["% Geral"]      = (gen_comp["Geral"]      / gen_comp["Geral"].sum()      * 100).round(1)
    gen_comp["% Finalistas"] = (gen_comp["Finalistas"] / gen_comp["Finalistas"].sum() * 100).round(1)

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        # Barras lado a lado: geral vs finalistas
        fig_gen_comp = go.Figure()
        cores_gen = {"Masculino": "#4C78A8", "Feminino": "#E45756"}
        for _, row in gen_comp.iterrows():
            cor = cores_gen.get(row["Gênero"], "#aaa")
            fig_gen_comp.add_trace(go.Bar(
                name=row["Gênero"],
                x=["Todos os participantes", "Finalistas"],
                y=[row["% Geral"], row["% Finalistas"]],
                marker_color=cor,
                text=[f"{row['% Geral']}%", f"{row['% Finalistas']}%"],
                textposition="outside",
            ))
        fig_gen_comp.update_layout(
            barmode="group", height=380,
            title="Participação por gênero: geral vs finalistas",
            yaxis=dict(title="% dos participantes", range=[0, 100]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin={"t": 60, "b": 10},
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#faf2b2",
        )
        st.plotly_chart(estilizar_fig(fig_gen_comp), use_container_width=True)

    with col_g2:
        # Equipes femininas vs mistas vs masculinas por categoria
        def classificar_equipe(row):
            if row["Fem"] == True:
                return "100% Feminina"
            return "Mista / Masculina"

        eq_gen = eq_filtrado[eq_filtrado["Categoria"].isin(["Alfa", "Beta"])].copy()
        eq_gen["Tipo Equipe"] = eq_gen.apply(classificar_equipe, axis=1)
        eq_gen_cat = eq_gen.groupby(["Categoria", "Tipo Equipe"]).size().reset_index(name="Equipes")

        fig_fem_cat = px.bar(
            eq_gen_cat, x="Categoria", y="Equipes",
            color_discrete_map={"100% Feminina": "#E45756", "Mista / Masculina": "#4C78A8"},
            barmode="stack",
            title="Equipes femininas por categoria",
            text_auto=True,
        )
        fig_fem_cat.update_layout(
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin={"t": 60, "b": 10},
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#faf2b2",
        )
        st.plotly_chart(estilizar_fig(fig_fem_cat), use_container_width=True)

    # Gênero por estado (top 10 estados com mais participantes femininos)
    p_uf = p_filtrado.merge(
        eq_filtrado[["ID", "UF"]].rename(columns={"ID": "Equipe"}),
        on="Equipe", how="left"
    )
    fem_uf = p_uf[p_uf["Gênero"] == "Feminino"].groupby("UF").size().reset_index(name="Feminino")
    total_uf_p = p_uf.groupby("UF").size().reset_index(name="Total")
    fem_uf = fem_uf.merge(total_uf_p, on="UF")
    fem_uf["% Feminino"] = (fem_uf["Feminino"] / fem_uf["Total"] * 100).round(1)
    fem_uf = fem_uf.nlargest(15, "% Feminino")

    fig_fem_uf = px.bar(
        fem_uf, x="UF", y="% Feminino",
        color="% Feminino", color_continuous_scale="RdPu",
        text="% Feminino",
        title="% de participantes femininas por estado (top 15)",
        labels={"% Feminino": "% feminino"},
    )
    fig_fem_uf.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_fem_uf.update_layout(
        height=350, showlegend=False,
        margin={"t": 50, "b": 10, "r": 20},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#faf2b2",
    )
    st.plotly_chart(estilizar_fig(fig_fem_uf), use_container_width=True)


# ============================================================
# TAB 3 — CATEGORIAS
# ============================================================
with tab3:
    eq_cat = eq_notas[eq_notas["Categoria"].isin(["Alfa", "Beta"])].copy()

    col_c1, col_c2 = st.columns(2)

    with col_c1:
        # Funil: participaram → final → premiadas por categoria
        funil_cat = eq_cat.groupby("Categoria").agg(
            Total=("ID", "count"),
            Final=("Final", "sum"),
            Premiadas=("Prem", lambda x: x.notna().sum()),
        ).reset_index()

        fig_funil = go.Figure()
        cores_cat = {"Alfa": "#72B7B2", "Beta": "#4C78A8"}
        etapas = ["Total", "Final", "Premiadas"]
        for _, row in funil_cat.iterrows():
            fig_funil.add_trace(go.Bar(
                name=row["Categoria"],
                x=etapas,
                y=[row["Total"], row["Final"], row["Premiadas"]],
                marker_color=cores_cat[row["Categoria"]],
                text=[row["Total"], row["Final"], row["Premiadas"]],
                textposition="outside",
            ))
        fig_funil.update_layout(
            barmode="group", height=380,
            title="Funil por categoria: participação → final → premiação",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin={"t": 60, "b": 10},
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#faf2b2",
        )
        st.plotly_chart(estilizar_fig(fig_funil), use_container_width=True)

    with col_c2:
        # Distribuição de notas por categoria — box plot
        eq_cat_notas = eq_cat[eq_cat["nota_final"] > 0]
        fig_box = px.box(
            eq_cat_notas, x="Categoria", y="nota_final",
            color="Categoria",
            color_discrete_map=cores_cat,
            points="outliers",
            title="Distribuição de notas finais por categoria",
            labels={"nota_final": "Nota final"},
        )
        fig_box.update_layout(
            height=380, showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#faf2b2",
        )
        st.plotly_chart(estilizar_fig(fig_box), use_container_width=True)

    # Público vs privado por categoria com taxa de premiação
    pub_priv_cat = eq_cat.groupby(["Categoria", "Tipo Escola"]).agg(
        Total=("ID", "count"),
        Premiadas=("Prem", lambda x: x.notna().sum()),
        Nota_media=("nota_final", "mean"),
    ).reset_index()
    pub_priv_cat = pub_priv_cat[pub_priv_cat["Tipo Escola"].isin(["Pública", "Privada"])]
    pub_priv_cat["Taxa premiação (%)"] = (pub_priv_cat["Premiadas"] / pub_priv_cat["Total"] * 100).round(2)
    pub_priv_cat["Nota média"] = pub_priv_cat["Nota_media"].round(2)

    col_c3, col_c4 = st.columns(2)
    with col_c3:
        fig_pp = px.bar(
            pub_priv_cat, x="Categoria", y="Total",
            color_discrete_map={"Privada": "#4C78A8", "Pública": "#72B7B2"},
            text_auto=True,
            title="Equipes por categoria e tipo de escola",
        )
        fig_pp.update_layout(
            height=320,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin={"t": 60, "b": 10},
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#faf2b2",
        )
        st.plotly_chart(estilizar_fig(fig_pp), use_container_width=True)

    with col_c4:
        fig_taxa_pp = px.bar(
            pub_priv_cat, x="Categoria", y="Taxa premiação (%)",
            barmode="group",
            color_discrete_map={"Privada": "#4C78A8", "Pública": "#72B7B2"},
            text="Taxa premiação (%)",
            title="Taxa de premiação: pública vs privada",
        )
        fig_taxa_pp.update_traces(texttemplate="%{text}%", textposition="outside")
        fig_taxa_pp.update_layout(
            height=320,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin={"t": 60, "b": 10, "r": 20},
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#faf2b2",
        )
        st.plotly_chart(estilizar_fig(fig_taxa_pp), use_container_width=True)