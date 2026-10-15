from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.financeiro_pagamentos import (
    FinanceiroPagamentoItem,
    FinanceiroPagamentosAgregado,
    FinanceiroPagamentosFiltros,
    FinanceiroPagamentosResponse,
    FinanceiroPagamentosResumo,
)


TODAS_UNIDADES = {"Todas Unidades", "Todas unidades", "todas unidades", "Todas"}

ORDER_BY_MAP = {
    "data_vencimento": "data_vencimento",
    "data_pagamento": "data_pagamento",
    "valor_previsto": "valor_previsto",
    "valor_pago": "valor_pago",
    "nome_paciente": "nome_paciente",
    "status": "status_normalizado",
    "tipo": "tipo",
    "venda_id": "venda_id",
    "criado_em": "criado_em",
    "atualizado_em": "atualizado_em",
}


class FinanceiroPagamentosService:
    def listar_pagamentos(
        self,
        db: Session,
        filtros: FinanceiroPagamentosFiltros,
        page: int = 1,
        per_page: int = 50,
        order_by: str = "data_vencimento",
        order_dir: str = "desc",
    ) -> FinanceiroPagamentosResponse:
        offset = (page - 1) * per_page
        where_sql, params = self._build_where(filtros)
        order_sql = self._build_order(order_by, order_dir)

        count_sql = f"""
        {self._base_cte()}
        SELECT COUNT(*) AS total
        FROM pagamentos_filtrados
        {where_sql}
        """
        total = db.execute(text(count_sql), params).scalar() or 0

        data_params = dict(params)
        data_params.update({"limit": per_page, "offset": offset})
        data_sql = f"""
        {self._base_cte()}
        SELECT *
        FROM pagamentos_filtrados
        {where_sql}
        {order_sql}
        LIMIT :limit OFFSET :offset
        """
        rows = db.execute(text(data_sql), data_params).mappings().all()

        return FinanceiroPagamentosResponse(
            total=total,
            page=page,
            per_page=per_page,
            resumo=self.obter_resumo(db, filtros),
            pagamentos=[self._row_to_item(row) for row in rows],
        )

    def obter_resumo(
        self,
        db: Session,
        filtros: FinanceiroPagamentosFiltros,
    ) -> FinanceiroPagamentosResumo:
        where_sql, params = self._build_where(filtros)

        totals_sql = f"""
        {self._base_cte()}
        SELECT
            COUNT(*) AS total_itens,
            COALESCE(SUM(valor_previsto), 0) AS valor_previsto_total,
            COALESCE(SUM(COALESCE(valor_pago, 0)), 0) AS valor_pago_total,
            COALESCE(SUM(CASE WHEN status_normalizado = 'pendente' THEN valor_previsto ELSE 0 END), 0) AS valor_pendente,
            COALESCE(SUM(CASE WHEN status_normalizado = 'vencido' THEN valor_previsto ELSE 0 END), 0) AS valor_vencido,
            COALESCE(SUM(CASE WHEN status_normalizado = 'cancelado' THEN valor_previsto ELSE 0 END), 0) AS valor_cancelado,
            COALESCE(SUM(CASE WHEN status_normalizado = 'falha' THEN valor_previsto ELSE 0 END), 0) AS valor_falha,
            COUNT(CASE WHEN status_normalizado IN ('pago', 'pago_em_atraso') THEN 1 END) AS quantidade_paga,
            COUNT(CASE WHEN status_normalizado = 'pendente' THEN 1 END) AS quantidade_pendente,
            COUNT(CASE WHEN status_normalizado = 'vencido' THEN 1 END) AS quantidade_vencida,
            COUNT(CASE WHEN status_normalizado = 'cancelado' THEN 1 END) AS quantidade_cancelada
        FROM pagamentos_filtrados
        {where_sql}
        """
        totals = db.execute(text(totals_sql), params).mappings().first() or {}

        por_status = self._agrupar(db, where_sql, params, "status_normalizado")
        por_tipo = self._agrupar(db, where_sql, params, "tipo")

        return FinanceiroPagamentosResumo(
            total_itens=totals.get("total_itens") or 0,
            valor_previsto_total=totals.get("valor_previsto_total") or Decimal("0"),
            valor_pago_total=totals.get("valor_pago_total") or Decimal("0"),
            valor_pendente=totals.get("valor_pendente") or Decimal("0"),
            valor_vencido=totals.get("valor_vencido") or Decimal("0"),
            valor_cancelado=totals.get("valor_cancelado") or Decimal("0"),
            valor_falha=totals.get("valor_falha") or Decimal("0"),
            quantidade_paga=totals.get("quantidade_paga") or 0,
            quantidade_pendente=totals.get("quantidade_pendente") or 0,
            quantidade_vencida=totals.get("quantidade_vencida") or 0,
            quantidade_cancelada=totals.get("quantidade_cancelada") or 0,
            por_status=por_status,
            por_tipo=por_tipo,
        )

    def pagamentos_da_venda(self, db: Session, venda_id: int) -> List[FinanceiroPagamentoItem]:
        filtros = FinanceiroPagamentosFiltros(venda_id=venda_id)
        where_sql, params = self._build_where(filtros)
        sql = f"""
        {self._base_cte()}
        SELECT *
        FROM pagamentos_filtrados
        {where_sql}
        ORDER BY data_vencimento NULLS LAST, tipo, numero_parcela NULLS FIRST, origem_id
        """
        rows = db.execute(text(sql), params).mappings().all()
        return [self._row_to_item(row) for row in rows]

    def _agrupar(
        self,
        db: Session,
        where_sql: str,
        params: Dict[str, Any],
        column: str,
    ) -> List[FinanceiroPagamentosAgregado]:
        sql = f"""
        {self._base_cte()}
        SELECT
            COALESCE({column}, 'sem_informacao') AS chave,
            COUNT(*) AS quantidade,
            COALESCE(SUM(valor_previsto), 0) AS valor_previsto,
            COALESCE(SUM(COALESCE(valor_pago, 0)), 0) AS valor_pago
        FROM pagamentos_filtrados
        {where_sql}
        GROUP BY COALESCE({column}, 'sem_informacao')
        ORDER BY quantidade DESC, chave ASC
        """
        rows = db.execute(text(sql), params).mappings().all()
        return [
            FinanceiroPagamentosAgregado(
                chave=row["chave"],
                quantidade=row["quantidade"] or 0,
                valor_previsto=row["valor_previsto"] or Decimal("0"),
                valor_pago=row["valor_pago"] or Decimal("0"),
            )
            for row in rows
        ]

    def _build_where(self, filtros: FinanceiroPagamentosFiltros) -> Tuple[str, Dict[str, Any]]:
        conditions: List[str] = []
        params: Dict[str, Any] = {}

        if filtros.data_vencimento_inicio:
            conditions.append("data_vencimento >= :data_vencimento_inicio")
            params["data_vencimento_inicio"] = filtros.data_vencimento_inicio
        if filtros.data_vencimento_fim:
            conditions.append("data_vencimento <= :data_vencimento_fim")
            params["data_vencimento_fim"] = filtros.data_vencimento_fim
        if filtros.data_pagamento_inicio:
            conditions.append("data_pagamento::date >= :data_pagamento_inicio")
            params["data_pagamento_inicio"] = filtros.data_pagamento_inicio
        if filtros.data_pagamento_fim:
            conditions.append("data_pagamento::date <= :data_pagamento_fim")
            params["data_pagamento_fim"] = filtros.data_pagamento_fim
        if filtros.unidade and filtros.unidade not in TODAS_UNIDADES:
            conditions.append("unidade = :unidade")
            params["unidade"] = filtros.unidade
        if filtros.cpf:
            conditions.append("regexp_replace(COALESCE(cpf_cnpj, ''), '[^0-9]', '', 'g') LIKE :cpf")
            params["cpf"] = f"%{self._digits(filtros.cpf)}%"
        if filtros.nome:
            conditions.append("nome_paciente ILIKE :nome")
            params["nome"] = f"%{filtros.nome}%"
        if filtros.venda_id:
            conditions.append("venda_id = :venda_id")
            params["venda_id"] = filtros.venda_id
        if filtros.documento_venda:
            conditions.append("documento_venda ILIKE :documento_venda")
            params["documento_venda"] = f"%{filtros.documento_venda}%"
        if filtros.forma_pagamento_id:
            conditions.append("forma_pagamento_id = :forma_pagamento_id")
            params["forma_pagamento_id"] = filtros.forma_pagamento_id
        if filtros.tipo_odontograma:
            conditions.append("tipo_odontograma ILIKE :tipo_odontograma")
            params["tipo_odontograma"] = f"%{filtros.tipo_odontograma}%"

        self._add_list_filter(conditions, params, "status_normalizado", filtros.status, "status")
        self._add_list_filter(conditions, params, "tipo", filtros.tipo, "tipo")

        if not conditions:
            return "", params

        return "WHERE " + " AND ".join(conditions), params

    def _add_list_filter(
        self,
        conditions: List[str],
        params: Dict[str, Any],
        column: str,
        values: Optional[Sequence[str]],
        prefix: str,
    ) -> None:
        normalized = [
            value.strip().lower()
            for value in (values or [])
            if value and value.strip().lower() not in {"todos", "todas"}
        ]
        if not normalized:
            return

        placeholders = []
        for index, value in enumerate(normalized):
            key = f"{prefix}_{index}"
            placeholders.append(f":{key}")
            params[key] = value

        conditions.append(f"{column} IN ({', '.join(placeholders)})")

    def _build_order(self, order_by: str, order_dir: str) -> str:
        column = ORDER_BY_MAP.get(order_by, "data_vencimento")
        direction = "ASC" if str(order_dir).lower() == "asc" else "DESC"
        return f"ORDER BY {column} {direction} NULLS LAST, tipo ASC, numero_parcela ASC NULLS LAST, origem_id ASC"

    @staticmethod
    def _digits(value: str) -> str:
        return "".join(ch for ch in value if ch.isdigit())

    def _row_to_item(self, row: Dict[str, Any]) -> FinanceiroPagamentoItem:
        return FinanceiroPagamentoItem(**dict(row))

    def _base_cte(self) -> str:
        return """
        WITH pagamentos_base AS (
            SELECT
                ('entrada:' || pve.id)::text AS item_key,
                'pre_vendas_entradas'::text AS origem,
                pve.id::integer AS origem_id,
                COALESCE(v.tipo_cobranca_inicial, 'entrada')::text AS tipo,
                v.id::integer AS venda_id,
                v.documento_venda::text AS documento_venda,
                p.paciente_id::integer AS paciente_id,
                p.nome_paciente::text AS nome_paciente,
                p.cpf_cnpj::text AS cpf_cnpj,
                COALESCE(v.unidade, pve.unidade, p.unidade)::text AS unidade,
                v.data_venda::date AS data_venda,
                COALESCE(tpo.nome, o.tipo, pve.tipo_odontograma, v.tipo_venda)::text AS tipo_odontograma,
                u.nome::text AS usuario_venda,
                pve.forma_pagamento_id::integer AS forma_pagamento_id,
                fp.nome::text AS forma_pagamento,
                0::integer AS numero_parcela,
                NULL::integer AS total_parcelas,
                COALESCE(pve.valor_solicitado, 0)::numeric AS valor_previsto,
                pve.valor_pago::numeric AS valor_pago,
                pve.expires_at::date AS data_vencimento,
                CASE WHEN LOWER(COALESCE(pve.status, '')) = 'pago' THEN pve.updated_at::timestamp ELSE NULL::timestamp END AS data_pagamento,
                CASE
                    WHEN LOWER(COALESCE(pve.status, '')) = 'pago' THEN 'pago'
                    WHEN LOWER(COALESCE(pve.status, '')) = 'cancelado' THEN 'cancelado'
                    WHEN LOWER(COALESCE(pve.status, '')) = 'expirado' THEN 'vencido'
                    WHEN v.status_venda = 'Cancelada' THEN 'cancelado'
                    WHEN pve.expires_at::date < CURRENT_DATE THEN 'vencido'
                    ELSE 'pendente'
                END::text AS status_normalizado,
                pve.status::text AS status_local,
                NULL::text AS status_delta,
                v.status_venda::text AS status_venda,
                v.carne_id::integer AS carne_id,
                fr_entrada.id::integer AS fatura_recorrente_id,
                NULL::integer AS fatura_avulsa_id,
                NULL::integer AS invoice_id,
                fr_entrada.subscription_id::text AS recurring_invoice_id,
                pve.checkout_id::text AS charge_id,
                pve.pre_venda_id::text AS pre_venda_id,
                pve.checkout_url::text AS checkout_url,
                NULL::text AS boleto_url,
                pve.created_at::timestamp AS criado_em,
                pve.updated_at::timestamp AS atualizado_em
            FROM pre_vendas_entradas pve
            LEFT JOIN vendas v ON v.pre_venda_id = pve.pre_venda_id
            LEFT JOIN pacientes p ON p.paciente_id = pve.paciente_id
            LEFT JOIN users u ON u.id = v.usuario_venda_id
            LEFT JOIN odontogramas o ON o.id = v.odontograma_id
            LEFT JOIN tipos_odontograma tpo ON tpo.nome = o.tipo AND tpo.ativo = true
            LEFT JOIN formas_pagamento fp ON fp.id = pve.forma_pagamento_id
            LEFT JOIN LATERAL (
                SELECT fr2.*
                FROM fatura_recorrente fr2
                WHERE fr2.venda_id = v.id
                ORDER BY fr2.id DESC
                LIMIT 1
            ) fr_entrada ON true

            UNION ALL

            SELECT
                ('carne:' || cpp.id)::text AS item_key,
                'carne_parcelas'::text AS origem,
                cpp.id::integer AS origem_id,
                'carne'::text AS tipo,
                v.id::integer AS venda_id,
                v.documento_venda::text AS documento_venda,
                p.paciente_id::integer AS paciente_id,
                COALESCE(p.nome_paciente, c.nome_cliente)::text AS nome_paciente,
                COALESCE(p.cpf_cnpj, c.documento_cliente)::text AS cpf_cnpj,
                COALESCE(v.unidade, p.unidade, c.unidade)::text AS unidade,
                v.data_venda::date AS data_venda,
                COALESCE(tpo_venda.nome, o.tipo, v.tipo_venda, tpo_carne.nome)::text AS tipo_odontograma,
                COALESCE(u_venda.nome, u_carne.nome)::text AS usuario_venda,
                NULL::integer AS forma_pagamento_id,
                c.metodo_cobranca::text AS forma_pagamento,
                cpp.numero_parcela::integer AS numero_parcela,
                c.total_parcelas::integer AS total_parcelas,
                COALESCE(cpp.valor_parcela, 0)::numeric AS valor_previsto,
                cpp.valor_pago::numeric AS valor_pago,
                cpp.data_vencimento::date AS data_vencimento,
                cpp.data_pagamento::timestamp AS data_pagamento,
                CASE
                    WHEN UPPER(COALESCE(cpp.status, '')) IN ('PAID', 'PAY') OR cpp.status IN ('Pago', 'Paga') THEN 'pago'
                    WHEN UPPER(COALESCE(cpp.status, '')) IN ('VOID', 'DELETED', 'CANCELED', 'CANCELLED') OR v.status_venda = 'Cancelada' THEN 'cancelado'
                    WHEN UPPER(COALESCE(cpp.status, '')) IN ('REFUND', 'REFUNDED') THEN 'estornado'
                    WHEN UPPER(COALESCE(cpp.status, '')) IN ('COUNTERCHARGE', 'CHARGEBACK') THEN 'disputa'
                    WHEN UPPER(COALESCE(cpp.status, '')) IN ('FAIL', 'FAILED', 'NOT_AUTHORIZED', 'NOT_APPROVED') THEN 'falha'
                    WHEN UPPER(COALESCE(cpp.status, '')) = 'UNCOLLECTIBLE' THEN 'vencido'
                    WHEN cpp.data_vencimento < CURRENT_DATE THEN 'vencido'
                    ELSE 'pendente'
                END::text AS status_normalizado,
                cpp.status::text AS status_local,
                cpp.status::text AS status_delta,
                v.status_venda::text AS status_venda,
                c.id::integer AS carne_id,
                NULL::integer AS fatura_recorrente_id,
                NULL::integer AS fatura_avulsa_id,
                NULL::integer AS invoice_id,
                c.recurring_invoice_id::text AS recurring_invoice_id,
                cpp.charge_id::text AS charge_id,
                v.pre_venda_id::text AS pre_venda_id,
                c.location_url::text AS checkout_url,
                cpp.boleto_url::text AS boleto_url,
                cpp.created_at::timestamp AS criado_em,
                COALESCE(cpp.data_pagamento, cpp.created_at)::timestamp AS atualizado_em
            FROM carne_parcelas cpp
            INNER JOIN carne_pagamento c ON c.id = cpp.carne_id
            LEFT JOIN LATERAL (
                SELECT v2.*
                FROM vendas v2
                WHERE v2.id = c.venda_id OR v2.carne_id = c.id
                ORDER BY CASE WHEN v2.id = c.venda_id THEN 0 ELSE 1 END, v2.id DESC
                LIMIT 1
            ) v ON true
            LEFT JOIN pacientes p ON p.paciente_id = v.paciente_id
            LEFT JOIN users u_venda ON u_venda.id = v.usuario_venda_id
            LEFT JOIN users u_carne ON (
                CASE WHEN c.criado_por ~ '^[0-9]+$' THEN c.criado_por::integer ELSE NULL END
            ) = u_carne.id
            LEFT JOIN odontogramas o ON o.id = v.odontograma_id
            LEFT JOIN tipos_odontograma tpo_venda ON tpo_venda.nome = o.tipo AND tpo_venda.ativo = true
            LEFT JOIN tipos_odontograma tpo_carne ON tpo_carne.id = c.tipo_odontograma_id

            UNION ALL

            SELECT
                ('venda_parcela:' || vp.id)::text AS item_key,
                'venda_parcelas'::text AS origem,
                vp.id::integer AS origem_id,
                CASE
                    WHEN fr.id IS NOT NULL THEN 'fatura_recorrente'
                    WHEN fa.id IS NOT NULL THEN 'fatura_avulsa'
                    ELSE 'parcela_venda'
                END::text AS tipo,
                v.id::integer AS venda_id,
                v.documento_venda::text AS documento_venda,
                p.paciente_id::integer AS paciente_id,
                p.nome_paciente::text AS nome_paciente,
                p.cpf_cnpj::text AS cpf_cnpj,
                COALESCE(v.unidade, p.unidade, o.unidade)::text AS unidade,
                v.data_venda::date AS data_venda,
                COALESCE(tpo.nome, o.tipo, v.tipo_venda)::text AS tipo_odontograma,
                u.nome::text AS usuario_venda,
                COALESCE(vp.forma_pagamento_id, v.forma_pagamento_id)::integer AS forma_pagamento_id,
                COALESCE(
                    fp_parcela.nome,
                    fp_venda.nome,
                    fa.forma_pagamento,
                    CASE integration.payment_method
                        WHEN 'ASAAS_PIX_AUTOMATIC' THEN 'Pix Recorrente'
                        WHEN 'ASAAS_CREDIT_CARD_RECURRENT' THEN 'Cartão recorrente Asaas'
                        WHEN 'ASAAS_BOLETO_INSTALLMENT' THEN 'Carnê Asaas'
                    END
                )::text AS forma_pagamento,
                vp.numero_parcela::integer AS numero_parcela,
                COALESCE(fr.total_parcelas, v.qtd_parcelas)::integer AS total_parcelas,
                COALESCE(vp.valor_parcela, 0)::numeric AS valor_previsto,
                CASE
                    WHEN resource.remote_status IN ('CONFIRMED', 'RECEIVED', 'RECEIVED_IN_CASH')
                    THEN COALESCE(vp.valor_pago, vp.valor_parcela)
                    ELSE vp.valor_pago
                END::numeric AS valor_pago,
                vp.data_vencimento::date AS data_vencimento,
                CASE
                    WHEN resource.remote_status IN ('CONFIRMED', 'RECEIVED', 'RECEIVED_IN_CASH')
                    THEN COALESCE(vp.data_pagamento, payment_event.paid_at, resource.last_event_at)
                    ELSE vp.data_pagamento
                END::timestamp AS data_pagamento,
                CASE
                    WHEN resource.remote_status IN ('CONFIRMED', 'RECEIVED', 'RECEIVED_IN_CASH')
                         AND COALESCE(vp.data_pagamento, payment_event.paid_at, resource.last_event_at)::date > vp.data_vencimento
                    THEN 'pago_em_atraso'
                    WHEN resource.remote_status IN ('CONFIRMED', 'RECEIVED', 'RECEIVED_IN_CASH') THEN 'pago'
                    WHEN resource.remote_status IN ('REFUNDED', 'PARTIALLY_REFUNDED', 'REFUND_REQUESTED', 'REFUND_IN_PROGRESS') THEN 'estornado'
                    WHEN resource.remote_status IN ('CHARGEBACK_REQUESTED', 'CHARGEBACK_DISPUTE', 'AWAITING_CHARGEBACK_REVERSAL') THEN 'disputa'
                    WHEN resource.remote_status IN ('CANCELLED', 'CANCELED') THEN 'cancelado'
                    WHEN resource.remote_status = 'OVERDUE' THEN 'vencido'
                    WHEN UPPER(COALESCE(vp.status_parcela, '')) IN ('PAGO', 'PAGA', 'PAID', 'PAY') THEN 'pago'
                    WHEN UPPER(COALESCE(vp.status_parcela, '')) IN ('CANCELADA', 'CANCELADO', 'CANCELED', 'CANCELLED', 'VOID', 'DELETED') OR v.status_venda = 'Cancelada' THEN 'cancelado'
                    WHEN UPPER(COALESCE(vp.status_parcela, '')) IN ('REFUND', 'REFUNDED') THEN 'estornado'
                    WHEN UPPER(COALESCE(vp.status_parcela, '')) IN ('COUNTERCHARGE', 'CHARGEBACK') THEN 'disputa'
                    WHEN UPPER(COALESCE(vp.status_parcela, '')) IN ('FAIL', 'FAILED', 'NOT_AUTHORIZED', 'NOT_APPROVED') THEN 'falha'
                    WHEN UPPER(COALESCE(vp.status_parcela, '')) = 'UNCOLLECTIBLE' THEN 'vencido'
                    WHEN vp.data_vencimento < CURRENT_DATE THEN 'vencido'
                    ELSE 'pendente'
                END::text AS status_normalizado,
                vp.status_parcela::text AS status_local,
                COALESCE(resource.remote_status, fr.status, fa.status, vp.status_parcela)::text AS status_delta,
                v.status_venda::text AS status_venda,
                NULL::integer AS carne_id,
                fr.id::integer AS fatura_recorrente_id,
                fa.id::integer AS fatura_avulsa_id,
                fa.invoice_id::integer AS invoice_id,
                fr.subscription_id::text AS recurring_invoice_id,
                COALESCE(fa.invoice_id::text, vp.documento_referencia)::text AS charge_id,
                v.pre_venda_id::text AS pre_venda_id,
                COALESCE(fr.checkout_url, fa.checkout_url)::text AS checkout_url,
                NULL::text AS boleto_url,
                vp.created_at::timestamp AS criado_em,
                vp.updated_at::timestamp AS atualizado_em
            FROM venda_parcelas vp
            INNER JOIN vendas v ON v.id = vp.venda_id
            INNER JOIN pacientes p ON p.paciente_id = v.paciente_id
            LEFT JOIN users u ON u.id = v.usuario_venda_id
            LEFT JOIN odontogramas o ON o.id = v.odontograma_id
            LEFT JOIN tipos_odontograma tpo ON tpo.nome = o.tipo AND tpo.ativo = true
            LEFT JOIN formas_pagamento fp_parcela ON fp_parcela.id = vp.forma_pagamento_id
            LEFT JOIN formas_pagamento fp_venda ON fp_venda.id = v.forma_pagamento_id
            LEFT JOIN asaas_sale_integrations integration
              ON integration.venda_id = v.id
            LEFT JOIN asaas_sale_payment_links payment_link
              ON payment_link.integration_id = integration.id
             AND payment_link.venda_id = v.id
             AND payment_link.numero_parcela = vp.numero_parcela
            LEFT JOIN asaas_sale_resources resource
              ON resource.id = payment_link.resource_id
             AND resource.resource_type = 'payment'
            LEFT JOIN (
                SELECT webhook.resource_id,
                       MIN(
                           COALESCE(
                               NULLIF(webhook.technical_data #>> '{payment,paymentDate}', '')::timestamptz,
                               NULLIF(webhook.technical_data #>> '{payment,confirmedDate}', '')::timestamptz,
                               NULLIF(webhook.technical_data #>> '{payment,clientPaymentDate}', '')::timestamptz,
                               NULLIF(webhook.technical_data ->> 'dateCreated', '')::timestamptz
                           )
                       ) AS paid_at
                FROM asaas_sale_webhook_events webhook
                WHERE webhook.status = 'processado'
                  AND webhook.event_type IN (
                      'PAYMENT_CONFIRMED',
                      'PAYMENT_RECEIVED',
                      'PAYMENT_RECEIVED_IN_CASH'
                  )
                GROUP BY webhook.resource_id
            ) payment_event
              ON payment_event.resource_id = resource.id
            LEFT JOIN LATERAL (
                SELECT fr2.*
                FROM fatura_recorrente fr2
                WHERE fr2.venda_id = v.id
                ORDER BY fr2.id DESC
                LIMIT 1
            ) fr ON true
            LEFT JOIN LATERAL (
                SELECT fa2.*
                FROM fatura_avulsa fa2
                WHERE fa2.venda_id = v.id
                ORDER BY fa2.id DESC
                LIMIT 1
            ) fa ON true
            LEFT JOIN LATERAL (
                SELECT fr2.id
                FROM fatura_recorrente fr2
                INNER JOIN vendas v2 ON v2.id = fr2.venda_id
                INNER JOIN venda_parcelas vp2 ON vp2.venda_id = v2.id
                WHERE fr.id IS NULL
                  AND v2.id <> v.id
                  AND v2.paciente_id = v.paciente_id
                  AND COALESCE(v2.odontograma_id, -1) = COALESCE(v.odontograma_id, -1)
                  AND v2.valor_liquido_total = v.valor_liquido_total
                  AND v2.qtd_parcelas = v.qtd_parcelas
                  AND vp2.numero_parcela = vp.numero_parcela
                  AND vp2.data_vencimento = vp.data_vencimento
                  AND vp2.valor_parcela = vp.valor_parcela
                ORDER BY fr2.id DESC
                LIMIT 1
            ) fr_shadow ON true
            LEFT JOIN LATERAL (
                SELECT c2.id
                FROM carne_pagamento c2
                LEFT JOIN vendas v2 ON v2.id = c2.venda_id OR v2.carne_id = c2.id
                WHERE (
                    v2.paciente_id = v.paciente_id
                    OR regexp_replace(COALESCE(c2.documento_cliente, ''), '[^0-9]', '', 'g') = regexp_replace(COALESCE(p.cpf_cnpj, ''), '[^0-9]', '', 'g')
                )
                  AND c2.valor_total = v.valor_liquido_total
                  AND c2.valor_parcela = vp.valor_parcela
                  AND c2.total_parcelas = v.qtd_parcelas
                ORDER BY ABS(EXTRACT(EPOCH FROM (c2.data_criacao - v.created_at))) ASC NULLS LAST, c2.id DESC
                LIMIT 1
            ) carne_shadow ON true
            WHERE NOT EXISTS (
                SELECT 1
                FROM carne_pagamento c2
                WHERE c2.venda_id = v.id OR c2.id = v.carne_id
            )
            AND (fr.id IS NOT NULL OR fr_shadow.id IS NULL)
            AND (fr.id IS NOT NULL OR carne_shadow.id IS NULL)
        ),
        pagamentos_filtrados AS (
            SELECT
                *,
                CASE
                    WHEN data_vencimento IS NULL THEN 0
                    WHEN status_normalizado IN ('pago', 'pago_em_atraso', 'cancelado', 'estornado') AND data_pagamento IS NOT NULL AND data_pagamento::date > data_vencimento
                        THEN data_pagamento::date - data_vencimento
                    WHEN status_normalizado NOT IN ('pago', 'pago_em_atraso', 'cancelado', 'estornado') AND data_vencimento < CURRENT_DATE
                        THEN CURRENT_DATE - data_vencimento
                    ELSE 0
                END::integer AS dias_atraso
            FROM pagamentos_base
        )
        """
