# 🏥 Configuração do Template Contrato Odontológico + Akimais

## 📋 Visão Geral

Transformamos o template CONTRACT_TEMPLATE original em um template de banco de dados configurável para o tipo "Contrato Odontológico + Akimais Saúde".

## 🚀 Como Configurar

### Opção 1: Usando o Script Python (Recomendado)

```bash
cd backend
python scripts/add_akimais_template.py
```

O script irá:
1. Procurar automaticamente o tipo "Akimais" no banco
2. Criar o template com todas as configurações
3. Definir como template padrão para esse tipo

### Opção 2: Usando SQL Direto

```bash
cd backend
psql -U seu_usuario -d sua_database -f migrations/insert_akimais_template.sql
```

### Opção 3: Usando o Script Genérico

```bash
cd backend
python scripts/add_template.py \
  --name "Contrato Odontológico + Akimais Saúde" \
  --file templates/contrato_akimais.html \
  --default
```

## 📝 O Que Foi Criado

### 1. Template HTML Completo
- **Arquivo**: `backend/templates/contrato_akimais.html`
- **Baseado em**: CONTRACT_TEMPLATE original
- **Melhorias**: 
  - Variáveis adaptadas para o novo sistema ({{}} ao invés de {})
  - Mantém toda a estrutura e estilo original
  - Suporte completo para mobile

### 2. Script de Instalação Python
- **Arquivo**: `backend/scripts/add_akimais_template.py`
- **Funcionalidades**:
  - Busca automática do tipo Akimais
  - Configuração como template padrão
  - Validações e tratamento de erros

### 3. Migration SQL
- **Arquivo**: `backend/migrations/insert_akimais_template.sql`
- **Funcionalidades**:
  - Inserção direta no banco
  - Detecção automática do tipo
  - Configuração de todas as variáveis

## 🔧 Variáveis do Template

O template usa as seguintes variáveis (todas com {{}}):

### Dados da Empresa
- `{{razao_social}}` - Nome da empresa
- `{{cnpj}}` - CNPJ formatado
- `{{endereco}}` - Endereço completo
- `{{empresa_cidade}}` - Cidade da empresa
- `{{telefone}}` - Telefone da empresa

### Dados do Paciente
- `{{paciente_nome}}` - Nome completo
- `{{paciente_cpf}}` - CPF formatado
- `{{paciente_data_nascimento}}` - Data de nascimento
- `{{paciente_rg}}` - RG
- `{{paciente_telefone}}` - Telefone principal
- `{{paciente_email}}` - Email

### Dados Financeiros
- `{{valor_total}}` - Valor total do contrato
- `{{numero_parcelas}}` - Quantidade de parcelas
- `{{valor_parcela}}` - Valor de cada parcela
- `{{forma_pagamento}}` - Forma de pagamento
- `{{dia_vencimento}}` - Dia de vencimento

### Outros
- `{{vendedor_nome}}` - Nome do vendedor
- `{{data_contrato}}` - Data do contrato
- `{{signature_html}}` - HTML da assinatura digital

## ✅ Verificação

Após a instalação, verifique se o template foi criado:

```sql
-- No PostgreSQL
SELECT id, name, slug, tipo_odontograma_id, is_default 
FROM contract_templates 
WHERE slug = 'contrato-akimais-v1';
```

## 🎯 Uso no Sistema

O template será usado automaticamente quando:
1. Uma venda for criada com tipo "Contrato Odontológico + Akimais"
2. O sistema buscará o template padrão para esse tipo
3. As variáveis serão preenchidas com os dados da venda

## 🛠️ Manutenção

### Atualizar o Template
1. Edite o arquivo HTML: `backend/templates/contrato_akimais.html`
2. Execute novamente o script de instalação
3. O sistema criará uma nova versão (v2, v3, etc.)

### Gerenciar via Interface
- Acesse: `http://localhost:3000/templates`
- Visualize, edite ou clone o template
- Defina como padrão ou desative

## 📞 Troubleshooting

**Problema**: Tipo Akimais não encontrado
- **Solução**: O script perguntará se deseja criar como genérico ou especificar outro ID

**Problema**: Template não aparece nas vendas
- **Solução**: Verifique se está marcado como `is_active = true` e `is_default = true`

**Problema**: Variáveis não são substituídas
- **Solução**: Certifique-se de usar `{{variavel}}` com duplas chaves

---

**Template configurado e pronto para uso! 🎉**
