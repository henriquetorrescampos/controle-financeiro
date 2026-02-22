import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Lapidar - Gestão Financeira",
    page_icon="assets/icon.ico",
    layout="wide")

def get_engine():
    db_url = st.secrets["connections"]["postgresql"]["url"]
    return create_engine(db_url)

engine = get_engine()

def init_db():
    with engine.connect() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS faturamentos (
                id SERIAL PRIMARY KEY, mes TEXT, convenio TEXT, valor FLOAT
            )'''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS custos (
                id SERIAL PRIMARY KEY, 
                mes TEXT, 
                aluguel FLOAT, energia FLOAT, agua FLOAT, 
                internet FLOAT, outros FLOAT, pessoal FLOAT,
                imposto_pago FLOAT
            )'''))
        conn.commit()

init_db()

st.title("Lapidar - Gestão Financeira")

mes_ref = st.selectbox("Selecione o Mês de Referência", 
                       ["Fev/2026", "Março/2026", "Abril/2026",
                        "Maio/2026", "Junho/2026", "Julho/2026",
                        "Agosto/2026", "Setembro/2026", "Outubro/2026",
                        "Novembro/2026", "Dezembro/2026"])

df_fat_existente = pd.read_sql(text("SELECT convenio, valor FROM faturamentos WHERE mes = :mes"), engine, params={"mes": mes_ref})
df_custos_existente = pd.read_sql(text("SELECT * FROM custos WHERE mes = :mes"), engine, params={"mes": mes_ref})

fat_map = dict(zip(df_fat_existente['convenio'], df_fat_existente['valor']))
c_existente = df_custos_existente.iloc[0] if not df_custos_existente.empty else None

with st.sidebar:
    st.header("📥 Lançamentos")
    st.image("assets/lapidar-logo-colorida.jpg", width=200)
    
    with st.expander("💸 Imposto e Pessoal", expanded=True):
        val_imposto = st.number_input("Valor do Imposto (R$)", min_value=0.0, step=10.0, 
                                      value=float(c_existente['imposto_pago']) if c_existente is not None else 0.0)
        val_pessoal = st.number_input("👨‍⚕️ Despesas com Pessoal", min_value=0.0, step=100.0,
                                      value=float(c_existente['pessoal']) if c_existente is not None else 0.0)
    
    with st.expander("📂 Custos Fixos"):
        val_aluguel = st.number_input("Aluguel", min_value=0.0, 
                                      value=float(c_existente['aluguel']) if c_existente is not None else 0.0)
        val_energia = st.number_input("Energia", min_value=0.0,
                                       value=float(c_existente['energia']) if c_existente is not None else 0.0)
        val_agua = st.number_input("Água", min_value=0.0,
                                    value=float(c_existente['agua']) if c_existente is not None else 0.0)
        val_internet = st.number_input("Internet", min_value=0.0,
                                        value=float(c_existente['internet']) if c_existente is not None else 0.0)
        val_outros = st.number_input("Demais Custos Fixos", min_value=0.0,
                                      value=float(c_existente['outros']) if c_existente is not None else 0.0)
    
    st.markdown("---")
    convenios = ["Ipasgo", "Iamesc", "Caixa", "SUS", "Particular"]
    fats = {}
    for conv in convenios:
        val_padrao = float(fat_map.get(conv, 0.0))
        fats[conv] = st.number_input(f"Fat. {conv}", min_value=0.0, value=val_padrao)

    if st.button("🚀 Salvar no Banco de Dados"):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM faturamentos WHERE mes = :mes"), {"mes": mes_ref})
            conn.execute(text("DELETE FROM custos WHERE mes = :mes"), {"mes": mes_ref})
            
            for conv, valor in fats.items():
                if valor > 0:
                    conn.execute(text("INSERT INTO faturamentos (mes, convenio, valor) VALUES (:mes, :conv, :val)"),
                                 {"mes": mes_ref, "conv": conv, "val": valor})
            
            conn.execute(text('''
                INSERT INTO custos (mes, aluguel, energia, agua, internet, outros, pessoal, imposto_pago) 
                VALUES (:mes, :alug, :ener, :agua, :net, :out, :pess, :imp)'''),
                {"mes": mes_ref, "alug": val_aluguel, "ener": val_energia, 
                 "agua": val_agua, "net": val_internet, "out": val_outros, "pess": val_pessoal, "imp": val_imposto})
        st.success(f"Dados de {mes_ref} salvos! Reiniciando dashboard...")
        st.rerun() # Força o app a recarregar para atualizar os gráficos


if not df_fat_existente.empty and not df_custos_existente.empty:
    total_bruto = df_fat_existente['valor'].sum()
    linha_c = df_custos_existente.iloc[0]
    
    gastos_fixos_pessoal = (linha_c['aluguel'] + linha_c['energia'] + linha_c['agua'] + 
                           linha_c['internet'] + linha_c['outros'] + linha_c['pessoal'])
    
    lucro_liquido = total_bruto - linha_c['imposto_pago'] - gastos_fixos_pessoal

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Faturamento Bruto", f"R$ {total_bruto:,.2f}")
    kpi2.metric("Imposto Pago", f"- R$ {linha_c['imposto_pago']:,.2f}")
    kpi3.metric("Custos Operacionais", f"R$ {gastos_fixos_pessoal:,.2f}")
    kpi4.metric("Lucro Líquido", f"R$ {lucro_liquido:,.2f}", f"{(lucro_liquido/total_bruto)*100:.1f}% margem")

    st.markdown("---")
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("Faturamento por Convênio")
        fig_pizza = px.pie(df_fat_existente, values='valor', names='convenio', hole=0.5,
                           color_discrete_sequence=px.colors.qualitative.Safe)
        st.plotly_chart(fig_pizza, use_container_width=True)

    with col_right:
        st.subheader("Detalhamento Mensal")
        resumo = {
            "Item": ["Faturamento", "Imposto", "Pessoal", "Fixos", "Lucro"],
            "Valor (R$)": [total_bruto, -linha_c['imposto_pago'], -linha_c['pessoal'], 
                           -(gastos_fixos_pessoal - linha_c['pessoal']), lucro_liquido]
        }
        st.dataframe(pd.DataFrame(resumo), hide_index=True)
else:
    st.info("Aguardando dados para o mês selecionado. Insira-os na barra lateral.")