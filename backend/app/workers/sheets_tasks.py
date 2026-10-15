import logging
import psycopg2
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from psycopg2.extras import execute_values
import hashlib
import time
import datetime
import re # Importar re globalmente se usado em clean_payment_methods

from app.database.db import DB_CONFIG

# Importe a instância celery_app do seu projeto
# AJUSTE O CAMINHO CONFORME SUA ESTRUTURA DE PROJETO
from app.workers.celery_app import celery_app

# Configuração do Logger
# Configure o logging no seu aplicativo principal ou aqui
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# CONFIGURAÇÃO GOOGLE SHEETS
# -----------------------------------------------------------------------------
# AJUSTE O CAMINHO CONFORME SUA ESTRUTURA DE PROJETO
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "backend/arquivos/googlesheets.json")
SPREADSHEET_ID = "1k8L7RsFHH2t6-B2BvaQ8ltNwJ1SVNANVEiZhmkHa_48"
RANGE_HOME = "HOME!A:P"      # A:P => 16 colunas
RANGE_CONTRATOS = "CONTRATOS!A:N"  # A:N => 14 colunas
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# -----------------------------------------------------------------------------
# FUNÇÃO DE LIMPEZA/PADRONIZAÇÃO DO MÉTODO DE PAGAMENTO (Sem alterações)
# -----------------------------------------------------------------------------
def clean_payment_methods(text: str) -> str:
    """
    Limpa e padroniza métodos de pagamento.
    Retorna string vazia ou um dos nomes padronizados.
    """
    if pd.isna(text) or text is None:
        return ''

    text_upper = str(text).upper().strip() # Garante que é string

    # Possíveis prefixos administrativos que queremos remover
    admin_prefixes = [
        r'^REC ODC\s*-?\s*', r'^REC CRED\s*-?\s*', r'^REC ADESÃO\s*-?\s*',
        r'^REC TX ADESÃO\s*-?\s*', r'^VENDA\s*-?\s*', r'^MANUT ORTO\s*-?\s*',
        r'^MAN ORTO\s*-?\s*', r'^BAIXA AUDITORIA\s*-?\s*',
    ]
    for pat in admin_prefixes:
        text_upper = re.sub(pat, '', text_upper)

    # Remove sufixos do tipo NI-XX
    text_upper = re.sub(r'NI-\d+', '', text_upper)

    # Limpa espaços múltiplos ou traços
    text_upper = re.sub(r'\s+', ' ', text_upper)
    text_upper = text_upper.strip('- ')

    # REGRA VINDI: Se contém VINDI, retorna VINDI
    if re.search(r'\bVINDI\b', text_upper):
        return 'VINDI'

    # Dicionário de métodos conhecidos (match exato após limpeza)
    payment_methods = {
        'AMIL': ['AMIL'], 'AUDITORIA AMIL': ['AUDITORIA AMIL'], 'BOLETO': ['BOLETO'],
        'BRASIL CARD': ['BRASIL CARD'], 'CAPIM': ['CAPIM'],
        'CARTAO CREDITO': ['CARTAO CREDITO', 'CARTÃO CRÉDITO', 'CARTÃO DE CRÉDITO'],
        'CARTAO DEBITO': ['CARTAO DEBITO', 'CARTÃO DÉBITO', 'CARTÃO DE DÉBITO'],
        'CARTAO CREDZ': ['CARTAO CREDZ', 'CREDZ'], 'DEPOSITO': ['DEPOSITO'],
        'DINHEIRO': ['DINHEIRO', 'DINHE'], 'DRCASH': ['DRCASH', 'DR CASH', 'DR.CASH'],
        'KONSIGA': ['KONSIGA'], 'LOSANGO': ['LOSANGO'],
        'PARCELA MAIS': ['PARCELA MAIS', 'PARCELAMAIS'], 'PIX': ['PIX'],
        'PRIMAVIDA': ['PRIMAVIDA'], 'SANTANDER': ['SANTANDER'],
        'TAXA DE ADESAO': ['TAXA DE ADESAO', 'TAXA ADESAO'],
        'TRANSF. BANCARIA': ['TRANSF BANCARIA', 'TRANSF. BANCARIA', 'TRANSFERENCIA', 'TRANSFERÊNCIA'],
    }
    for standard_name, variations in payment_methods.items():
        if text_upper in variations:
            return standard_name

    # Tenta match por palavra-chave (aproximação)
    keywords = {
        'BOLETO': ['BOLETO'], 'CARTAO CREDITO': ['CREDITO', 'CRÉDITO', 'CRED'],
        'CARTAO DEBITO': ['DEBITO', 'DÉBITO', 'DEB'], 'DINHEIRO': ['DINHEIRO'], 'PIX': ['PIX']
    }
    for method, keys in keywords.items():
        for key in keys:
            if re.search(rf'\b{key}\b', text_upper):
                return method

    # Se nada foi encontrado, retorna o texto original "limpo"
    # Pode ser útil retornar '' ou um valor padrão como 'OUTROS' aqui?
    return text_upper

