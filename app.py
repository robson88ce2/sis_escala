from datetime import datetime, timedelta, time
import os
import streamlit as st
import pandas as pd
import json # Importar json para lidar com a coluna plantonistas na escala

from utils import (
    criar_tabelas, listar_plantonistas, cadastrar_plantonista, apagar_plantonista,
    listar_viaturas, cadastrar_viatura, apagar_viatura,
    listar_coordenadores, cadastrar_coordenador, apagar_coordenador,
    gerar_escala_manual, gerar_escala_automatica, apagar_escala,
    gerar_historico_excel_por_equipe, gerar_historico_pdf_por_equipe,
    safe_json_loads, safe_list_load,
    conectar, gerar_pdf_escala_por_equipe
)

# --- Funções auxiliares ---
def valida_cpf(cpf):
    # Se CPF for vazio, consideramos válido (opcional)
    if not cpf:
        return True
        
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11:
        return False
    
    # Algoritmo de validação simplificado
    if len(set(cpf)) == 1:
        return False
    
    # Verificação do primeiro dígito
    soma = 0
    for i in range(9):
        soma += int(cpf[i]) * (10 - i)
    resto = soma % 11
    if resto < 2:
        digito1 = 0
    else:
        digito1 = 11 - resto
    if digito1 != int(cpf[9]):
        return False
    
    # Verificação do segundo dígito
    soma = 0
    for i in range(10):
        soma += int(cpf[i]) * (11 - i)
    resto = soma % 11
    if resto < 2:
        digito2 = 0
    else:
        digito2 = 11 - resto
    if digito2 != int(cpf[10]):
        return False
    
    return True

def valida_telefone(telefone):
    # Se telefone for vazio, consideramos válido (opcional)
    if not telefone:
        return True
        
    telefone = ''.join(filter(str.isdigit, telefone))
    return len(telefone) >= 10 and len(telefone) <= 11

# Novas funções para editar registros
def atualizar_plantonista(id, nome, matricula, cpf, telefone):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE plantonistas SET nome = ?, matricula = ?, cpf = ?, telefone = ? WHERE id = ?',
        (nome, matricula, cpf, telefone, id)
    )
    conn.commit()
    conn.close()

def atualizar_viatura(id, placa, modelo):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE viaturas SET placa = ?, modelo = ? WHERE id = ?',
        (placa, modelo, id)
    )
    conn.commit()
    conn.close()

def atualizar_coordenador(id, nome, matricula, contato):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE coordenadores SET nome = ?, matricula = ?, contato = ? WHERE id = ?',
        (nome, matricula, contato, id)
    )
    conn.commit()
    conn.close()

def atualizar_escala(id, data_inicio, data_fim, turno, vagas, plantonistas, viatura_id, coordenador_id):
    conn = conectar()
    cursor = conn.cursor()
    plantonistas_json = json.dumps(plantonistas)
    cursor.execute(
        'UPDATE escalas SET data_inicio = ?, data_fim = ?, turno = ?, vagas = ?, plantonistas = ?, viatura_id = ?, coordenador_id = ? WHERE id = ?',
        (data_inicio, data_fim, turno, vagas, plantonistas_json, viatura_id, coordenador_id, id)
    )
    conn.commit()
    conn.close()

# Função com cache para melhorar o desempenho
@st.cache_data(ttl=600)  # Cache por 10 minutos
def listar_plantonistas_cached():
    return listar_plantonistas()

@st.cache_data(ttl=600)
def listar_viaturas_cached():
    return listar_viaturas()

@st.cache_data(ttl=600)
def listar_coordenadores_cached():
    return listar_coordenadores()

