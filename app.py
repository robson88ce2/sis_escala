from datetime import datetime, timedelta
import os
import streamlit as st
import pandas as pd
from utils import (
    criar_tabelas, listar_plantonistas, cadastrar_plantonista, apagar_plantonista,
    listar_viaturas, cadastrar_viatura, apagar_viatura,
    listar_coordenadores, cadastrar_coordenador, apagar_coordenador,
    gerar_escala_manual, gerar_escala_automatica, apagar_escala,
    gerar_historico_excel_por_equipe, gerar_historico_pdf_por_equipe,
    safe_json_loads, safe_list_load,
    conectar,gerar_pdf_escala_por_equipe
)

# --- Configuração ---
st.set_page_config(page_title="Sistema de Escalas Extra", layout="wide")
criar_tabelas()
st.title("📋 Sistema de Escalas de Serviço Extra")

# Criar pasta de relatórios se não existir
os.makedirs("relatorios", exist_ok=True)

# --- Menu Principal ---
menu = st.sidebar.selectbox("Menu", ["Gerenciar", "Gerar Escala", "Histórico", "Dashboard"])


# --- Gerenciar ---
if menu == "Gerenciar":
    aba = st.sidebar.radio("Gerenciar:", ["Plantonistas", "Viaturas", "Coordenadores"])

    def listar_e_apagar(df, apagar_func, entidade):
        df["Apagar"] = False
        edit_df = st.data_editor(
            df,
            column_config={"Apagar": st.column_config.CheckboxColumn("🗑️", help="Marque para apagar")},
            use_container_width=True,
            hide_index=True
        )
        apagar_linhas = edit_df[edit_df["Apagar"] == True]
        if not apagar_linhas.empty:
            if st.button(f"⚠️ Apagar {entidade}(s) selecionados"):
                for _, row in apagar_linhas.iterrows():
                    apagar_func(row["id"])
                st.success(f"{entidade}(s) apagado(s)!")
                st.rerun()

    if aba == "Plantonistas":
        st.header("Cadastrar Plantonista")
        with st.form(key='form_plantonista'):
            nome = st.text_input("Nome")
            matricula = st.text_input("Matrícula")
            cpf = st.text_input("CPF")
            telefone = st.text_input("Telefone")
            enviar = st.form_submit_button("Cadastrar")
            if enviar:
                if not nome or not matricula:
                    st.warning("Nome e matrícula são obrigatórios.")
                else:
                    cadastrar_plantonista(nome, matricula, cpf, telefone)
                    st.success("Plantonista cadastrado com sucesso!")
        st.subheader("Lista de Plantonistas")
        listar_e_apagar(listar_plantonistas(), apagar_plantonista, "Plantonista")

    elif aba == "Viaturas":
        st.header("Cadastrar Viatura")
        with st.form(key='form_viatura'):
            placa = st.text_input("Placa")
            modelo = st.text_input("Modelo")
            enviar = st.form_submit_button("Cadastrar")
            if enviar:
                cadastrar_viatura(placa, modelo)
                st.success("Viatura cadastrada com sucesso!")
        st.subheader("Lista de Viaturas")
        listar_e_apagar(listar_viaturas(), apagar_viatura, "Viatura")

    elif aba == "Coordenadores":
        st.header("Cadastrar Coordenador")
        with st.form(key='form_coord'):
            nome = st.text_input("Nome")
            matricula = st.text_input("Matrícula")
            contato = st.text_input("Contato")
            enviar = st.form_submit_button("Cadastrar")
            if enviar:
                cadastrar_coordenador(nome, matricula, contato)
                st.success("Coordenador cadastrado com sucesso!")
        st.subheader("Lista de Coordenadores")
        listar_e_apagar(listar_coordenadores(), apagar_coordenador, "Coordenador")


