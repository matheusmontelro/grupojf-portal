# Guia de Templates de Contratos Digitais

## 📋 Índice
1. [Nomenclatura de Templates](#nomenclatura)
2. [Como Adicionar Novos Templates](#como-adicionar)
3. [Estrutura do Template HTML](#estrutura-html)
4. [Variáveis Disponíveis](#variaveis)
5. [Exemplos Práticos](#exemplos)

## 🏷️ Nomenclatura de Templates {#nomenclatura}

### Padrões de Nome e Slug

#### Para o campo `name` (Nome de Exibição):
```
[Tipo] - [Especialidade] [Características]
```

Exemplos:
- `Contrato Padrão - Odontologia Geral`
- `Contrato Ortodôntico - Tratamento Completo`
- `Contrato Pediátrico - Atendimento Infantil`
- `Contrato VIP - Implantes Premium`
- `Contrato Empresarial - Plano Corporativo`

#### Para o campo `slug` (Identificador URL):
```
contrato-[tipo]-[especialidade]-[versao]
```

Exemplos:
- `contrato-padrao-odontologia`
- `contrato-ortodontico-completo`
- `contrato-pediatrico-infantil`
- `contrato-vip-implantes`
- `contrato-empresarial-corporativo`

### Regras de Nomenclatura:
1. **Slug**: Sempre em minúsculas, sem acentos, separado por hífens
2. **Nome**: Claro e descritivo, indicando o tipo de contrato
3. **Versão**: Pode adicionar sufixo como `-v2` para novas versões

## 🚀 Como Adicionar Novos Templates {#como-adicionar}

### Método 1: Via API (Recomendado para Produção)

```bash
# 1. Criar arquivo JSON com o template
cat > novo_template.json << 'EOF'
{
  "name": "Contrato Implante Dentário - Premium",
  "slug": "contrato-implante-premium",
  "description": "Template para contratos de implantes com garantia estendida",
  "tipo_odontograma_id": null,
  "template_html": "<!-- HTML do template aqui -->",
  "template_config": {
    "show_dependents": false,
    "show_witnesses": true,
    "highlight_warranty": true,
    "warranty_years": 5
  },
  "is_default": false
}
EOF

# 2. Enviar via API
curl -X POST http://localhost:8001/api/contract-templates/ \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d @novo_template.json
```

### Método 2: Via Script Python

```python
# criar_template_implante.py
from app.database.db import DatabaseConnection
import json

def criar_template_implante():
    template_html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Contrato de Implante Dentário</title>
    <style>
        /* Estilos específicos para implante */
        .warranty-box {
            background: #28a745;
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <!-- Conteúdo do template -->
</body>
</html>
    """
    
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO contract_templates (
                name, slug, description, template_html, 
                template_config, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            "Contrato Implante Dentário - Premium",
            "contrato-implante-premium",
            "Template para implantes com garantia estendida",
            template_html,
            json.dumps({
                "show_warranty": True,
                "warranty_years": 5,
                "show_payment_plan": True
            }),
            "admin"
        ))
        conn.commit()

if __name__ == "__main__":
    criar_template_implante()
```

### Método 3: Via SQL Direto

```sql
-- inserir_template_clareamento.sql
INSERT INTO contract_templates (
    name,
    slug,
    description,
    tipo_odontograma_id,
    template_html,
    template_config,
    created_by
) VALUES (
    'Contrato Clareamento Dental - Express',
    'contrato-clareamento-express',
    'Template para tratamento de clareamento rápido',
    (SELECT id FROM tipos_odontograma WHERE nome LIKE '%Clareamento%' LIMIT 1),
    '<!-- HTML do template -->',
    '{
        "duration_days": 15,
        "sessions_included": 3,
        "home_kit_included": true
    }',
    'system'
);
```

## 📄 Estrutura do Template HTML {#estrutura-html}

### Estrutura Básica Recomendada:

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contrato [Tipo]</title>
    <style>
        /* Estilos base - copiar do template padrão */
        body { font-family: Arial, sans-serif; }
        .container { max-width: 210mm; margin: 0 auto; }
        
        /* Estilos específicos do template */
        .highlight-[tipo] {
            /* Personalizações */
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- 1. Cabeçalho -->
        <div class="header">
            <h1>CONTRATO DE [TIPO DE SERVIÇO]</h1>
            <p>Vendedor: {vendedor_nome}</p>
        </div>
        
        <!-- 2. Dados da Empresa -->
        <section class="empresa">
            <h2>CONTRATADA</h2>
            <p>{empresa_razao_social} - CNPJ: {empresa_cnpj}</p>
        </section>
        
        <!-- 3. Dados do Paciente -->
        <section class="paciente">
            <h2>CONTRATANTE</h2>
            <p>Nome: {paciente_nome}</p>
            <p>CPF: {paciente_cpf}</p>
            <!-- Mais campos... -->
        </section>
        
        <!-- 4. Objeto do Contrato -->
        <section class="objeto">
            <h2>OBJETO DO CONTRATO</h2>
            <!-- Descrição específica do serviço -->
        </section>
        
        <!-- 5. Valores e Pagamento -->
        <section class="pagamento">
            <h2>INVESTIMENTO</h2>
            <p>Valor Total: R$ {valor_total:,.2f}</p>
            <p>Parcelas: {qtd_parcelas}x de R$ {valor_parcela:,.2f}</p>
        </section>
        
        <!-- 6. Cláusulas Específicas -->
        <section class="clausulas">
            <!-- Cláusulas do contrato -->
        </section>
        
        <!-- 7. Assinaturas -->
        <section class="assinaturas">
            {signature_html}
            <p>{paciente_nome}</p>
        </section>
    </div>
</body>
</html>
```

## 📊 Variáveis Disponíveis {#variaveis}

### Variáveis do Paciente:
- `{paciente_nome}` - Nome completo
- `{paciente_cpf}` - CPF formatado
- `{paciente_rg}` - RG
- `{paciente_data_nascimento}` - Data de nascimento
- `{paciente_email}` - E-mail
- `{paciente_telefone1}` - Telefone principal
- `{paciente_telefone2}` - Telefone secundário
- `{paciente_endereco}` - Endereço
- `{paciente_bairro}` - Bairro
- `{paciente_cidade}` - Cidade
- `{paciente_estado}` - Estado (UF)
- `{paciente_cep}` - CEP

### Variáveis da Empresa:
- `{empresa_razao_social}` - Nome da empresa
- `{empresa_cnpj}` - CNPJ
- `{empresa_cidade}` - Cidade da empresa
- `{empresa_endereco_completo}` - Endereço completo

### Variáveis Financeiras:
- `{valor_total}` - Valor total do contrato
- `{qtd_parcelas}` - Quantidade de parcelas
- `{valor_parcela}` - Valor de cada parcela
- `{valor_mensalidade}` - Valor mensal (para contratos)
- `{dia_vencimento}` - Dia de vencimento
- `{forma_pagamento}` - Forma de pagamento

### Variáveis do Sistema:
- `{vendedor_nome}` - Nome do vendedor
- `{data_contrato}` - Data do contrato formatada
- `{cidade_contrato}` - Cidade do contrato
- `{signature_html}` - HTML da assinatura digital
- `{observacao_tratamentos}` - Observações sobre tratamentos

### Variáveis de Dependentes:
- `{dependente_1_nome}` até `{dependente_5_nome}`
- `{dependente_1_cpf}` até `{dependente_5_cpf}`
- `{dependente_1_nascimento}` até `{dependente_5_nascimento}`
- `{dependentes_rows}` - HTML da tabela de dependentes
- `{dependentes_mobile}` - HTML mobile dos dependentes

## 💡 Exemplos Práticos {#exemplos}

### Exemplo 1: Template para Clareamento

```python
# template_clareamento.py
TEMPLATE_CLAREAMENTO = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Contrato de Clareamento Dental</title>
    <style>
        .clareamento-destaque {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            margin: 20px 0;
        }
        
        .antes-depois {
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
        }
        
        .resultado-box {
            border: 2px solid #667eea;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="clareamento-destaque">
            <h1>✨ CONTRATO DE CLAREAMENTO DENTAL ✨</h1>
            <p>Transforme seu sorriso em 15 dias!</p>
        </div>
        
        <!-- Conteúdo específico para clareamento -->
        <div class="antes-depois">
            <div class="resultado-box">
                <h3>ANTES</h3>
                <p>Dentes amarelados<br>ou manchados</p>
            </div>
            <div class="resultado-box">
                <h3>DEPOIS</h3>
                <p>Sorriso branco<br>e radiante!</p>
            </div>
        </div>
        
        <section>
            <h2>TRATAMENTO INCLUI:</h2>
            <ul>
                <li>✅ Avaliação inicial completa</li>
                <li>✅ 3 sessões de clareamento em consultório</li>
                <li>✅ Kit de clareamento caseiro</li>
                <li>✅ Acompanhamento por 30 dias</li>
                <li>✅ Garantia de resultado</li>
            </ul>
        </section>
        
        <!-- Restante do contrato... -->
    </div>
</body>
</html>
"""

# Função para inserir
def inserir_template_clareamento():
    from app.database.db import DatabaseConnection
    import json
    
    with DatabaseConnection() as conn:
        cursor = conn.cursor()
        
        # Buscar tipo de odontograma relacionado
        cursor.execute("""
            SELECT id FROM tipos_odontograma 
            WHERE nome LIKE '%Clareamento%' 
            LIMIT 1
        """)
        tipo_id = cursor.fetchone()
        
        cursor.execute("""
            INSERT INTO contract_templates (
                name, slug, description, tipo_odontograma_id,
                template_html, template_config, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                template_html = EXCLUDED.template_html,
                template_config = EXCLUDED.template_config,
                version = contract_templates.version + 1,
                updated_at = NOW()
        """, (
            "Contrato Clareamento Dental - Express",
            "contrato-clareamento-express",
            "Template moderno para tratamento de clareamento",
            tipo_id[0] if tipo_id else None,
            TEMPLATE_CLAREAMENTO,
            json.dumps({
                "theme": "gradient",
                "show_results": True,
                "warranty_days": 180,
                "sessions": 3
            }),
            "admin"
        ))
        conn.commit()
        print("✅ Template de clareamento inserido!")
```

### Exemplo 2: Template para Prótese

```python
# template_protese.py
TEMPLATE_PROTESE = """
<!-- Template específico para próteses com detalhamento técnico -->
<!DOCTYPE html>
<html>
<head>
    <style>
        .technical-specs {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 20px;
            margin: 20px 0;
        }
        
        .warranty-seal {
            position: relative;
            display: inline-block;
            background: gold;
            padding: 20px;
            border-radius: 50%;
            text-align: center;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <!-- Conteúdo específico para prótese -->
    <div class="technical-specs">
        <h3>ESPECIFICAÇÕES TÉCNICAS DA PRÓTESE</h3>
        <ul>
            <li>Material: Porcelana Premium / Zircônia</li>
            <li>Laboratório: Certificado ISO 9001</li>
            <li>Garantia: 5 anos contra defeitos</li>
            <li>Ajustes inclusos: Ilimitados no primeiro ano</li>
        </ul>
    </div>
    
    <div class="warranty-seal">
        <span>GARANTIA<br>5 ANOS</span>
    </div>
</body>
</html>
"""
```

### Exemplo 3: Associar Template a Tipo de Odontograma

```sql
-- Associar template ao tipo específico
UPDATE contract_templates 
SET tipo_odontograma_id = (
    SELECT id FROM tipos_odontograma 
    WHERE nome = 'Contrato Ortodôntico'
)
WHERE slug = 'contrato-ortodontico';

-- Criar tipo de odontograma se não existir
INSERT INTO tipos_odontograma (nome, descricao, ativo)
VALUES ('Clareamento Express', 'Tratamento de clareamento rápido', true)
ON CONFLICT (nome) DO NOTHING;
```

## 🔧 Manutenção de Templates

### Atualizar Template Existente:
```python
# Via API
curl -X PUT http://localhost:8001/api/contract-templates/1 \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "template_html": "<!-- HTML atualizado -->",
    "template_config": {"version": "2.0"}
  }'
```

### Desativar Template:
```sql
UPDATE contract_templates 
SET is_active = false, 
    updated_at = NOW(),
    updated_by = 'admin'
WHERE slug = 'contrato-antigo';
```

### Definir Template Padrão:
```sql
-- Remover padrão anterior
UPDATE contract_templates SET is_default = false;

-- Definir novo padrão
UPDATE contract_templates 
SET is_default = true 
WHERE slug = 'contrato-padrao-odontologia-v2';
```

## 📝 Checklist para Novo Template

- [ ] Definir nome descritivo e slug único
- [ ] Criar HTML com todas as seções necessárias
- [ ] Incluir todas as variáveis necessárias
- [ ] Testar renderização com dados de exemplo
- [ ] Definir configurações no template_config
- [ ] Associar ao tipo de odontograma (se aplicável)
- [ ] Documentar particularidades do template
- [ ] Fazer backup antes de substituir template ativo
- [ ] Testar em ambiente de desenvolvimento primeiro

## 🚨 Dicas Importantes

1. **Sempre teste o template** antes de ativar em produção
2. **Use o preview da API** para verificar a renderização
3. **Mantenha versões anteriores** para rollback se necessário
4. **Documente mudanças** no campo description
5. **Use template_config** para flags e configurações
6. **Evite JavaScript** nos templates para compatibilidade
7. **Otimize para impressão** com media queries CSS
8. **Considere mobile** para visualização no celular

## 🆘 Troubleshooting

### Template não aparece:
- Verificar se está ativo: `is_active = true`
- Verificar associação com tipo_odontograma_id
- Verificar se há template padrão definido

### Variáveis não substituídas:
- Verificar ortografia exata da variável
- Verificar se o dado existe no banco
- Usar preview para debug

### Erro ao salvar:
- Verificar se o slug é único
- Verificar sintaxe HTML
- Verificar JSON do template_config