# -----------------------------------------------------------------------------
# FUNÇÃO DE CONEXÃO COM BANCO (Sem alterações)
# -----------------------------------------------------------------------------
def connect_db():
    """ Conecta no PostgreSQL e retorna (conn, cursor). """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        logger.debug("Conexão com o banco de dados estabelecida.")
        return conn, cur
    except psycopg2.Error as e:
        logger.exception(f"Erro ao conectar ao banco de dados: {e}")
        raise # Re-levanta a exceção para a task Celery saber que falhou

# -----------------------------------------------------------------------------
# FUNÇÕES DE GERENCIAMENTO DE LOCK NO BANCO (Sem alterações)
# -----------------------------------------------------------------------------
def acquire_db_lock(conn, cur, task_name, worker_id, expire_seconds=3500):
    """
    Tenta adquirir um lock no banco de dados. Retorna True se obtido.
    """
    try:
        now = datetime.datetime.now(datetime.timezone.utc) # Use UTC
        # Limpa locks expirados ANTES de tentar adquirir
        cur.execute("""
            DELETE FROM public.sheets_task_locks
            WHERE expires_at < %s
        """, (now,))
        conn.commit() # Commit a limpeza de locks expirados

        # Tenta obter o lock
        locked_at = now
        expires_at = now + datetime.timedelta(seconds=expire_seconds)

        cur.execute("""
            INSERT INTO public.sheets_task_locks (task_name, locked_at, locked_by, expires_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (task_name) DO NOTHING
        """, (task_name, locked_at, worker_id, expires_at))

        # Verifica se inseriu (obteve o lock)
        if cur.rowcount > 0:
            conn.commit()
            logger.info(f"[acquire_db_lock] Lock obtido para '{task_name}' por '{worker_id}'")
            return True
        else:
            # Lock não obtido, verifica quem o detém (apenas para log)
            cur.execute("""
                SELECT locked_by, locked_at, expires_at
                FROM public.sheets_task_locks
                WHERE task_name = %s
            """, (task_name,))
            lock_info = cur.fetchone()
            if lock_info:
                other_worker, lock_time, expiration = lock_info
                logger.warning(f"[acquire_db_lock] Lock para '{task_name}' já existe, detido por '{other_worker}' desde {lock_time}, expira em {expiration}")
            else:
                # Deveria ter info se o insert falhou por conflito, mas pode ter sido deletado entre o insert e o select
                 logger.warning(f"[acquire_db_lock] Lock para '{task_name}' não pôde ser adquirido, mas não foi encontrado lock ativo (possível race condition ou lock expirado e limpo).")
            conn.commit() # Commit mesmo se não obteve o lock (pode ter feito a limpeza)
            return False

    except psycopg2.Error as e:
        logger.exception(f"[acquire_db_lock] Erro ao tentar obter lock '{task_name}': {e}")
        conn.rollback()
        return False
    except Exception as e:
        logger.exception(f"[acquire_db_lock] Erro inesperado ao obter lock '{task_name}': {e}")
        conn.rollback()
        return False


def release_db_lock(conn, cur, task_name, worker_id):
    """ Libera um lock no banco de dados. """
    try:
        cur.execute("""
            DELETE FROM public.sheets_task_locks
            WHERE task_name = %s AND locked_by = %s
        """, (task_name, worker_id))

        if cur.rowcount > 0:
            logger.info(f"[release_db_lock] Lock liberado para '{task_name}' por '{worker_id}'")
        else:
            # Isso pode acontecer se o lock expirou e foi limpo por outra task
            logger.warning(f"[release_db_lock] Lock não encontrado ou já liberado para '{task_name}' pelo worker '{worker_id}'")
        conn.commit()
        return True

    except psycopg2.Error as e:
        logger.error(f"[release_db_lock] Erro ao liberar lock '{task_name}': {e}")
        conn.rollback()
        return False
    except Exception as e:
        logger.exception(f"[release_db_lock] Erro inesperado ao liberar lock '{task_name}': {e}")
        conn.rollback()
        return False

