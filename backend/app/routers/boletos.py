# Boleto routes.
import re
import uuid
import logging
import traceback
from datetime import datetime, timedelta
from typing import List, Optional
import requests

from fastapi import APIRouter, HTTPException, status, Query

from ..boleto_sdk.sdk import BoletoSDK
from ..boleto_sdk.sdk_utils import get_token_and_seller_for_unidade
from ..database.db import DatabaseConnection

from ..models.boletos import (
    BoletoCreateFull,
    BoletoCreatedItem,
    BoletoRead,
    BoletoUpdate
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/boletos", tags=["boletos"])


def _verificar_se_contrato_existe(contrato_id: int) -> bool:
    """
    Retorna True se o contrato existir, False caso contrário.
    """
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT contrato_id FROM contratos WHERE contrato_id = %s", (contrato_id,))
        row = cursor.fetchone()
    return bool(row)


@router.post("", response_model=List[BoletoCreatedItem], status_code=status.HTTP_201_CREATED)
def criar_boletos(data: BoletoCreateFull):
    """
    Emite 1 ou mais boletos na Bempaggo (chamando BoletoSDK) e salva no DB.
    Retorna lista de informações de cada parcela criada.
    A emissão financeira não altera a unidade cadastral do paciente.
    """
    logger.info("==== [CRIA BOLETOS] Recebendo requisição de criar boletos ====")
    logger.debug(
        "Requisição de boleto validada. unidade=%s parcelas=%s",
        data.unidade,
        data.num_parcelas,
    )

    # Se o campo contrato_id estiver preenchido, verifica se existe no banco.
    if data.contrato_id is not None:
        existe = _verificar_se_contrato_existe(data.contrato_id)
        if not existe:
            raise HTTPException(
                status_code=400,
                detail=f"Contrato {data.contrato_id} não encontrado no banco."
            )

    # 1) Obter token e seller_id a partir da unidade
    try:
        logger.debug("Buscando token e seller_id para a unidade '%s'", data.unidade)
        api_token, seller_id = get_token_and_seller_for_unidade(data.unidade, "production")
        logger.debug("Obtido: api_token=[REDACTED], seller_id=%s", seller_id)
    except ValueError as e:
        logger.error("Unidade inválida ou sem token configurado: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    if not api_token:
        logger.error("Token não configurado para a unidade '%s'", data.unidade)
        raise HTTPException(status_code=400, detail=f"Token não configurado para unidade {data.unidade}.")

    # 2) Instanciar a SDK
    sdk = BoletoSDK(
        api_token=api_token,
        seller_id=seller_id,
        environment="production"  # ou "production"
    )
    logger.debug("Instanciada BoletoSDK com environment=production")

    # 3) Montar dados do customer
    try:
        logger.debug("Preparando objeto customer_data")
        customer_data = {
            "name": data.nome_cliente,
            "document": data.cpf_cnpj,
            "email": data.email or "",
            "birthdate": data.birthdate.isoformat() if data.birthdate else "",
            "phone": {
                "countryCode": int(re.sub(r"\D", "", data.phone_country_code) or 55),
                "areaCode": int(re.sub(r"\D", "", data.phone_area_code) or 21),
                "number": int(re.sub(r"\D", "", data.phone_number) or 999999999),
            },
            "address": {
                "street": data.street,
                "streetNumber": data.street_number,
                "neighborhood": data.neighborhood,
                "city": data.city,
                "state": data.state,
                "zipCode": data.zip_code,
            }
        }
        logger.debug("customer_data final: %s", customer_data)
    except Exception as e:
        logger.error("Erro ao processar customer_data: %s", traceback.format_exc())
        raise HTTPException(status_code=422, detail=f"Erro ao processar dados do cliente: {e}")

    # 4) Calcular valor total em centavos
    valor_centavos = int(round(data.valor_reais * 100))
    logger.debug("Calculado valor_centavos=%s a partir de valor_reais=%s", valor_centavos, data.valor_reais)
    if valor_centavos <= 0:
        logger.error("Valor inválido: %s", valor_centavos)
        raise HTTPException(status_code=400, detail="Valor inválido.")

    # 5) Lógica para parcelas
    parcela_base = valor_centavos // data.num_parcelas
    resto = valor_centavos % data.num_parcelas
    logger.debug("parcelas=%s => parcela_base=%s, resto=%s", data.num_parcelas, parcela_base, resto)

    now = datetime.now()
    results: List[BoletoCreatedItem] = []

    # Pega "criado_por" (se não vier, fallback)
    criado_por = data.criado_por if data.criado_por else "API_USER"

    for i in range(data.num_parcelas):
        parcela_idx = i + 1
        logger.info("=== Iniciando emissão da parcela %s/%s ===", parcela_idx, data.num_parcelas)

        # Gera um UUID para cada parcela
        my_unique_id = str(uuid.uuid4())
        short_id = my_unique_id[:10]

        # Data de vencimento
        parcela_due = data.days_until_due + 30 * i
        due_date_dt = now + timedelta(days=parcela_due)
        due_date_iso = due_date_dt.isoformat() + "Z"

        # Payment limit date
        payment_limit_iso = (due_date_dt + timedelta(days=60)).isoformat() + "Z"

        # Valor desta parcela
        v = parcela_base
        if resto > 0:
            v += 1
            resto -= 1

        order_ref = f"PED_{short_id}_PARCELA_{parcela_idx}"

        # Definir instruções
        if data.is_minor_dependent and data.dependent_name:
            instructions = f"Tratamento para o paciente: {data.dependent_name}. {data.instrucoes_padrao}"
        else:
            instructions = data.instrucoes_padrao or "Não receber após o vencimento"

        # 6) Boleto_data p/ Bempaggo
        boleto_data = {
            "orderReference": order_ref,
            "amount": v,
            "customer": customer_data,
            "payments": [{
                "amount": v,
                "paymentMethod": "BOLETO",
                "dueDate": due_date_iso,
                "paymentLimitDate": payment_limit_iso,
                "fine": {"days": 1, "type": "PERCENTAGE", "amount": 20000},
                "interest": {"days": 1, "type": "PERCENTAGE", "amount": 10000, "frequency": "DAILY"},
                "instructions": instructions
            }],
            "notificationUrl": f"{os.getenv('PUBLIC_BASE_URL', 'https://api.exemplo.com')}/webhook/bempaggo?token={my_unique_id}"
        }
        logger.debug("Dados para criar boleto (parcela %s): %s", parcela_idx, boleto_data)

        # 7) Chamar a Bempaggo via SDK
        try:
            response = sdk.create_boleto(boleto_data)
            logger.debug("Resposta Bempaggo (parcela %s): %s", parcela_idx, response)
        except requests.exceptions.HTTPError as http_err:
            logger.error("Erro HTTP ao criar boleto na parcela %s: %s", parcela_idx, traceback.format_exc())
            if http_err.response is not None:
                logger.error("Corpo da resposta Bempaggo (HTTP %s): %s",
                            http_err.response.status_code, http_err.response.text)
                try:
                    bempaggo_data = http_err.response.json()
                    bempaggo_msg = bempaggo_data.get("message", http_err.response.text)
                except:
                    bempaggo_msg = http_err.response.text
            else:
                bempaggo_msg = str(http_err)

            raise HTTPException(
                status_code=400,
                detail=f"Erro ao criar boleto (parcela {parcela_idx}): {bempaggo_msg}"
            )
        except Exception as e:
            logger.error("Erro inesperado ao chamar SDK Bempaggo p/ parcela %s: %s", parcela_idx, traceback.format_exc())
            raise HTTPException(
                status_code=400,
                detail=f"Erro inesperado (parcela {parcela_idx}): {str(e)}"
            )

        status_resp = response.get("status", "UNKNOWN")
        boleto_url = response.get("boleto_url", "")
        digitable_line = response.get("digitable_line", "")
        bar_code = response.get("bar_code", "")
        charge_id = response.get("charge_id", "")
        transaction_message = response.get("transaction_message", "")

        # 8) Salvar no banco (tabela boletos)
        try:
            phone_digits = (
                f"{customer_data['phone']['countryCode']}"
                f"{customer_data['phone']['areaCode']}"
                f"{customer_data['phone']['number']}"
            )
            address_full = (
                f"{customer_data['address']['street']}, "
                f"{customer_data['address']['streetNumber']}, "
                f"{customer_data['address']['neighborhood']}, "
                f"{customer_data['address']['city']}-{customer_data['address']['state']}, "
                f"CEP: {customer_data['address']['zipCode']}"
            )

            logger.debug(
                "Salvar parcela %s no DB: phone_digits=%s address_full='%s'",
                parcela_idx, phone_digits, address_full
            )

            with DatabaseConnection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO boletos (
                        nome_cliente, cpf_cnpj, telefone, endereco,
                        valor, data_vencimento, boleto_url, linha_digitavel,
                        codigo_barras, status, data_geracao, unidade,
                        charge_id, criado_por, uuid, instrucoes,
                        dependent_name, is_minor, order_reference,
                        numero_parcela, total_parcelas, contrato_id
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING id
                """, (
                    data.nome_cliente,
                    data.cpf_cnpj,
                    phone_digits,
                    address_full,
                    float(v) / 100.0,
                    due_date_dt,
                    boleto_url,
                    digitable_line,
                    bar_code,
                    status_resp,
                    data.unidade,
                    charge_id,
                    criado_por,   # <--- Agora usamos o campo
                    my_unique_id,
                    instructions,
                    data.dependent_name if data.is_minor_dependent else None,
                    data.is_minor_dependent,
                    order_ref,
                    parcela_idx,
                    data.num_parcelas,
                    data.contrato_id
                ))
                new_id = cursor.fetchone()[0]
                conn.commit()

            db_message = f"Boleto salvo com ID {new_id}"
            logger.info("Sucesso ao salvar parcela %s: %s", parcela_idx, db_message)

        except Exception as e:
            logger.error("Erro ao salvar parcela %s no DB: %s", parcela_idx, traceback.format_exc())
            db_message = f"Falha ao salvar parcela {parcela_idx} no DB: {str(e)}"

        # 9) Montar objeto de resposta
        results.append(BoletoCreatedItem(
            parcela=parcela_idx,
            total_parcelas=data.num_parcelas,
            id=new_id,
            status=status_resp,
            boleto_url=boleto_url,
            digitable_line=digitable_line,
            bar_code=bar_code,
            message=transaction_message or db_message
        ))

    logger.info("==== [CRIA BOLETOS] Finalizado com sucesso. Gerados %s boletos. ====", len(results))
    return results


@router.get("", response_model=List[BoletoRead])
def list_all_boletos():
    """Lista todos os boletos do banco (sem chamar Bempaggo)."""
    logger.info("Listando todos os boletos do banco.")
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                id, nome_cliente, cpf_cnpj, telefone, endereco,
                valor, data_vencimento, boleto_url, linha_digitavel,
                codigo_barras, status, data_geracao, unidade,
                charge_id, criado_por, uuid, instrucoes,
                dependent_name, is_minor, order_reference,
                metodo_pagamento, numero_parcela, total_parcelas,
                contrato_id
            FROM boletos
            ORDER BY id
        """)
        rows = cursor.fetchall()

    logger.debug("Encontrados %s registros na tabela boletos", len(rows))
    return [_row_to_boleto_read(r) for r in rows]


@router.get("", response_model=List[BoletoRead])
def get_boletos(
    contrato_id: Optional[int] = Query(None),
    paciente_id: Optional[int] = Query(None)
):
    """
    Lista boletos de acordo com os parâmetros de query:
      - Se 'contrato_id' for informado, filtra por contrato_id
      - Se 'paciente_id' for informado, filtra por paciente_id
      - Se nenhum for informado, retorna todos
    """
    query = """
        SELECT
            id, nome_cliente, cpf_cnpj, telefone, endereco,
            valor, data_vencimento, boleto_url, linha_digitavel,
            codigo_barras, status, data_geracao, unidade,
            charge_id, criado_por, uuid, instrucoes,
            dependent_name, is_minor, order_reference,
            metodo_pagamento, numero_parcela, total_parcelas,
            contrato_id
        FROM boletos
        WHERE 1=1
    """
    params = []

    if contrato_id is not None:
        query += " AND contrato_id = %s"
        params.append(contrato_id)

    if paciente_id is not None:
        query += " AND paciente_id = %s"
        params.append(paciente_id)

    query += " ORDER BY id"

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

    return [_row_to_boleto_read(row) for row in rows]


@router.put("/{boleto_id}", response_model=BoletoRead)
def update_boleto(boleto_id: int, data: BoletoUpdate):
    """Atualiza campos de um boleto no banco (sem chamar Bempaggo)."""
    logger.info("Atualizando boleto ID=%s com payload: %s", boleto_id, data.dict(exclude_unset=True))

    with DatabaseConnection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM boletos WHERE id = %s", (boleto_id,))
        existing = cursor.fetchone()
        if not existing:
            logger.warning("Tentativa de atualizar boleto inexistente ID=%s", boleto_id)
            raise HTTPException(status_code=404, detail="Boleto não encontrado")

        fields = []
        values = []

        if data.nome_cliente is not None:
            fields.append("nome_cliente = %s")
            values.append(data.nome_cliente)
        if data.cpf_cnpj is not None:
            fields.append("cpf_cnpj = %s")
            values.append(data.cpf_cnpj)
        if data.telefone is not None:
            fields.append("telefone = %s")
            values.append(data.telefone)
        if data.endereco is not None:
            fields.append("endereco = %s")
            values.append(data.endereco)
        if data.valor is not None:
            fields.append("valor = %s")
            values.append(data.valor)
        if data.data_vencimento is not None:
            fields.append("data_vencimento = %s")
            values.append(data.data_vencimento)
        if data.boleto_url is not None:
            fields.append("boleto_url = %s")
            values.append(data.boleto_url)
        if data.linha_digitavel is not None:
            fields.append("linha_digitavel = %s")
            values.append(data.linha_digitavel)
        if data.codigo_barras is not None:
            fields.append("codigo_barras = %s")
            values.append(data.codigo_barras)
        if data.status is not None:
            fields.append("status = %s")
            values.append(data.status)
        if data.unidade is not None:
            fields.append("unidade = %s")
            values.append(data.unidade)
        if data.charge_id is not None:
            fields.append("charge_id = %s")
            values.append(data.charge_id)
        if data.criado_por is not None:
            fields.append("criado_por = %s")
            values.append(data.criado_por)
        if data.uuid is not None:
            fields.append("uuid = %s")
            values.append(data.uuid)
        if data.instrucoes is not None:
            fields.append("instrucoes = %s")
            values.append(data.instrucoes)
        if data.dependent_name is not None:
            fields.append("dependent_name = %s")
            values.append(data.dependent_name)
        if data.is_minor is not None:
            fields.append("is_minor = %s")
            values.append(data.is_minor)
        if data.order_reference is not None:
            fields.append("order_reference = %s")
            values.append(data.order_reference)
        if data.metodo_pagamento is not None:
            fields.append("metodo_pagamento = %s")
            values.append(data.metodo_pagamento)
        if data.numero_parcela is not None:
            fields.append("numero_parcela = %s")
            values.append(data.numero_parcela)
        if data.total_parcelas is not None:
            fields.append("total_parcelas = %s")
            values.append(data.total_parcelas)

        # Caso queira permitir atualização de contrato_id
        if data.contrato_id is not None:
            existe_contrato = _verificar_se_contrato_existe(data.contrato_id)
            if not existe_contrato:
                raise HTTPException(
                    status_code=400,
                    detail=f"Contrato {data.contrato_id} não encontrado."
                )
            fields.append("contrato_id = %s")
            values.append(data.contrato_id)

        if not fields:
            logger.info("Nenhum campo para atualizar em boleto ID=%s. Retornando registro original.", boleto_id)
            cursor.execute("""
                SELECT
                    id, nome_cliente, cpf_cnpj, telefone, endereco,
                    valor, data_vencimento, boleto_url, linha_digitavel,
                    codigo_barras, status, data_geracao, unidade,
                    charge_id, criado_por, uuid, instrucoes,
                    dependent_name, is_minor, order_reference,
                    metodo_pagamento, numero_parcela, total_parcelas,
                    contrato_id
                FROM boletos
                WHERE id = %s
            """, (boleto_id,))
            row = cursor.fetchone()
            return _row_to_boleto_read(row)

        sql = f"""
        UPDATE boletos
        SET {', '.join(fields)}
        WHERE id = %s
        RETURNING
            id, nome_cliente, cpf_cnpj, telefone, endereco,
            valor, data_vencimento, boleto_url, linha_digitavel,
            codigo_barras, status, data_geracao, unidade,
            charge_id, criado_por, uuid, instrucoes,
            dependent_name, is_minor, order_reference,
            metodo_pagamento, numero_parcela, total_parcelas,
            contrato_id
        """
        values.append(boleto_id)

        try:
            cursor.execute(sql, tuple(values))
            updated_row = cursor.fetchone()
            conn.commit()
            logger.info("Boleto ID=%s atualizado com sucesso.", boleto_id)
        except Exception as e:
            logger.error("Erro ao atualizar boleto ID=%s: %s", boleto_id, traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Erro ao atualizar boleto: {str(e)}")

    return _row_to_boleto_read(updated_row)


@router.delete("/{boleto_id}")
def delete_boleto(boleto_id: int):
    """Remove um boleto do banco (sem chamar Bempaggo)."""
    logger.info("Removendo boleto ID=%s", boleto_id)
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM boletos WHERE id = %s", (boleto_id,))
        row = cursor.fetchone()
        if not row:
            logger.warning("Boleto ID=%s não encontrado para exclusão", boleto_id)
            raise HTTPException(status_code=404, detail="Boleto não encontrado")

        cursor.execute("DELETE FROM boletos WHERE id = %s", (boleto_id,))
        conn.commit()

    logger.info("Boleto ID=%s removido com sucesso.", boleto_id)
    return {"message": f"Boleto {boleto_id} removido com sucesso."}


@router.get("/", response_model=List[BoletoRead])
def get_boletos(
    contrato_id: Optional[int] = Query(None),
    paciente_id: Optional[int] = Query(None)
):
    """
    Lista boletos de acordo com os parâmetros de query:
      - Se 'contrato_id' for informado, retorna boletos daquele contrato;
      - Se 'paciente_id' for informado, retorna boletos daquele paciente;
      - Se nenhum parâmetro for passado, retorna todos os boletos.
    """
    query = """
        SELECT
            id, nome_cliente, cpf_cnpj, telefone, endereco,
            valor, data_vencimento, boleto_url, linha_digitavel,
            codigo_barras, status, data_geracao, unidade,
            charge_id, criado_por, uuid, instrucoes,
            dependent_name, is_minor, order_reference,
            metodo_pagamento, numero_parcela, total_parcelas,
            contrato_id
        FROM boletos
        WHERE 1=1
    """
    params = []

    if contrato_id is not None:
        query += " AND contrato_id = %s"
        params.append(contrato_id)

    if paciente_id is not None:
        query += " AND paciente_id = %s"
        params.append(paciente_id)

    query += " ORDER BY id"

    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

    boletos = []
    for row in rows:
        boletos.append(_row_to_boleto_read(row))

    return boletos


def _row_to_boleto_read(row) -> BoletoRead:
    """Converte tuple do cursor em BoletoRead."""
    return BoletoRead(
        id=row[0],
        nome_cliente=row[1],
        cpf_cnpj=row[2],
        telefone=row[3],
        endereco=row[4],
        valor=float(row[5]),
        data_vencimento=row[6],
        boleto_url=row[7],
        linha_digitavel=row[8],
        codigo_barras=row[9],
        status=row[10],
        data_geracao=row[11],
        unidade=row[12],
        charge_id=row[13],
        criado_por=row[14],
        uuid=row[15],
        instrucoes=row[16],
        dependent_name=row[17],
        is_minor=row[18],
        order_reference=row[19],
        metodo_pagamento=row[20],
        numero_parcela=row[21],
        total_parcelas=row[22],
        contrato_id=row[23]
    )

@router.get("/pagos", response_model=List[BoletoRead], summary="Listar Boletos Pagos")
def get_boletos_pagos():
    """
    Recupera e retorna uma lista completa de todos os boletos
    que estão marcados com o status 'PAY' no banco de dados.
    """
    logger.info("Recebida requisição para listar boletos pagos.")

    # Query SQL para buscar todos os campos dos boletos com status 'PAY'
    # Certifique-se que todas as colunas do BoletoRead estão aqui
    query = """
        SELECT
            id, nome_cliente, cpf_cnpj, telefone, endereco,
            valor, data_vencimento, boleto_url, linha_digitavel,
            codigo_barras, status, data_geracao, unidade,
            charge_id, criado_por, uuid, instrucoes,
            dependent_name, is_minor, order_reference,
            metodo_pagamento, numero_parcela, total_parcelas,
            contrato_id
        FROM public.boletos
        WHERE status = 'PAY' -- Pode usar UPPER(status) = 'PAY' se necessário
        ORDER BY data_vencimento DESC, id DESC; -- Ordena pelos mais recentes (opcional)
    """

    try:
        with DatabaseConnection() as conn:
            # Usar DictCursor pode ser útil se _row_to_boleto_read esperar um dicionário
            # cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor = conn.cursor() # Usando cursor padrão que retorna tuplas
            logger.debug("Executando query para buscar boletos pagos.")
            cursor.execute(query)
            rows = cursor.fetchall()
            logger.info(f"Encontrados {len(rows)} boletos com status 'PAY'.")

            # Converte as linhas do banco (tuplas) em modelos Pydantic BoletoRead
            # Garanta que a função _row_to_boleto_read esteja definida corretamente
            # para lidar com a ordem das colunas retornadas pela query.
            boletos_pagos = [_row_to_boleto_read(row) for row in rows]
            return boletos_pagos

    except Exception as e:
        logger.error(f"Erro ao buscar boletos pagos no banco de dados: {e}", exc_info=True)
        # Retorna um erro genérico para o cliente
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocorreu um erro interno ao buscar os boletos pagos."
        )
