import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# --- CONFIGURAÇÃO DA CONEXÃO ---
# No deploy, o Streamlit busca essa URL em .streamlit/secrets.toml
# Para teste local, você pode substituir pela sua string de conexão
def get_engine():
    db_url = st.secrets["connections"]["postgresql"]["url"]
    return create_engine(db_url)

engine = get_engine()

# --- FUNÇÕES DE BANCO DE DADOS ---
def init_db():
    with engine.connect() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS faturamentos (
                id SERIAL PRIMARY KEY, 
                mes TEXT, 
                convenio TEXT, 
                valor FLOAT
            )'''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS custos (
                id SERIAL PRIMARY KEY, 
                mes TEXT, 
                fixos FLOAT, 
                pessoal FLOAT
            )'''))
        conn.commit()

init_db()

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Clínica Pro - Financeiro", layout="wide")
st.title("🏥 Gestão Financeira Lapidar")

mes_ref = st.selectbox("Selecione o Mês de Referência", 
                       ["Fev/2026", "Março/2026", "Abril/2026",
                        "Maio/2026", "Junho/2026", "Julho/2026",
                        "Agosto/2026", "Setembro/2026", "Outubro/2026",
                        "Novembro/2026", "Dezembro/2026"])

# Sidebar para inputs
with st.sidebar:
    st.header("📥 Lançamentos")
    c_fixos = st.number_input("Custos Fixos", min_value=0.0)
    c_pessoal = st.number_input("Custos Pessoal", min_value=0.0)
    
    st.markdown("---")
    convenios = ["Ipasgo", "Iamesc", "Caixa", "SUS", "Particular"]
    fats = {conv: st.number_input(f"Fat. {conv}", min_value=0.0) for conv in convenios}

    if st.button("🚀 Salvar no Banco de Dados"):
        with engine.begin() as conn:
            # Limpa dados do mês para evitar duplicados
            conn.execute(text("DELETE FROM faturamentos WHERE mes = :mes"), {"mes": mes_ref})
            conn.execute(text("DELETE FROM custos WHERE mes = :mes"), {"mes": mes_ref})
            
            # Insere novos faturamentos
            for conv, valor in fats.items():
                if valor > 0:
                    conn.execute(text("INSERT INTO faturamentos (mes, convenio, valor) VALUES (:mes, :conv, :val)"),
                                 {"mes": mes_ref, "conv": conv, "val": valor})
            
            # Insere custos
            conn.execute(text("INSERT INTO custos (mes, fixos, pessoal) VALUES (:mes, :f, :p)"),
                         {"mes": mes_ref, "f": c_fixos, "p": c_pessoal})
        st.success("Dados sincronizados com o PostgreSQL!")

# --- LEITURA E DASHBOARD ---
df_fat = pd.read_sql(text("SELECT convenio, valor FROM faturamentos WHERE mes = :mes"), engine, params={"mes": mes_ref})
df_custos = pd.read_sql(text("SELECT fixos, pessoal FROM custos WHERE mes = :mes"), engine, params={"mes": mes_ref})

if not df_fat.empty and not df_custos.empty:
    total_bruto = df_fat['valor'].sum()
    gastos_totais = df_custos['fixos'].iloc[0] + df_custos['pessoal'].iloc[0]
    imposto = total_bruto * 0.06
    lucro = total_bruto - imposto - gastos_totais

    # KPIs
    c1, c2, c3 = st.columns(3)
    c1.metric("Receita Bruta", f"R$ {total_bruto:,.2f}")
    c2.metric("Despesas Totais", f"R$ {gastos_totais:,.2f}")
    c3.metric("Lucro Líquido", f"R$ {lucro:,.2f}", delta=f"{(lucro/total_bruto)*100:.1f}% de margem")

    st.bar_chart(df_fat.set_index('convenio'))
else:
    st.info("Aguardando dados para este mês...")