# -----------------------------------------------------------------------------
# FUNÇÃO PARA CARREGAR DADOS DO GOOGLE SHEETS (Sem alterações)
# -----------------------------------------------------------------------------
def load_sheet_data() -> pd.DataFrame | None:
    """
    Lê as abas HOME e CONTRATOS do Google Sheets, unifica colunas,
    aplica clean_payment_methods e retorna um DataFrame final ou None em caso de erro.
    """
    logger.info("[load_sheet_data] Iniciando leitura do Google Sheets...")
    try:
        credentials = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
        )
        service = build("sheets", "v4", credentials=credentials)
        sheet = service.spreadsheets()

        # Leitura da Aba HOME
        logger.debug(f"Lendo range: {RANGE_HOME}")
        home_result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_HOME).execute()
        values_home = home_result.get("values", [])
        df_home = pd.DataFrame()
        if values_home and len(values_home) > 1: # Precisa ter cabeçalho + dados
            df_home = pd.DataFrame(values_home[1:], columns=values_home[0])
            df_home["SISTEMA"] = "Clínico"
            logger.info(f"[load_sheet_data] {len(df_home)} linhas lidas da aba HOME.")
            # Renomear e garantir colunas - HOME
            rename_map_home = {"CNPJ_CPF": "CPF"} # Apenas o que muda
            df_home.columns = [c.upper().strip() for c in df_home.columns]
            df_home = df_home.rename(columns=rename_map_home)
        else:
             logger.warning(f"[load_sheet_data] Nenhum dado encontrado ou apenas cabeçalho na aba HOME ({RANGE_HOME}).")


        # Leitura da Aba CONTRATOS
        logger.debug(f"Lendo range: {RANGE_CONTRATOS}")
        contratos_result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_CONTRATOS).execute()
        values_contratos = contratos_result.get("values", [])
        df_contratos = pd.DataFrame()
        if values_contratos and len(values_contratos) > 1:
            df_contratos = pd.DataFrame(values_contratos[1:], columns=values_contratos[0])
            df_contratos["SISTEMA"] = "Contratos"
            logger.info(f"[load_sheet_data] {len(df_contratos)} linhas lidas da aba CONTRATOS.")
            # Renomear e garantir colunas - CONTRATOS
            rename_map_contratos = {} # Nenhuma renomeação explícita necessária aqui
            df_contratos.columns = [c.upper().strip() for c in df_contratos.columns]
            df_contratos = df_contratos.rename(columns=rename_map_contratos)
        else:
             logger.warning(f"[load_sheet_data] Nenhum dado encontrado ou apenas cabeçalho na aba CONTRATOS ({RANGE_CONTRATOS}).")


        # Lista completa de colunas esperadas no DataFrame final (antes do hash)
        # Baseado nas colunas de HOME e CONTRATOS + Sistema + Metodo Pagamento
        expected_cols = [
            "LANCTO", "NOME", "DATA", "TIPO", "VALOR", "DOCUMENTO", "CPF", # CPF vem de HOME (era CNPJ_CPF)
            "HORA", "FONE1", "FONE2", "NOME_CRD013", "CATEGORIA", "UNIDADE",
            "MES", "TERMINAL", "USUARIO", "SISTEMA", "CODIGO", # CODIGO vem de CONTRATOS
            "METODO_PAGAMENTO" # Será gerada
        ]

        # Garantir colunas ausentes em cada DF antes de concatenar
        for col in expected_cols:
             if col != "METODO_PAGAMENTO": # Metodo Pagamento é gerado depois
                 if col not in df_home.columns and not df_home.empty:
                     df_home[col] = None # Ou "" se preferir string vazia
                 if col not in df_contratos.columns and not df_contratos.empty:
                     df_contratos[col] = None # Ou ""

        # Concatenar os DataFrames
        if not df_home.empty or not df_contratos.empty:
            df_final = pd.concat([df_home, df_contratos], ignore_index=True)
            logger.info(f"[load_sheet_data] DataFrames concatenados. Total de linhas: {len(df_final)}")
        else:
             logger.warning("[load_sheet_data] Ambas as abas (HOME, CONTRATOS) estão vazias ou não retornaram dados.")
             return pd.DataFrame() # Retorna DF vazio se não há dados

        # Limpeza e Geração de Colunas
        # Preenche NaNs com string vazia para evitar erros na limpeza/hash
        df_final = df_final.fillna('')

        # Aplica limpeza no método de pagamento
        # Certifique-se que NOME_CRD013 existe antes de aplicar
        if "NOME_CRD013" in df_final.columns:
             logger.info("[load_sheet_data] Aplicando limpeza de método de pagamento...")
             df_final["METODO_PAGAMENTO"] = df_final["NOME_CRD013"].apply(clean_payment_methods)
        else:
             logger.warning("[load_sheet_data] Coluna 'NOME_CRD013' não encontrada para gerar 'METODO_PAGAMENTO'.")
             df_final["METODO_PAGAMENTO"] = '' # Cria a coluna vazia

        # Seleciona e reordena apenas as colunas esperadas para consistência
        # Garante que mesmo que a planilha tenha colunas extras, elas sejam ignoradas aqui
        final_expected_cols = [col for col in expected_cols if col in df_final.columns] # Pega as que realmente existem no DF
        df_final = df_final[final_expected_cols]


        logger.info(f"[load_sheet_data] Leitura e pré-processamento concluídos. {len(df_final)} linhas no DataFrame final.")
        return df_final

    except Exception as e:
        logger.exception(f"[load_sheet_data] Erro ao ler ou processar Google Sheets: {e}")
        return None # Retorna None para indicar falha na leitura

