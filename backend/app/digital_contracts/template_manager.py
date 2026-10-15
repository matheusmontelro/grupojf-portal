# backend/app/digital_contracts/template_manager.py
"""
Gerenciador de templates de contratos digitais
"""
import json
import logging
from typing import Optional, Dict, List
from datetime import datetime
from sqlalchemy.orm import Session
from psycopg2.extras import RealDictCursor  # Adicionar import para cursor de dicionário
from ..database.db import DatabaseConnection
# from ..models.contract_templates import ContractTemplate, ContractTemplateVariable  # Removido - causando erro de circular import
from .templates import CONTRACT_TEMPLATE, render_contract

logger = logging.getLogger(__name__)

class TemplateManager:
    """
    Gerencia templates de contratos digitais
    """
    
    def __init__(self):
        self.default_template = CONTRACT_TEMPLATE
    
    def get_template_for_odontograma(self, odontograma_id: int) -> tuple[str, dict]:
        """
        Busca o template apropriado para um odontograma específico
        Retorna: (template_html, template_config)
        """
        logger.info(f"Buscando template para odontograma_id={odontograma_id}")
        
        with DatabaseConnection() as conn:
            # Usar cursor que retorna dicionários para facilitar o acesso por nome de coluna
            cursor = conn.cursor(cursor_factory=RealDictCursor)  # Corrigido para psycopg2
            
            # Buscar tipo de odontograma
            cursor.execute("""
                SELECT t.id as tipo_id, t.nome as tipo_nome
                FROM odontogramas o
                LEFT JOIN tipos_odontograma t ON o.tipo = t.nome
                WHERE o.id = %s
            """, (odontograma_id,))
            
            result = cursor.fetchone()
            if not result:
                logger.warning(f"Odontograma {odontograma_id} não encontrado ou sem tipo no cadastro.")
                return self.default_template, {}
            
            tipo_id = result.get('tipo_id')
            tipo_nome = result.get('tipo_nome')

            if tipo_id is None:
                logger.warning(f"Odontograma {odontograma_id} tem o nome de tipo '{tipo_nome}', mas este tipo não foi encontrado na tabela 'tipos_odontograma' ou não possui um ID válido.")
                # Decide se quer usar um template padrão ou levantar um erro.
                # Por enquanto, usa o default_template definido na classe.
                return self.default_template, {}
            
            logger.info(f"Tipo de odontograma: {tipo_nome} (id={tipo_id})")
            logger.info(f"📍 DEBUG: Entrando em get_template_for_odontograma com tipo_id={tipo_id}")
            
            # DESABILITADO: Busca no banco de dados para evitar erro de import circular
            # Por enquanto, vamos direto para o fallback de templates hardcoded
            
            # # Buscar template específico para o tipo
            # if tipo_id:
            #     cursor.execute("""
            #         SELECT id, template_html, template_config
            #         FROM contract_templates
            #         WHERE tipo_odontograma_id = %s 
            #         AND is_active = true
            #         ORDER BY version DESC
            #         LIMIT 1
            #     """, (tipo_id,))
            #     
            #     template_data = cursor.fetchone()
            #     if template_data:
            #         template_id, template_html, template_config = template_data
            #         
            #         # Incrementar contador de uso
            #         cursor.execute("""
            #             UPDATE contract_templates 
            #             SET usage_count = usage_count + 1,
            #                 last_used_at = NOW()
            #             WHERE id = %s
            #         """, (template_id,))
            #         conn.commit()
            #         
            #         logger.info(f"Template customizado encontrado: id={template_id}")
            #         return template_html, template_config or {}
            # 
            # # Se não houver template específico, buscar template padrão
            # cursor.execute("""
            #     SELECT id, template_html, template_config
            #     FROM contract_templates
            #     WHERE is_default = true AND is_active = true
            #     ORDER BY version DESC
            #     LIMIT 1
            # """)
            # 
            # default_data = cursor.fetchone()
            # if default_data:
            #     template_id, template_html, template_config = default_data
            #     logger.info(f"Usando template padrão: id={template_id}")
            #     return template_html, template_config or {}
            
            # Fallback para template hardcoded baseado no tipo
            logger.info(f"Usando template hardcoded para tipo_id={tipo_id}")
            from .templates import get_template_by_tipo_id # Import local para evitar circular
            
            template = get_template_by_tipo_id(tipo_id) # get_template_by_tipo_id deve lidar com tipo_id não encontrado se necessário.
            logger.info(f"📍 DEBUG: Template selecionado tem {len(template)} caracteres")
            logger.info(f"📍 DEBUG: Template contém 'ORTODÔNTICOS'? {'ORTODÔNTICOS' in template}")
            return template, {} # Assume que config é {} para templates hardcoded por enquanto
    
    def render_contract_with_template(self, odontograma_id: int, dados: dict) -> str:
        """
        Renderiza o contrato usando o template apropriado
        """
        template_html, template_config = self.get_template_for_odontograma(odontograma_id)
        
        # Aplicar configurações do template
        if template_config: # template_config é {} por enquanto devido ao fallback acima
            # Exemplo: ocultar seção de dependentes
            if not template_config.get('show_dependents', True):
                dados['dependentes_rows'] = ''
                dados['dependentes_mobile'] = ''
            
            # Exemplo: adicionar cláusulas customizadas
            custom_clauses = template_config.get('custom_clauses', [])
            if custom_clauses:
                # TODO: Implementar inserção de cláusulas customizadas
                pass
        
        # Se o template_html for o mesmo que o self.default_template (CONTRACT_AKIMAIS_TEMPLATE)
        # E a função render_contract de .templates for a que deve ser usada para ele.
        # A lógica atual em get_template_for_odontograma já retorna o template string diretamente.
        
        # A função render_contract em .templates já tem a lógica de _get_default_values e .format
        # No entanto, a sua função render_contract em templates.py usa uma variável global CONTRATO_AKIMAIS_TEMPLATE
        # que é manipulada por render_contract_by_tipo. Isso é um pouco confuso.
        # A forma mais simples aqui é garantir que `render_contract` de .templates seja chamada com os `dados`
        # e o template correto já selecionado.
        
        # A função `render_contract_by_tipo` em `templates.py` já faz a seleção do template e chama `render_contract`.
        # Então, se `get_template_for_odontograma` está apenas retornando o HTML do template correto,
        # precisamos ter uma forma de passar esse HTML para a função de renderização principal, ou
        # a lógica de `_get_default_values` e `format` precisa ser replicada/chamada aqui.

        # Dado que a lógica de renderização principal (com _get_default_values) está em `_render_template` e
        # em `render_contract` (no arquivo templates.py), e que `get_template_by_tipo_id`
        # retorna o HTML string, a maneira mais consistente seria usar _render_template.
        
        # No entanto, a sua `render_contract` (de templates.py) já tem a lógica de `defaults` e `format`.
        # Se `get_template_by_tipo_id` retorna o template string correto,
        # e `dados` já contém `valor_base_contrato` etc., então chamar `render_contract` passando
        # os `dados` e fazendo com que `render_contract` use o `template_html` que passamos seria o ideal.

        # A atual `render_contract` em `templates.py` está ligada ao CONTRATO_AKIMAIS_TEMPLATE globalmente.
        # A `render_contract_by_tipo` em `templates.py` tenta contornar isso.
        # Para simplificar aqui, vamos usar o _render_template que não depende da variável global.
        
        # return self._render_template(template_html, dados)
        
        # OU, se a intenção é sempre usar a lógica de templates.py/render_contract
        # e templates.py/get_template_by_tipo_id:
        from .templates import render_contract_by_tipo, get_template_by_tipo_id
        
        # Primeiro, obter o tipo_id como já está fazendo
        # (A lógica de get_template_for_odontograma já pega tipo_id e tipo_nome)
        # Precisamos do tipo_id para passar para render_contract_by_tipo
        
        # Re-fetch tipo_id para clareza, embora já o tenhamos de get_template_for_odontograma
        current_tipo_id = None
        with DatabaseConnection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT t.id FROM odontogramas o JOIN tipos_odontograma t ON o.tipo = t.nome WHERE o.id = %s", (odontograma_id,))
            res = cursor.fetchone()
            if res:
                current_tipo_id = res['id']

        if current_tipo_id is None: # Se não encontrar tipo_id, não pode usar render_contract_by_tipo
             logger.error(f"Não foi possível determinar o tipo_id para odontograma {odontograma_id} para render_contract_by_tipo.")
             # Fallback para renderização genérica ou erro
             return self._render_template(self.default_template, dados) # Usa o default da classe

        # Agora chame a função de renderização de templates.py que lida com a seleção de template
        return render_contract_by_tipo(dados, current_tipo_id)

    
    def _render_template(self, template: str, dados: dict) -> str:
        """
        Renderiza um template substituindo as variáveis
        """
        # Preparar dados com valores padrão
        defaults = self._get_default_values(dados)
        
        # Fazer a substituição
        try:
            return template.format(**defaults)
        except KeyError as e:
            logger.error(f"Variável não encontrada no template: {e}")
            # Tentar renderizar com valores vazios para variáveis faltantes
            import re
            missing_vars = re.findall(r'\{(\w+)\}', template)
            for var in missing_vars:
                if var not in defaults:
                    defaults[var] = ''
            return template.format(**defaults)
    
    def _get_default_values(self, dados: dict) -> dict:
        """
        Prepara valores padrão para o template.
        Esta função é uma cópia da lógica dentro de render_contract em templates.py
        Seria melhor centralizar isso.
        """
        from datetime import datetime
        
        # Calcular valores derivados
        valor_total = float(dados.get('valor_total', 0))
        # Usa 'qtd_parcelas' do frontend (que deve ser o número correto de parcelas do contrato)
        qtd_parcelas_final = int(dados.get('qtd_parcelas', 1)) 
        
        valor_parcela_final = 0
        # Usa 'valor_base_contrato' do frontend se disponível (este é o valor da parcela/mensalidade)
        valor_base_contrato = dados.get('valor_base_contrato') 

        if valor_base_contrato is not None:
            valor_parcela_final = float(valor_base_contrato)
        elif qtd_parcelas_final > 0:
            valor_parcela_final = valor_total / qtd_parcelas_final
        else: # qtd_parcelas_final é 0 ou inválido, e não temos valor_base_contrato
            valor_parcela_final = valor_total
            if qtd_parcelas_final <= 0: qtd_parcelas_final = 1 # Evitar divisão por zero e garantir ao menos 1 parcela

        # Formatar valores monetários
        valor_total_formatado = f"{valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        valor_parcela_formatado = f"{valor_parcela_final:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # Preparar HTML da assinatura
        signature_html = ""
        if dados.get('assinatura_base64'):
            signature_html = f'<img src="{dados["assinatura_base64"]}" class="signature-image" alt="Assinatura do paciente" />'
        
        # Valores padrão
        defaults = {
            'vendedor_nome': dados.get('vendedor_nome', 'VENDEDOR'),
            'empresa_razao_social': 'J&F ODONTOLOGIA 2016 LTDA',
            'empresa_cnpj': '24.476.639/0001-06',
            'empresa_cidade': 'Nova Iguaçu',
            'empresa_endereco_completo': 'Rua Otávio Tarquino Nº 173 - Centro - CEP: 26215-342',
            'paciente_nome': dados.get('paciente_nome', ''),
            'paciente_cpf': dados.get('paciente_cpf', ''),
            'paciente_data_nascimento': dados.get('paciente_data_nascimento', ''),
            'paciente_rg': dados.get('paciente_rg', ''),
            'paciente_orgao_expedidor': dados.get('paciente_orgao_expedidor', 'DETRAN'),
            'paciente_endereco': dados.get('endereco', '') or dados.get('paciente_endereco', ''),
            'paciente_cep': dados.get('paciente_cep', ''),
            'paciente_bairro': dados.get('paciente_bairro', ''),
            'paciente_cidade': dados.get('paciente_cidade', ''),
            'paciente_estado': dados.get('paciente_estado', ''),
            'paciente_telefone1': dados.get('paciente_telefone1', ''),
            'paciente_telefone2': dados.get('paciente_telefone2', ''),
            'paciente_email': dados.get('paciente_email', ''),
            'observacao_tratamentos': dados.get('observacao_tratamentos', 'PACIENTE NÃO INFORMOU INTERESSE EM TRATAMENTOS'),
            'valor_total': valor_total,
            'valor_total_formatado': valor_total_formatado,
            'qtd_parcelas': qtd_parcelas_final,
            'valor_parcela': valor_parcela_final,
            'valor_parcela_formatado': valor_parcela_formatado,
            'dia_vencimento': dados.get('dia_vencimento', '10'),
            'forma_pagamento': dados.get('forma_pagamento', 'BOLETO'),
            'cidade_contrato': dados.get('cidade_contrato', 'Rio de Janeiro'),
            'data_contrato': datetime.now().strftime("%d de %B de %Y").replace(
                'January', 'janeiro').replace('February', 'fevereiro').replace('March', 'março').replace(
                'April', 'abril').replace('May', 'maio').replace('June', 'junho').replace(
                'July', 'julho').replace('August', 'agosto').replace('September', 'setembro').replace(
                'October', 'outubro').replace('November', 'novembro').replace('December', 'dezembro'),
            'signature_html': signature_html,
        }
        
        # Adicionar dependentes
        defaults.update(self._prepare_dependents(dados))
        
        # Mesclar com dados fornecidos (garante que os dados originais não sejam sobrescritos pelos defaults se já existirem)
        # A ordem é importante: o que está em `dados` prevalece sobre `defaults`
        final_data_for_template = {**defaults, **dados} 
        # Mas para os campos calculados, queremos que os calculados aqui (em defaults) sejam usados
        final_data_for_template['valor_total'] = valor_total
        final_data_for_template['valor_total_formatado'] = valor_total_formatado
        final_data_for_template['qtd_parcelas'] = qtd_parcelas_final
        final_data_for_template['valor_parcela'] = valor_parcela_final
        final_data_for_template['valor_parcela_formatado'] = valor_parcela_formatado
        final_data_for_template['signature_html'] = signature_html
        final_data_for_template.update(self._prepare_dependents(dados)) # Re-aplicar dependentes para garantir que usem o `dados` original

        return final_data_for_template # Retorna o dicionário preparado
    
    def _prepare_dependents(self, dados: dict) -> dict:
        """
        Prepara HTML dos dependentes
        """
        dependentes_rows = ""
        dependentes_mobile = ""
        dependentes_count = 0
        
        for i in range(1, 6):
            dependente_nome = dados.get(f'dependente_{i}_nome', '')
            dependente_cpf = dados.get(f'dependente_{i}_cpf', '')
            dependente_nascimento = dados.get(f'dependente_{i}_nascimento', '')
            
            if dependente_nome and dependente_nome.strip():
                dependentes_count += 1
                
                # Desktop
                dependentes_rows += f"""
                <tr>
                    <td class="number-cell">{dependentes_count}</td>
                    <td style="font-weight: bold;">NOME</td>
                    <td style="font-weight: bold;">CPF</td>
                    <td style="font-weight: bold;">DATA DE NASCIMENTO</td>
                </tr>
                <tr>
                    <td></td>
                    <td>{dependente_nome}</td>
                    <td>{dependente_cpf}</td>
                    <td>{dependente_nascimento}</td>
                </tr>
                """
                
                # Mobile
                dependentes_mobile += f"""
                <div class="mobile-dependente">
                    <div class="mobile-dependente-header">DEPENDENTE {dependentes_count}</div>
                    <div class="mobile-dependente-content">
                        <div class="mobile-field">
                            <div class="mobile-field-label">NOME</div>
                            <div class="mobile-field-value">{dependente_nome}</div>
                        </div>
                        <div class="mobile-field">
                            <div class="mobile-field-label">CPF</div>
                            <div class="mobile-field-value">{dependente_cpf}</div>
                        </div>
                        <div class="mobile-field">
                            <div class="mobile-field-label">DATA DE NASCIMENTO</div>
                            <div class="mobile-field-value">{dependente_nascimento}</div>
                        </div>
                    </div>
                </div>
                """
        
        # Se não houver dependentes
        if not dependentes_rows:
            dependentes_rows = """
            <tr>
                <td colspan="4" style="text-align: center; font-style: italic; color: #666;">
                    Nenhum dependente vinculado
                </td>
            </tr>
            """
            
        if not dependentes_mobile:
            dependentes_mobile = """
            <div style="text-align: center; font-style: italic; color: #666; padding: 20px;">
                Nenhum dependente vinculado
            </div>
            """
        
        return {
            'dependentes_rows': dependentes_rows,
            'dependentes_mobile': dependentes_mobile
        }

# Instância global
template_manager = TemplateManager()