def obter_plantonista_por_id(id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM plantonistas WHERE id = ?', (id,))
    resultado = cursor.fetchone()
    conn.close()
    if resultado:
        return {
            "id": resultado[0],
            "nome": resultado[1],
            "matricula": resultado[2],
            "cpf": resultado[3],
            "telefone": resultado[4]
        }
    return None

def obter_viatura_por_id(id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM viaturas WHERE id = ?', (id,))
    resultado = cursor.fetchone()
    conn.close()
    if resultado:
        return {
            "id": resultado[0],
            "placa": resultado[1],
            "modelo": resultado[2]
        }
    return None

def obter_coordenador_por_id(id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM coordenadores WHERE id = ?', (id,))
    resultado = cursor.fetchone()
    conn.close()
    if resultado:
        return {
            "id": resultado[0],
            "nome": resultado[1],
            "matricula": resultado[2],
            "contato": resultado[3]
        }
    return None

def obter_escala_por_id(id):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM escalas WHERE id = ?', (id,))
    resultado = cursor.fetchone()
    conn.close()
    if resultado:
        return {
            "id": resultado[0],
            "data_inicio": resultado[1],
            "data_fim": resultado[2],
            "turno": resultado[3],
            "vagas": resultado[4],
            "plantonistas": json.loads(resultado[5]) if resultado[5] else [],
            "viatura_id": resultado[6],
            "coordenador_id": resultado[7]
        }
    return None


def exportar_relatorio_individual(plantonista_nome):
    conn = conectar()
    query = '''
    SELECT e.data_inicio, e.data_fim, e.turno, e.vagas 
    FROM escalas e
    WHERE JSON_EXTRACT(e.plantonistas, '$') LIKE ?
    ORDER BY e.data_inicio DESC
    '''
    busca = f'%{plantonista_nome}%'
    df = pd.read_sql_query(query, conn, params=[busca])
    
    # Calcular horas trabalhadas
    df['horas_trabalhadas'] = (pd.to_datetime(df['data_fim']) - 
                              pd.to_datetime(df['data_inicio'])).dt.total_seconds() / 3600
    
    return df

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
    
    def listar_e_apagar(df, apagar_func, entidade, editar_func=None):
        
        # Adiciona colunas de ação se não existirem (para evitar erro no rerun)
        if "Apagar" not in df.columns:
             df["Apagar"] = False
        if editar_func and "Editar" not in df.columns:
             df["Editar"] = False

        column_config = {"Apagar": st.column_config.CheckboxColumn("🗑️", help="Marque para apagar")}
        if editar_func:
             column_config["Editar"] = st.column_config.CheckboxColumn("✏️", help="Marque para editar")

        edit_df = st.data_editor(
            df,
            column_config=column_config,
            use_container_width=True,
            hide_index=True
        )
        
        # Processar exclusão
        apagar_linhas = edit_df[edit_df["Apagar"] == True]
        if not apagar_linhas.empty:
            confirmacao = st.checkbox(f"⚠️ Confirmar exclusão de {len(apagar_linhas)} {entidade}(s)?", key=f'confirm_delete_{entidade}')
            if st.button(f"Apagar {entidade}(s) selecionados") and confirmacao:
                for _, row in apagar_linhas.iterrows():
                    apagar_func(row["id"])
                st.success(f"{entidade}(s) apagado(s)!")
                st.cache_data.clear() # Limpa o cache após exclusão
                st.rerun()
            elif not confirmacao and st.button(f"Apagar {entidade}(s) selecionados", key=f'delete_btn_{entidade}'):
                st.warning("Por favor, confirme a exclusão.")
        
        # Processar edição
        if editar_func:
            editar_linhas = edit_df[edit_df["Editar"] == True]
            if not editar_linhas.empty:
                # Pega o ID da primeira linha marcada para edição (Streamlit só permite uma edição por vez)
                id_para_editar = editar_linhas.iloc[0]["id"]
                editar_func(id_para_editar) # Chama a função de edição com o ID

    # Inicializa o estado de edição se não existir
    if 'editando_plantonista_id' not in st.session_state:
        st.session_state['editando_plantonista_id'] = None
    if 'editando_viatura_id' not in st.session_state:
        st.session_state['editando_viatura_id'] = None
    if 'editando_coordenador_id' not in st.session_state:
        st.session_state['editando_coordenador_id'] = None


    if aba == "Plantonistas":
        st.header("Cadastrar Plantonista")
        
        # Verificar se estamos no modo de edição
        editando_id = st.session_state.get('editando_plantonista_id', None)
        plantonista_atual = None
        
        if editando_id:
            plantonista_atual = obter_plantonista_por_id(editando_id)
            if plantonista_atual:
                 st.info(f"Editando plantonista: {plantonista_atual['nome']}")
            else:
                 st.error("Plantonista não encontrado para edição.")
                 st.session_state.pop('editando_plantonista_id', None)
                 st.rerun()


        with st.form(key='form_plantonista'):
            nome = st.text_input("Nome", value=plantonista_atual['nome'] if plantonista_atual else "")
            matricula = st.text_input("Matrícula", value=plantonista_atual['matricula'] if plantonista_atual else "")
            cpf = st.text_input("CPF", value=plantonista_atual['cpf'] if plantonista_atual else "")
            telefone = st.text_input("Telefone", value=plantonista_atual['telefone'] if plantonista_atual else "")
            
            col_enviar, col_cancelar = st.columns(2)

            with col_enviar:
                if editando_id:
                    enviar = st.form_submit_button("Atualizar")
                else:
                    enviar = st.form_submit_button("Cadastrar")
            
            with col_cancelar:
                if editando_id:
                    cancelar = st.form_submit_button("Cancelar")
                else:
                    cancelar = False # Não há botão de cancelar no modo de cadastro

            if cancelar:
                st.session_state.pop('editando_plantonista_id', None)
                st.rerun()
                
            if enviar:
                if not nome or not matricula:
                    st.warning("Nome e matrícula são obrigatórios.")
                elif cpf and not valida_cpf(cpf): # Valida CPF apenas se preenchido
                    st.warning("CPF inválido!")
                elif telefone and not valida_telefone(telefone): # Valida Telefone apenas se preenchido
                    st.warning("Telefone inválido! Digite DDD + número.")
                else:
                    if editando_id:
                        atualizar_plantonista(editando_id, nome, matricula, cpf, telefone)
                        st.success("Plantonista atualizado com sucesso!")
                        st.session_state.pop('editando_plantonista_id', None)
                    else:
                        cadastrar_plantonista(nome, matricula, cpf, telefone)
                        st.success("Plantonista cadastrado com sucesso!")
                    # Limpar o cache para atualizar a lista
                    st.cache_data.clear()
                    st.rerun()
        
        st.subheader("Lista de Plantonistas")
        # Adicionando campo de busca
        filtro_plantonista = st.text_input("Filtrar plantonistas por nome:", key='filtro_plantonista_gerenciar')
        plantonistas_df = listar_plantonistas_cached()
        
        if filtro_plantonista:
            plantonistas_filtrados = plantonistas_df[plantonistas_df['nome'].str.contains(filtro_plantonista, case=False)]
        else:
            plantonistas_filtrados = plantonistas_df
        
        # Função para editar plantonista
        def editar_plantonista(id):
            st.session_state['editando_plantonista_id'] = id
            st.rerun()
            
        listar_e_apagar(plantonistas_filtrados, apagar_plantonista, "Plantonista", editar_plantonista)
    
    elif aba == "Viaturas":
        st.header("Cadastrar Viatura")
        
        # Verificar se estamos no modo de edição
        editando_id = st.session_state.get('editando_viatura_id', None)
        viatura_atual = None
        
        if editando_id:
            viatura_atual = obter_viatura_por_id(editando_id)
            if viatura_atual:
                st.info(f"Editando viatura: {viatura_atual['placa']} - {viatura_atual['modelo']}")
            else:
                st.error("Viatura não encontrada para edição.")
                st.session_state.pop('editando_viatura_id', None)
                st.rerun()
        
        with st.form(key='form_viatura'):
            placa = st.text_input("Placa", value=viatura_atual['placa'] if viatura_atual else "")
            modelo = st.text_input("Modelo", value=viatura_atual['modelo'] if viatura_atual else "")
            
            col_enviar, col_cancelar = st.columns(2)

            with col_enviar:
                if editando_id:
                    enviar = st.form_submit_button("Atualizar")
                else:
                    enviar = st.form_submit_button("Cadastrar")
            
            with col_cancelar:
                if editando_id:
                    cancelar = st.form_submit_button("Cancelar")
                else:
                    cancelar = False
            
            if cancelar:
                st.session_state.pop('editando_viatura_id', None)
                st.rerun()
                
            if enviar:
                if not placa or not modelo:
                    st.warning("Placa e modelo são obrigatórios.")
                else:
                    if editando_id:
                        atualizar_viatura(editando_id, placa, modelo)
                        st.success("Viatura atualizada com sucesso!")
                        st.session_state.pop('editando_viatura_id', None)
                    else:
                        cadastrar_viatura(placa, modelo)
                        st.success("Viatura cadastrada com sucesso!")
                    # Limpar o cache para atualizar a lista
                    st.cache_data.clear()
                    st.rerun()
        
        st.subheader("Lista de Viaturas")
        
        # Função para editar viatura
        def editar_viatura(id):
            st.session_state['editando_viatura_id'] = id
            st.rerun()
            
        listar_e_apagar(listar_viaturas_cached(), apagar_viatura, "Viatura", editar_viatura)
    
    elif aba == "Coordenadores":
        st.header("Cadastrar Coordenador")
        
        # Verificar se estamos no modo de edição
        editando_id = st.session_state.get('editando_coordenador_id', None)
        coordenador_atual = None
        
        if editando_id:
            coordenador_atual = obter_coordenador_por_id(editando_id)
            if coordenador_atual:
                st.info(f"Editando coordenador: {coordenador_atual['nome']}")
            else:
                st.error("Coordenador não encontrado para edição.")
                st.session_state.pop('editando_coordenador_id', None)
                st.rerun()
        
        with st.form(key='form_coord'):
            nome = st.text_input("Nome", value=coordenador_atual['nome'] if coordenador_atual else "")
            matricula = st.text_input("Matrícula", value=coordenador_atual['matricula'] if coordenador_atual else "")
            contato = st.text_input("Contato", value=coordenador_atual['contato'] if coordenador_atual else "")
            
            col_enviar, col_cancelar = st.columns(2)

            with col_enviar:
                if editando_id:
                    enviar = st.form_submit_button("Atualizar")
                else:
                    enviar = st.form_submit_button("Cadastrar")
            
            with col_cancelar:
                if editando_id:
                    cancelar = st.form_submit_button("Cancelar")
                else:
                    cancelar = False
            
            if cancelar:
                st.session_state.pop('editando_coordenador_id', None)
                st.rerun()
                
            if enviar:
                if not nome or not matricula:
                    st.warning("Nome e matrícula são obrigatórios.")
                else:
                    if editando_id:
                        atualizar_coordenador(editando_id, nome, matricula, contato)
                        st.success("Coordenador atualizado com sucesso!")
                        st.session_state.pop('editando_coordenador_id', None)
                    else:
                        cadastrar_coordenador(nome, matricula, contato)
                        st.success("Coordenador cadastrado com sucesso!")
                    # Limpar o cache para atualizar a lista
                    st.cache_data.clear()
                    st.rerun()
        
        st.subheader("Lista de Coordenadores")
        
        # Função para editar coordenador
        def editar_coordenador(id):
            st.session_state['editando_coordenador_id'] = id
            st.rerun()
            
        listar_e_apagar(listar_coordenadores_cached(), apagar_coordenador, "Coordenador", editar_coordenador)

# --- Gerar Escala ---
elif menu == "Gerar Escala":
    # Verificar se estamos no modo de edição de escala
    editando_escala_id = st.session_state.get('editando_escala_id', None)
    escala_atual = None
    
    if editando_escala_id:
        escala_atual = obter_escala_por_id(editando_escala_id)
        if escala_atual:
            st.info(f"Editando escala de {escala_atual['data_inicio']} a {escala_atual['data_fim']}")
        else:
            st.error("Escala não encontrada para edição.")
            st.session_state.pop('editando_escala_id', None)
            st.rerun()

    if st.button("📄 Gerar PDF das Escalas com Assinatura", key='gerar_pdf_assinatura'):
        pdf_bytes = gerar_pdf_escala_por_equipe()
        st.download_button(
            label="⬇️ Baixar PDF",
            data=pdf_bytes,
            file_name="escalas_completas.pdf",
            mime="application/pdf",
            key='download_pdf_assinatura'
        )
    st.info("O arquivo Word também foi salvo em 'relatorios/escala_completa.docx' para edição.")
    
    st.header("Gerar Escala")
    
    # Organizar em tabs para separar manual e automática (ou edição)
    if not editando_escala_id:
        tab1, tab2 = st.tabs(["Escala Manual", "Escala Automática"])
    else:
        tab1, tab2 = st.tabs(["Editar Escala", "Escala Automática"]) # Muda o nome da tab se estiver editando
    
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            if editando_escala_id:
                data_inicio_value = datetime.strptime(escala_atual['data_inicio'], '%Y-%m-%d %H:%M')
                data_inicio_date = st.date_input("Data de Início", data_inicio_value.date(), key='edit_data_inicio_date')
                hora_inicio = st.time_input("Hora de Início", data_inicio_value.time(), key='edit_hora_inicio')
                turno = st.text_input("Turno", escala_atual['turno'], key='edit_turno')
            else:
                data_inicio_date = st.date_input("Data de Início", datetime.now(), key='new_data_inicio_date')
                hora_inicio = st.time_input("Hora de Início", time(16, 0), key='new_hora_inicio')
                turno = st.text_input("Turno", "18h às 02h", key='new_turno')
        with col2:
            if editando_escala_id:
                data_fim_value = datetime.strptime(escala_atual['data_fim'], '%Y-%m-%d %H:%M')
                data_fim_date = st.date_input("Data de Fim", data_fim_value.date(), key='edit_data_fim_date')
                hora_fim = st.time_input("Hora de Fim", data_fim_value.time(), key='edit_hora_fim')
                vagas = st.number_input("Vagas Disponíveis", 1, 10, escala_atual['vagas'], key='edit_vagas')
            else:
                data_fim_date = st.date_input("Data de Fim", datetime.now() + timedelta(days=1), key='new_data_fim_date')
                hora_fim = st.time_input("Hora de Fim", time(2, 0), key='new_hora_fim')
                vagas = st.number_input("Vagas Disponíveis", 1, 10, 3, key='new_vagas')
        
        data_inicio = datetime.combine(data_inicio_date, hora_inicio).strftime('%Y-%m-%d %H:%M')
        data_fim = datetime.combine(data_fim_date, hora_fim).strftime('%Y-%m-%d %H:%M')
        
        viaturas = listar_viaturas_cached().to_dict('records')
        coordenadores = listar_coordenadores_cached().to_dict('records')
        
        # Encontrar o índice da viatura/coordenador selecionado para preencher o selectbox
        viatura_index = 0
        if editando_escala_id and escala_atual['viatura_id']:
             viatura_ids = [v['id'] for v in viaturas]
             try:
                 viatura_index = viatura_ids.index(escala_atual['viatura_id'])
             except ValueError:
                 viatura_index = 0 # Seleciona o primeiro se não encontrar
        
        viatura = st.selectbox(
            "Viatura", 
            viaturas, 
            index=viatura_index,
            format_func=lambda x: f"{x['placa']} ({x['modelo']})" if x else "Nenhuma",
            key='select_viatura_escala'
        )
        
        coord_index = 0
        if editando_escala_id and escala_atual['coordenador_id']:
            coord_ids = [c['id'] for c in coordenadores]
            try:
                coord_index = coord_ids.index(escala_atual['coordenador_id'])
            except ValueError:
                coord_index = 0 # Seleciona o primeiro se não encontrar

        coordenador = st.selectbox(
            "Coordenador", 
            coordenadores, 
            index=coord_index,
            format_func=lambda x: f"{x['nome']} ({x['matricula']})" if x else "Nenhum",
            key='select_coordenador_escala'
        )
        
        # Adicionando campo de busca para plantonistas
        filtro_plantonista_escala = st.text_input("Filtrar plantonistas:", key='filtro_plantonista_escala')
        plantonistas_df = listar_plantonistas_cached()
        
        if filtro_plantonista_escala:
            plantonistas_filtrados = plantonistas_df[plantonistas_df['nome'].str.contains(filtro_plantonista_escala, case=False)]['nome'].tolist()
        else:
            plantonistas_filtrados = plantonistas_df['nome'].tolist()
        
        # Se estiver editando, preencher os plantonistas selecionados
        default_plantonistas = []
        if editando_escala_id:
            default_plantonistas = escala_atual['plantonistas']
            
        plantonistas = st.multiselect("Plantonistas", plantonistas_filtrados, default=default_plantonistas, key='multiselect_plantonistas')
        
        if editando_escala_id:
            col_atualizar, col_cancelar_edicao = st.columns(2)
            with col_atualizar:
                if st.button("Atualizar Escala"):
                    if not plantonistas:
                        st.warning("Selecione pelo menos um plantonista.")
                    else:
                        atualizar_escala(
                            editando_escala_id, 
                            data_inicio, 
                            data_fim, 
                            turno, 
                            vagas, 
                            plantonistas, 
                            viatura['id'], 
                            coordenador['id']
                        )
                        st.success("Escala atualizada com sucesso!")
                        st.session_state.pop('editando_escala_id', None)
                        st.cache_data.clear() # Limpa o cache após atualização
                        st.rerun()
            with col_cancelar_edicao:
                if st.button("Cancelar Edição"):
                    st.session_state.pop('editando_escala_id', None)
                    st.rerun()
        else:
            if st.button("Gerar Escala Manual"):
                if not plantonistas:
                    st.warning("Selecione pelo menos um plantonista.")
                else:
                    gerar_escala_manual(data_inicio, data_fim, turno, vagas, plantonistas, viatura_id=viatura['id'], coordenador_id=coordenador['id'])
                    st.success("Escala manual gerada!")
                    st.cache_data.clear() # Limpa o cache após geração
                    st.rerun()
    
    # A tab de Escala Automática só aparece se não estiver editando uma escala
    if not editando_escala_id:
        with tab2:
            col1, col2 = st.columns(2)
            with col1:
                data_inicio_auto_date = st.date_input("Data de Início (Auto)", datetime.now(), key='auto_data_inicio_date')
                hora_inicio_auto = st.time_input("Hora de Início (Auto)", time(16, 0), key='auto_hora_inicio')
                turno_auto = st.text_input("Turno (Auto)", "18h às 02h", key='auto_turno')
            with col2:
                data_fim_auto_date = st.date_input("Data de Fim (Auto)", datetime.now() + timedelta(days=1), key='auto_data_fim_date')
                hora_fim_auto = st.time_input("Hora de Fim (Auto)", time(2, 0), key='auto_hora_fim')
                vagas_auto = st.number_input("Vagas Disponíveis (Auto)", 1, 10, 3, key='auto_vagas')
            
            data_inicio_auto = datetime.combine(data_inicio_auto_date, hora_inicio_auto).strftime('%Y-%m-%d %H:%M')
            data_fim_auto = datetime.combine(data_fim_auto_date, hora_fim_auto).strftime('%Y-%m-%d %H:%M')
            
            viatura_auto = st.selectbox("Viatura (Auto)", viaturas, format_func=lambda x: f"{x['placa']} ({x['modelo']})" if x else "Nenhuma", key='select_viatura_auto')
            coordenador_auto = st.selectbox("Coordenador (Auto)", coordenadores, format_func=lambda x: f"{x['nome']} ({x['matricula']})" if x else "Nenhum", key='select_coordenador_auto')
            
            if st.button("Gerar Escala Automática"):
                gerar_escala_automatica(data_inicio_auto, data_fim_auto, turno_auto, vagas_auto, viatura_id=viatura_auto['id'], coordenador_id=coordenador_auto['id'])
                st.success("Escala automática gerada!")
                st.cache_data.clear() # Limpa o cache após geração
                st.rerun()

# --- Histórico ---
elif menu == "Histórico":
    st.header("Histórico de Escalas (Por Equipe)")
    
    conn = conectar()
    # Corrigido: Usando data_inicio para filtrar o histórico, assumindo que historico tem essa coluna
    # Se a coluna for diferente (ex: data_servico), ajuste aqui
    df = pd.read_sql_query('SELECT * FROM escalas', conn) # Carrega escalas para mostrar histórico
    conn.close()

    df['equipe'] = df['plantonistas'].apply(safe_json_loads)
    df['Início'] = pd.to_datetime(df['data_inicio'])
    df['Fim'] = pd.to_datetime(df['data_fim'])
    
    # Filtro por data
    col1, col2 = st.columns(2)
    data_min = df['Início'].min()
    data_max = df['Fim'].max()
    
    # Usando chaves únicas para os date_input
    filtro_inicio = col1.date_input("Data início (filtro)", data_min.date() if pd.notnull(data_min) else datetime.today(), key='hist_filtro_inicio')
    filtro_fim = col2.date_input("Data fim (filtro)", data_max.date() if pd.notnull(data_max) else datetime.today(), key='hist_filtro_fim')
    
    # Filtrando o DataFrame carregado
    filtrado = df[(df['Início'].dt.date >= filtro_inicio) & (df['Fim'].dt.date <= filtro_fim)].copy() # Use .copy() para evitar SettingWithCopyWarning
    
    filtrado['Início'] = filtrado['Início'].dt.strftime('%d/%m/%Y %H:%M')
    filtrado['Fim'] = filtrado['Fim'].dt.strftime('%d/%m/%Y %H:%M')
    
    # Adiciona colunas de ação se não existirem
    if "Apagar" not in filtrado.columns:
        filtrado["Apagar"] = False
    if "Editar" not in filtrado.columns:
        filtrado["Editar"] = False

    edit = st.data_editor(
        filtrado[['id', 'Início', 'Fim', 'turno', 'vagas', 'equipe', 'Apagar', 'Editar']],
        column_config={
            'Apagar': st.column_config.CheckboxColumn('🗑️', help='Marque para apagar'),
            'Editar': st.column_config.CheckboxColumn('✏️', help='Marque para editar')
        },
        use_container_width=True,
        hide_index=True,
        key='historico_data_editor' # Chave única para o data_editor
    )
    
    # Editar escala
    editar_linhas = edit[edit['Editar']]
    if not editar_linhas.empty:
        # Pega o ID da primeira linha marcada para edição
        id_para_editar = editar_linhas.iloc[0]["id"]
        st.session_state['editando_escala_id'] = id_para_editar
        st.rerun()
    
    # Apagar escalas
    deletar = edit[edit['Apagar']]
    if not deletar.empty:
        confirmacao = st.checkbox("⚠️ Confirmar exclusão das escalas selecionadas?", key='confirm_delete_escala_hist')
        if st.button("Apagar Escalas Selecionadas", key='delete_btn_escala_hist') and confirmacao:
            for _, row in deletar.iterrows():
                apagar_escala(row['id'])
            st.success("Escalas apagadas!")
            st.cache_data.clear() # Limpa o cache após exclusão
            st.rerun()
        elif not confirmacao and st.button("Apagar Escalas Selecionadas", key='delete_btn_escala_hist_no_confirm'):
            st.warning("Por favor, confirme a exclusão.")
    
    # Exportações
    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button("⬇️ Exportar CSV (Por Equipe)", 
                          data=filtrado.to_csv(index=False).encode('utf-8'), 
                          file_name='historico_equipes.csv', 
                          mime='text/csv',
                          key='download_csv_hist')
    with col2:
        st.button("📊 Gerar Excel (Por Equipe)", on_click=gerar_historico_excel_por_equipe, key='gerar_excel_hist')
    
    # Relatório individual
    with col3:
        # Pega a lista de plantonistas das escalas filtradas
        plantonistas_filtrados_list = sorted(list(set([p for equipe in filtrado['equipe'] for p in equipe if p])))
        
        if plantonistas_filtrados_list:
            st.subheader("Relatório Individual")
            plantonista_selecionado = st.selectbox("Selecione o plantonista", plantonistas_filtrados_list, key='select_plantonista_relatorio')
            
            if st.button("Gerar Relatório Individual", key='gerar_relatorio_individual_btn'):
                 relatorio = exportar_relatorio_individual(plantonista_selecionado)
                 st.write(f"Relatório para {plantonista_selecionado}:")
                 st.dataframe(relatorio, use_container_width=True)
                 st.download_button("⬇️ Baixar Relatório Individual", 
                                   data=relatorio.to_csv(index=False).encode('utf-8'),
                                   file_name=f"relatorio_{plantonista_selecionado}.csv",
                                   mime="text/csv",
                                   key='download_relatorio_individual')
        else:
            st.info("Nenhuma escala encontrada no período para gerar relatório individual.")

    
    # Selecionar escalas para gerar PDF
    st.subheader("Gerar PDF de Escalas Selecionadas")
    ids_disponiveis = filtrado['id'].tolist()
    escalas_marcadas = st.multiselect("Selecione as escalas que deseja incluir no PDF:", ids_disponiveis, key='select_escalas_pdf')
    
    if st.button("📄 Gerar PDF das Escalas Selecionadas", key='gerar_pdf_selecionadas_btn'):
        if not escalas_marcadas:
            st.warning("Você precisa selecionar pelo menos uma escala.")
        else:
            pdf_bytes = gerar_pdf_escala_por_equipe(ids=escalas_marcadas)
            st.download_button(
                label="⬇️ Baixar PDF",
                data=pdf_bytes,
                file_name="escalas_selecionadas.pdf",
                mime="application/pdf",
                key='download_pdf_selecionadas'
            )

# --- Dashboard ---
elif menu == "Dashboard":
    st.header("Dashboard")
    
    # Adicionar filtro por período
    col1, col2 = st.columns(2)
    with col1:
        data_inicio_filtro = st.date_input("Período: Data inicial", datetime.now() - timedelta(days=30), key='dashboard_filtro_inicio')
    with col2:
        data_fim_filtro = st.date_input("Período: Data final", datetime.now(), key='dashboard_filtro_fim')
    
    # Filtrar dados pelo período
    conn = conectar()
    # Corrigido: Usando data_inicio para filtrar o histórico
    # Se a coluna for diferente (ex: data_servico), ajuste aqui
    df = pd.read_sql_query(
        'SELECT * FROM historico WHERE data_inicio BETWEEN ? AND ?', # <-- CORREÇÃO AQUI
        conn, 
        params=[data_inicio_filtro.strftime('%Y-%m-%d'), data_fim_filtro.strftime('%Y-%m-%d')]
    )
    conn.close()

    df['plantonistas_lista'] = df['plantonistas'].apply(safe_list_load)
    df['horas_totais'] = df['horas_normais'] + df['horas_especiais']
    
    # Métricas globais em cards lado a lado
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Horas Normais Total", f"{df['horas_normais'].sum():.1f}h")
    with col2:
        st.metric("Horas Especiais Total", f"{df['horas_especiais'].sum():.1f}h")
    with col3:
        st.metric("Horas Totais", f"{df['horas_totais'].sum():.1f}h")
    
    # Gráfico geral
    st.subheader("Distribuição de Horas no Período")
    if not df.empty:
        st.bar_chart(df[['horas_normais', 'horas_especiais']])
    else:
        st.info("Nenhum dado de histórico no período selecionado.")

    # Ranking dos plantonistas
    st.subheader("Ranking: Plantonistas com Mais Horas Totais no Período")
    from collections import defaultdict
    horas_por_plantonista = defaultdict(lambda: {'normais': 0, 'especiais': 0})
    
    for _, row in df.iterrows():
        for nome in row['plantonistas_lista']:
            horas_por_plantonista[nome]['normais'] += row['horas_normais']
            horas_por_plantonista[nome]['especiais'] += row['horas_especiais']
    
    if horas_por_plantonista:
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
        
        # Exportar ranking
        st.download_button("⬇️ Exportar Ranking", 
                           data=ranking_df.to_csv(index=False).encode('utf-8'),
                           file_name="ranking_plantonistas.csv",
                           mime="text/csv",
                           key='download_ranking')
    else:
        st.info("Nenhum dado de plantonista no período selecionado.")

    
    # Filtro individual
    st.subheader("Filtrar Plantonista Individualmente")
    todos = sorted(horas_por_plantonista.keys())
    
    # Adicionar campo de busca para plantonistas
    filtro_plantonista_dashboard = st.text_input("Buscar plantonista:", key='filtro_plantonista_dashboard')
    if filtro_plantonista_dashboard:
        todos_filtrados = [p for p in todos if filtro_plantonista_dashboard.lower() in p.lower()]
    else:
        todos_filtrados = todos
    
    if todos_filtrados:
        escolhido = st.selectbox("Plantonista", todos_filtrados, key='select_plantonista_dashboard')
    
        filtrado_individual = df[df['plantonistas_lista'].apply(lambda l: escolhido in l)]
        if not filtrado_individual.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Normais", f"{filtrado_individual['horas_normais'].sum():.1f}h")
            with col2:
                st.metric("Especiais", f"{filtrado_individual['horas_especiais'].sum():.1f}h")
            with col3:
                st.metric("Totais", f"{filtrado_individual['horas_totais'].sum():.1f}h")
                
            st.subheader(f"Distribuição de horas - {escolhido} no Período")
            st.bar_chart(filtrado_individual[['horas_normais', 'horas_especiais']])
            
            # Histórico detalhado
            st.subheader("Histórico Detalhado no Período")
            detalhes = filtrado_individual[['data_inicio', 'data_fim', 'horas_normais', 'horas_especiais', 'horas_totais']] # Usando data_inicio/data_fim
            detalhes = detalhes.sort_values(by='data_inicio', ascending=False)
            st.dataframe(detalhes, use_container_width=True)
        else:
            st.write("Nenhum dado para este plantonista no período selecionado.")
    else:
        st.info("Nenhum plantonista encontrado no período selecionado.")