# -----------------------------------------------------------------------------
# FUNÇÃO PARA CALCULAR HASH ÚNICO (Sem alterações)
# -----------------------------------------------------------------------------
def calculate_unique_hash(row: pd.Series) -> str:
    """
    Cria um hash MD5 único para cada registro baseado nos campos chave.
    AGORA INCLUI 'LANCTO'.
    Trata valores nulos/ausentes como strings vazias para consistência.
    IMPORTANTE: A ordem e os campos devem ser consistentes.
    """
    try:
        # Adicionando LANCTO à lista de campos para o hash.
        # A ordem exata não importa, desde que seja consistente.
        # Vamos adicioná-lo no início para clareza.
        unique_fields = [
            str(row.get("LANCTO", "")),    # <-- ADICIONADO AQUI
            str(row.get("DATA", "")),
            str(row.get("VALOR", "")),
            str(row.get("NOME", "")),
            str(row.get("SISTEMA", "")),
            str(row.get("DOCUMENTO", ""))
        ]
        unique_str = "|".join(unique_fields)
        return hashlib.md5(unique_str.encode('utf-8')).hexdigest()
    except Exception as e:
        logger.error(f"Erro ao calcular hash para linha: {row}. Erro: {e}")
        return f"error_hashing_{time.time()}"

# -----------------------------------------------------------------------------
# FUNÇÃO PARA OBTER HASHES EXISTENTES DO BANCO (Versão Revisada)
# -----------------------------------------------------------------------------
def get_existing_hashes(conn) -> set:
    """
    Obtém o conjunto de hashes de registros existentes na tabela
    buscando na coluna indexada 'registro_hash'.
    """
    logger.info("[get_existing_hashes] Buscando hashes existentes da coluna 'registro_hash' no banco...")
    existing_hashes = set()
    sql = "SELECT registro_hash FROM public.transacoes WHERE registro_hash IS NOT NULL"
    try:
        with conn.cursor() as cur: # Usar 'with' garante fechamento do cursor
            cur.execute(sql)
            results = cur.fetchall()
            existing_hashes = {row[0] for row in results}
            logger.info(f"[get_existing_hashes] {len(existing_hashes)} hashes únicos encontrados no banco.")
    except psycopg2.Error as e:
        logger.exception(f"[get_existing_hashes] Erro de banco ao buscar hashes: {e}")
        # Levantar a exceção pode ser melhor para parar a task
        raise
    except Exception as e:
        logger.exception(f"[get_existing_hashes] Erro inesperado ao buscar hashes: {e}")
        raise
    return existing_hashes