# --- Gerar Escala ---
elif menu == "Gerar Escala":
    if st.button("📄 Gerar PDF das Escalas com Assinatura"):
        pdf_bytes = gerar_pdf_escala_por_equipe()
        st.download_button(
            label="⬇️ Baixar PDF",
            data=pdf_bytes,
            file_name="escalas_completas.pdf",
            mime="application/pdf"
        )
    st.info("O arquivo Word também foi salvo em 'relatorios/escala_completa.docx' para edição.")
    st.header("Gerar Escala")
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.text_input("Data Início (YYYY-MM-DD HH:MM)", datetime.now().strftime('%Y-%m-%d 16:00'))
        turno = st.text_input("Turno", "18h às 02h")
        vagas = st.number_input("Vagas Disponíveis", 1, 10, 3)
    with col2:
        data_fim = st.text_input("Data Fim (YYYY-MM-DD HH:MM)", (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d 02:00'))

    viaturas = listar_viaturas().to_dict('records')
    coordenadores = listar_coordenadores().to_dict('records')

    viatura = st.selectbox("Viatura", viaturas, format_func=lambda x: f"{x['placa']} ({x['modelo']})" if x else "Nenhuma")
    coordenador = st.selectbox("Coordenador", coordenadores, format_func=lambda x: f"{x['nome']} ({x['matricula']})" if x else "Nenhum")

    plantonistas = st.multiselect("Plantonistas", listar_plantonistas()['nome'].tolist())

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Gerar Escala Manual"):
            if not plantonistas:
                st.warning("Selecione pelo menos um plantonista.")
            else:
                gerar_escala_manual(data_inicio, data_fim, turno, vagas, plantonistas, viatura_id=viatura['id'], coordenador_id=coordenador['id'])
                st.success("Escala manual gerada!")
                st.rerun()
    with col2:
        if st.button("Gerar Escala Automática"):
            gerar_escala_automatica(data_inicio, data_fim, turno, vagas, viatura_id=viatura['id'], coordenador_id=coordenador['id'])
            st.success("Escala automática gerada!")
            st.rerun()


# --- Histórico ---
# --- Histórico ---
elif menu == "Histórico":
    st.header("Histórico de Escalas (Por Equipe)")
    df = pd.read_sql_query('SELECT * FROM escalas', conectar())
    df['equipe'] = df['plantonistas'].apply(safe_json_loads)
    df['Início'] = pd.to_datetime(df['data_inicio'])
    df['Fim'] = pd.to_datetime(df['data_fim'])

    # Filtro por data
    col1, col2 = st.columns(2)
    data_min = df['Início'].min()
    data_max = df['Fim'].max()
    filtro_inicio = col1.date_input("Data início (filtro)", data_min.date() if pd.notnull(data_min) else datetime.today())
    filtro_fim = col2.date_input("Data fim (filtro)", data_max.date() if pd.notnull(data_max) else datetime.today())

    filtrado = df[(df['Início'].dt.date >= filtro_inicio) & (df['Fim'].dt.date <= filtro_fim)]

    filtrado['Início'] = filtrado['Início'].dt.strftime('%d/%m/%Y %H:%M')
    filtrado['Fim'] = filtrado['Fim'].dt.strftime('%d/%m/%Y %H:%M')

    filtrado['Apagar'] = False
    edit = st.data_editor(
        filtrado[['id', 'Início', 'Fim', 'turno', 'vagas', 'equipe', 'Apagar']],
        column_config={'Apagar': st.column_config.CheckboxColumn('🗑️', help='Marque para apagar')},
        use_container_width=True,
        hide_index=True
    )
    
    # Apagar escalas
    deletar = edit[edit['Apagar']]
    if not deletar.empty and st.button("⚠️ Apagar Escalas Selecionadas"):
        for _, row in deletar.iterrows():
            apagar_escala(row['id'])
        st.success("Escalas apagadas!")
        st.rerun()

    # Exportações
    st.download_button("⬇️ Exportar CSV (Por Equipe)", data=filtrado.to_csv(index=False).encode('utf-8'), file_name='historico_equipes.csv', mime='text/csv')
    st.button("📊 Gerar Excel (Por Equipe)", on_click=gerar_historico_excel_por_equipe)

    # Selecionar escalas para gerar PDF
    ids_disponiveis = filtrado['id'].tolist()
    escalas_marcadas = st.multiselect("Selecione as escalas que deseja incluir no PDF:", ids_disponiveis)

    if st.button("📄 Gerar PDF das Escalas Selecionadas"):
        if not escalas_marcadas:
            st.warning("Você precisa selecionar pelo menos uma escala.")
        else:
            pdf_bytes = gerar_pdf_escala_por_equipe(ids=escalas_marcadas)
            st.download_button(
                label="⬇️ Baixar PDF",
                data=pdf_bytes,
                file_name="escalas_selecionadas.pdf",
                mime="application/pdf"
            )



# --- Dashboard ---
elif menu == "Dashboard":
    st.header("Dashboard")
    
    df = pd.read_sql_query('SELECT * FROM historico', conectar())
    df['plantonistas_lista'] = df['plantonistas'].apply(safe_list_load)
    df['horas_totais'] = df['horas_normais'] + df['horas_especiais']

    # Métricas globais
    st.metric("Horas Normais Total", df['horas_normais'].sum())
    st.metric("Horas Especiais Total", df['horas_especiais'].sum())
    st.metric("Horas Totais", df['horas_totais'].sum())

    # Gráfico geral
    st.bar_chart(df[['horas_normais', 'horas_especiais']])

    # Ranking dos plantonistas
    st.subheader("Ranking: Plantonistas com Mais Horas Totais")
    from collections import defaultdict

    horas_por_plantonista = defaultdict(lambda: {'normais': 0, 'especiais': 0})

    for _, row in df.iterrows():
        for nome in row['plantonistas_lista']:
            horas_por_plantonista[nome]['normais'] += row['horas_normais']
            horas_por_plantonista[nome]['especiais'] += row['horas_especiais']

    ranking_df = pd.DataFrame([
        {
            'Plantonista': nome,
            'Horas Normais': dados['normais'],
            'Horas Especiais': dados['especiais'],
            'Horas Totais': dados['normais'] + dados['especiais']
        }
        for nome, dados in horas_por_plantonista.items()
    ]).sort_values(by='Horas Totais', ascending=False)

    st.dataframe(ranking_df.reset_index(drop=True), use_container_width=True)

    # Filtro individual
    st.subheader("Filtrar Plantonista")
    todos = sorted(horas_por_plantonista.keys())
    escolhido = st.selectbox("Plantonista", todos)

    filtrado = df[df['plantonistas_lista'].apply(lambda l: escolhido in l)]
    if not filtrado.empty:
        st.metric("Normais", filtrado['horas_normais'].sum())
        st.metric("Especiais", filtrado['horas_especiais'].sum())
        st.metric("Totais", filtrado['horas_totais'].sum())
        st.bar_chart(filtrado[['horas_normais', 'horas_especiais']])
    else:
        st.write("Nenhum dado para este plantonista.")