# -----------------------------------------------------------------------------
# FUNÇÃO PARA PREPARAR REGISTROS PARA SINCRONIZAÇÃO (Nova)
# -----------------------------------------------------------------------------
def prepare_records_for_sync(df: pd.DataFrame, existing_db_hashes: set) -> tuple[list, list, list]:
    """
    Prepara os registros para sincronização: Calcula hashes da planilha,
    identifica hashes a deletar do DB e prepara registros novos para inserção.
    Retorna (hashes_para_deletar, registros_para_inserir, colunas_finais_com_hash).
    """
    logger.info("[prepare_records_for_sync] Iniciando preparação para sincronização...")

    # Colunas finais que devem existir na tabela do BD, incluindo o hash
    # IMPORTANTE: A ordem aqui deve corresponder à ordem dos valores em 'records_to_insert'
    colunas_final_com_hash = [
        "LANCTO", "NOME", "DATA", "TIPO", "VALOR", "DOCUMENTO", "CPF",
        "HORA", "FONE1", "FONE2", "NOME_CRD013", "CATEGORIA", "UNIDADE",
        "MES", "TERMINAL", "USUARIO", "SISTEMA", "CODIGO",
        "METODO_PAGAMENTO", "registro_hash" # Hash é a última
    ]
    # Colunas usadas para gerar a lista de valores (todas exceto a última)
    colunas_para_valores = colunas_final_com_hash[:-1]

    sheet_hashes_map = {} # Mapeia hash -> lista de valores da linha (para inserção)
    sheet_hashes_set = set() # Apenas o conjunto de hashes da planilha

    total_rows = len(df)
    processed = 0
    duplicatas_planilha = 0
    erros_hash = 0

    logger.info(f"[prepare_records_for_sync] Processando {total_rows} linhas do DataFrame...")
    for index, row in df.iterrows():
        processed += 1
        if processed % 50000 == 0: # Log a cada 50k linhas
             logger.info(f"[prepare_records_for_sync] Processando linha {processed}/{total_rows}...")

        row_hash = calculate_unique_hash(row)

        # Verifica se o hash foi calculado corretamente
        if row_hash.startswith("error_hashing_"):
             erros_hash += 1
             continue # Pula linhas com erro de hash

        # Verifica duplicatas na própria planilha (baseado no hash)
        if row_hash in sheet_hashes_set:
            duplicatas_planilha += 1
            continue # Pula esta linha duplicada da planilha

        sheet_hashes_set.add(row_hash)
        # Monta a lista de valores na ordem de colunas_final_com_hash
        # Usar row.get(col, None) para robustez se alguma coluna não veio do load_sheet_data
        registro_values = [row.get(col, None) for col in colunas_para_valores]
        registro_values.append(row_hash) # Adiciona o hash ao final da lista
        sheet_hashes_map[row_hash] = registro_values

    if duplicatas_planilha > 0:
         logger.warning(f"[prepare_records_for_sync] {duplicatas_planilha} linhas duplicadas (baseado no hash) encontradas e ignoradas na planilha.")
    if erros_hash > 0:
         logger.error(f"[prepare_records_for_sync] {erros_hash} linhas tiveram erro no cálculo do hash e foram ignoradas.")

    logger.info(f"[prepare_records_for_sync] {len(sheet_hashes_set)} hashes únicos válidos calculados da planilha.")

    # --- Comparação de Conjuntos ---
    logger.info("[prepare_records_for_sync] Comparando hashes da planilha com hashes do banco...")
    hashes_to_delete = list(existing_db_hashes - sheet_hashes_set) # Convertido para lista
    hashes_to_insert = sheet_hashes_set - existing_db_hashes

    # Preparar a lista de listas de valores para inserção
    # Garante que só incluímos hashes que realmente mapeamos
    records_to_insert = [sheet_hashes_map[h] for h in hashes_to_insert if h in sheet_hashes_map]

    # Log dos resultados da comparação
    logger.info(f"[prepare_records_for_sync] {len(hashes_to_delete)} hashes identificados para deletar do DB.")
    logger.info(f"[prepare_records_for_sync] {len(records_to_insert)} novos registros preparados para inserir no DB.")
    if len(hashes_to_insert) != len(records_to_insert):
        logger.error(f"[prepare_records_for_sync] Discrepância: {len(hashes_to_insert)} hashes para inserir, mas {len(records_to_insert)} registros mapeados!")

    return hashes_to_delete, records_to_insert, colunas_final_com_hash

# -----------------------------------------------------------------------------
# FUNÇÃO PARA DELETAR REGISTROS OBSOLETOS (Nova)
# -----------------------------------------------------------------------------
def delete_obsolete_records(conn, cur, hashes_to_delete: list):
    """
    Deleta registros do banco de dados baseado em uma lista de hashes, usando lotes.
    Retorna o número de registros deletados.
    """
    if not hashes_to_delete:
        logger.info("[delete_obsolete_records] Nenhum registro obsoleto para deletar.")
        return 0

    total_to_delete = len(hashes_to_delete)
    logger.info(f"[delete_obsolete_records] Iniciando exclusão em lote de {total_to_delete} registros obsoletos...")

    batch_size = 5000 # Ajuste conforme necessário
    deleted_count = 0
    delete_query = "DELETE FROM public.transacoes WHERE registro_hash IN %s"

    try:
        for i in range(0, total_to_delete, batch_size):
            batch_hashes = hashes_to_delete[i : i + batch_size]
            # execute_values espera uma lista de tuplas
            tuples_to_delete = [(h,) for h in batch_hashes]

            # Executa a deleção para o lote
            execute_values(cur, delete_query, tuples_to_delete, page_size=batch_size)
            # Importante: Obter a contagem de linhas afetadas ANTES do commit
            batch_deleted_count = cur.rowcount
            # Commit após cada lote bem-sucedido
            conn.commit()
            deleted_count += batch_deleted_count # Usar rowcount retornado
            logger.info(
                f"[delete_obsolete_records] Lote {i // batch_size + 1}/"
                f"{(total_to_delete + batch_size - 1) // batch_size} processado. "
                f"{batch_deleted_count} registros deletados neste lote. "
                f"Total deletado: {deleted_count}/{total_to_delete}"
            )
        logger.info(f"[delete_obsolete_records] Exclusão em lote concluída. Total de {deleted_count} registros deletados.")

    except psycopg2.Error as e:
        logger.exception(f"[delete_obsolete_records] Erro de banco durante a exclusão em lote: {e}")
        try:
            conn.rollback() # Tenta reverter a transação do lote atual
            logger.info("[delete_obsolete_records] Rollback da transação do lote de exclusão realizado.")
        except Exception as roll_e:
             logger.error(f"[delete_obsolete_records] Erro ao tentar reverter transação de exclusão: {roll_e}")
        raise # Propaga o erro original para a task Celery

    except Exception as e:
        logger.exception(f"[delete_obsolete_records] Erro inesperado durante exclusão: {e}")
        try:
            conn.rollback()
        except Exception as roll_e:
             logger.error(f"[delete_obsolete_records] Erro ao tentar reverter transação de exclusão: {roll_e}")
        raise

    return deleted_count

# -----------------------------------------------------------------------------
# FUNÇÃO PARA INSERIR REGISTROS EM LOTE (Versão Revisada)
# -----------------------------------------------------------------------------
def bulk_insert_records(conn, cur, new_records: list, colunas: list):
    """
    Insere múltiplos registros de uma vez usando execute_values.
    'colunas' deve incluir 'registro_hash'.
    'new_records' deve ser uma lista de listas/tuplas com valores na ordem de 'colunas'.
    Retorna o número de registros inseridos.
    """
    if not new_records:
        logger.info("[bulk_insert_records] Nenhum novo registro para inserir.")
        return 0

    total_to_insert = len(new_records)
    logger.info(f"[bulk_insert_records] Iniciando inserção em lote de {total_to_insert} registros...")

    # Formata nomes de colunas - use aspas duplas se tiver maiúsculas/minúsculas misturadas no DB
    # Se forem todas minúsculas, aspas não são estritamente necessárias mas não prejudicam.
    columns_str = ", ".join([f'"{col.lower()}"' for col in colunas])
    insert_query = f"INSERT INTO public.transacoes ({columns_str}) VALUES %s"

    batch_size = 5000 # Ajuste conforme necessário
    inserted_count = 0

    try:
        for i in range(0, total_to_insert, batch_size):
            batch = new_records[i : i + batch_size]
            # Executa a inserção para o lote
            execute_values(cur, insert_query, batch, page_size=batch_size)
            batch_inserted_count = cur.rowcount # Obter contagem antes do commit
            conn.commit() # Commit após cada lote bem-sucedido
            inserted_count += batch_inserted_count
            logger.info(
                f"[bulk_insert_records] Lote {i // batch_size + 1}/"
                f"{(total_to_insert + batch_size - 1) // batch_size} processado. "
                f"{batch_inserted_count} registros inseridos neste lote. "
                f"Total inserido: {inserted_count}/{total_to_insert}"
            )
        logger.info(f"[bulk_insert_records] Inserção em lote concluída. Total de {inserted_count} novos registros inseridos.")

    except psycopg2.Error as e:
        logger.exception(f"[bulk_insert_records] Erro de banco durante a inserção em lote: {e}")
        try:
            conn.rollback()
            logger.info("[bulk_insert_records] Rollback da transação do lote de inserção realizado.")
        except Exception as roll_e:
             logger.error(f"Erro ao tentar reverter transação de inserção: {roll_e}")
        raise # Propaga o erro original

    except Exception as e:
        logger.exception(f"[bulk_insert_records] Erro inesperado durante inserção: {e}")
        try:
            conn.rollback()
        except Exception as roll_e:
             logger.error(f"Erro ao tentar reverter transação de inserção: {roll_e}")
        raise

    return inserted_count


# -----------------------------------------------------------------------------
# TAREFA CELERY PRINCIPAL (Versão Revisada - Sync)
# -----------------------------------------------------------------------------
# Aumente o time_limit se a sincronização for demorada (ex: 1 hora = 3600)
@celery_app.task(name="app.workers.sheets_tasks.fetch_and_sync_sheets", time_limit=3600)
def fetch_and_sync_sheets():
    """
    Tarefa Celery que sincroniza Google Sheets com o DB:
    Lê Google Sheets, compara com DB via hash, DELETA obsoletos e INSERE novos.
    Usa lock no DB para evitar execuções concorrentes.
    """
    start_task_time = time.time()
    worker_id = f"worker-sheets-sync-{start_task_time:.0f}-{id(fetch_and_sync_sheets)}"
    task_name = "sheets_google_sync" # Nome para o lock no banco
    conn = None
    cur = None
    lock_acquired = False

    logger.info(f"--- [TASK START] {task_name} --- Worker ID: {worker_id}")

    try:
        # 1. Conectar ao Banco
        conn, cur = connect_db() # connect_db já levanta exceção se falhar

        # 2. Verificar Tabela de Lock (Opcional mas bom)
        try:
            cur.execute("SELECT 1 FROM public.sheets_task_locks LIMIT 1")
            cur.fetchone() # Apenas para garantir que a query funciona
            logger.debug(f"Tabela de locks 'public.sheets_task_locks' verificada.")
        except psycopg2.errors.UndefinedTable:
             logger.error(f"A tabela de locks 'public.sheets_task_locks' não existe! Crie-a ou remova a lógica de lock.")
             # Decida se quer continuar sem lock ou falhar
             # raise psycopg2.errors.UndefinedTable("Tabela de lock não encontrada")
             pass # Continua sem lock se a tabela não existe (ajuste conforme sua política)
        except psycopg2.Error as e:
             logger.error(f"Erro ao verificar tabela de locks: {e}")
             raise # Falha a task se não consegue verificar

        # 3. Adquirir Lock no Banco
        # Use um tempo de expiração ligeiramente menor que o time_limit da task
        lock_acquired = acquire_db_lock(conn, cur, task_name, worker_id, expire_seconds=3500)
        if not lock_acquired:
            logger.warning(f"Não foi possível adquirir o lock '{task_name}'. Outra instância pode estar ativa. Encerrando task.")
            # Encerra silenciosamente, outra task está trabalhando
            return

        logger.info(f"Lock '{task_name}' adquirido com sucesso por {worker_id}.")

        # --- BLOCO PRINCIPAL DA SINCRONIZAÇÃO (DENTRO DO LOCK) ---
        sync_start_time = time.time()
        try:
            # 4. Ler dados do Google Sheets
            logger.info("Iniciando leitura e pré-processamento do Google Sheets...")
            df = load_sheet_data() # Retorna DataFrame ou None
            if df is None:
                 # Falha na leitura do Sheets é crítica, não podemos continuar
                 raise ValueError("Falha ao ler dados do Google Sheets. Verifique logs anteriores.")
            if df.empty:
                 logger.warning("Nenhum dado retornado do Google Sheets. O banco será comparado com um conjunto vazio (pode levar a exclusões se houver dados no banco).")
            else:
                 logger.info(f"{len(df)} linhas carregadas e pré-processadas do Google Sheets.")

            # 5. Obter Hashes Existentes do Banco
            existing_db_hashes = get_existing_hashes(conn) # Levanta exceção em caso de erro

            # 6. Preparar para Sincronização (Comparar Hashes, Identificar Ações)
            hashes_to_delete, records_to_insert, colunas_final = prepare_records_for_sync(df, existing_db_hashes)

            # 7. Deletar Registros Obsoletos (em lotes)
            deleted_count = delete_obsolete_records(conn, cur, hashes_to_delete) # Levanta exceção em caso de erro

            # 8. Inserir Novos Registros (em lotes)
            inserted_count = bulk_insert_records(conn, cur, records_to_insert, colunas_final) # Levanta exceção em caso de erro

            sync_end_time = time.time()
            sync_duration = sync_end_time - sync_start_time
            logger.info(f"--- Sincronização concluída em {sync_duration:.2f} segundos ---")
            logger.info(f"Registros deletados do banco: {deleted_count}")
            logger.info(f"Registros inseridos no banco: {inserted_count}")

            # 9. (Opcional) Verificar Contagem Final
            try:
                cur.execute("SELECT COUNT(*) FROM public.transacoes")
                final_db_count = cur.fetchone()[0]
                logger.info(f"Contagem final de registros na tabela 'public.transacoes': {final_db_count}")
                # Validar se a contagem final faz sentido (opcional)
                # expected_count = len(existing_db_hashes) - deleted_count + inserted_count
                # if final_db_count != expected_count:
                #     logger.warning(f"Contagem final no banco ({final_db_count}) difere do esperado ({expected_count})!")
            except Exception as count_e:
                logger.error(f"Erro ao obter contagem final de registros: {count_e}")


        except Exception as sync_error:
            # Se ocorrer um erro DENTRO do bloco de sincronização, loga e re-levanta
            logger.exception(f"Erro CRÍTICO durante a execução da sincronização: {sync_error}")
            # Rollback é feito dentro das funções de batch, mas podemos tentar de novo aqui por segurança
            if conn:
                try: conn.rollback()
                except: pass
            raise # Re-levanta para a task Celery marcar como falha

        # --- FIM DO BLOCO PRINCIPAL DA SINCRONIZAÇÃO ---

    except Exception as task_error:
        # Captura erros que ocorrem FORA do bloco de sincronização principal
        # (ex: falha na conexão, erro no lock inicial)
        logger.exception(f"Erro irrecuperável na configuração ou início da task: {task_error}")
        # Não precisa de raise aqui se o erro já foi levantado antes (ex: connect_db)
        # Mas se chegou aqui por um erro inesperado, pode ser bom levantar para o Celery
        # raise task_error # Descomente se quiser garantir que a task falhe no Celery

    finally:
        # --- SEMPRE TENTAR LIBERAR O LOCK E FECHAR A CONEXÃO ---
        if lock_acquired and conn and cur:
            try:
                release_ok = release_db_lock(conn, cur, task_name, worker_id)
                logger.info(f"Tentativa de liberar lock '{task_name}'. Sucesso: {release_ok}")
            except Exception as release_e:
                logger.error(f"Erro EXCEPCIONAL ao tentar liberar lock: {release_e}") # Não deve acontecer

        if cur:
            try: cur.close()
            except: pass # Ignora erros ao fechar cursor
        if conn:
            try: conn.close()
            except: pass # Ignora erros ao fechar conexão
            logger.info("Conexão com o banco de dados fechada.")

        end_task_time = time.time()
        task_duration = end_task_time - start_task_time
        logger.info(f"--- [TASK END] {task_name} --- Duração total: {task_duration:.2f} segundos ---")

# Exemplo de como agendar a tarefa no Celery Beat (coloque isso na sua configuração Celery):
# app.conf.beat_schedule = {
#     'sync-sheets-every-10-minutes': {
#         'task': 'app.workers.sheets_tasks.fetch_and_sync_sheets', # Nome completo da task
#         'schedule': crontab(minute='*/10'), # Ou timedelta(minutes=10)
#     },
# }
# Certifique-se de importar 'crontab' ou 'timedelta' de 'celery.schedules'
