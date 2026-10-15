# 📋 Instruções Completas - Sistema de Templates de Contratos

## 🚀 Como Usar o Sistema de Templates

### 1. Adicionar Templates via Script Python

O jeito mais fácil de adicionar novos templates é usando o script Python que criamos:

```bash
# Ver tipos de odontograma disponíveis
python scripts/add_template.py --list-tipos

# Adicionar template de ortodontia
python scripts/add_template.py \
  --name "Contrato Ortodontia - Aparelho Fixo" \
  --tipo-id 2 \
  --file templates/ortodontia_fixo.html \
  --default

# Adicionar template genérico (sem tipo específico)
python scripts/add_template.py \
  --name "Contrato Clareamento Dental" \
  --file templates/clareamento_dental.html
```

### 2. Templates Prontos Disponíveis

Já criamos 3 templates completos para você usar como exemplo:

#### 📁 `backend/templates/`
- **ortodontia_fixo.html** - Template moderno para tratamento ortodôntico
- **implante_unitario.html** - Template elegante para implantes
- **clareamento_dental.html** - Template colorido para clareamento

### 3. Interface Web (Frontend)

Adicionamos duas novas páginas ao sistema:

#### 📄 **Página de Gerenciamento** (`/templates`)
- Lista todos os templates cadastrados
- Permite visualizar, editar, clonar e excluir
- Define template padrão por tipo
- Busca e filtros

#### 👁️ **Página de Preview** (`/templates/:id`)
- Visualiza o template renderizado com dados de exemplo
- Alterna entre preview e código HTML
- Download do arquivo HTML
- Lista de variáveis disponíveis

### 4. Variáveis Disponíveis nos Templates

Todas as variáveis devem ser usadas com duplas chaves: `{{variavel}}`

#### Dados do Paciente:
- `{{paciente_nome}}` - Nome completo
- `{{paciente_cpf}}` - CPF formatado
- `{{paciente_telefone}}` - Telefone
- `{{paciente_email}}` - E-mail
- `{{paciente_endereco}}` - Endereço completo

#### Dados do Dentista:
- `{{dentista_nome}}` - Nome do profissional
- `{{dentista_cro}}` - Número do CRO
- `{{dentista_especialidade}}` - Especialidade

#### Dados Financeiros:
- `{{valor_total}}` - Valor total formatado
- `{{forma_pagamento}}` - Descrição da forma de pagamento
- `{{numero_parcelas}}` - Quantidade de parcelas
- `{{valor_parcela}}` - Valor de cada parcela

#### Dados da Empresa:
- `{{razao_social}}` - Nome da clínica
- `{{cnpj}}` - CNPJ formatado
- `{{endereco}}` - Endereço da clínica
- `{{telefone}}` - Telefone da clínica

#### Dados do Contrato:
- `{{data_contrato}}` - Data do contrato formatada
- `{{numero_contrato}}` - Número único do contrato
- `{{tipo_tratamento}}` - Tipo de tratamento/odontograma

### 5. Criar Template Personalizado

#### Estrutura Básica:
```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Contrato - {{tipo_tratamento}}</title>
    <style>
        /* Seus estilos CSS aqui */
    </style>
</head>
<body>
    <h1>{{razao_social}}</h1>
    <h2>Contrato de {{tipo_tratamento}}</h2>
    
    <p>Paciente: {{paciente_nome}}</p>
    <p>CPF: {{paciente_cpf}}</p>
    
    <!-- Conteúdo do contrato -->
    
    <div class="assinaturas">
        <div>
            _______________________<br>
            {{paciente_nome}}
        </div>
        <div>
            _______________________<br>
            {{dentista_nome}}<br>
            CRO: {{dentista_cro}}
        </div>
    </div>
</body>
</html>
```

### 6. Fluxo de Uso no Sistema

1. **Cadastro do Template:**
   - Use o script Python ou API para adicionar
   - Defina se é template padrão para algum tipo

2. **Seleção Automática:**
   - Sistema escolhe template baseado no tipo de odontograma
   - Se não houver específico, usa o template padrão geral

3. **Renderização:**
   - Template é preenchido com dados reais
   - HTML é gerado e enviado para assinatura digital

### 7. Comandos Úteis

```bash
# Adicionar todos os templates de exemplo
python scripts/add_template.py --name "Contrato Ortodontia - Aparelho Fixo" --tipo-id 2 --file templates/ortodontia_fixo.html --default
python scripts/add_template.py --name "Contrato Implante Unitário" --tipo-id 3 --file templates/implante_unitario.html
python scripts/add_template.py --name "Contrato Clareamento Dental" --file templates/clareamento_dental.html

# Executar migração do banco
python -c "from app.database.db import engine; exec(open('migrations/create_contract_templates_tables.sql').read())"
```

### 8. Boas Práticas

1. **Nomeação:**
   - Use nomes descritivos e padronizados
   - Inclua tipo de tratamento no nome
   - Use slugs em lowercase com hífens

2. **Versionamento:**
   - Sempre incremente versão ao modificar
   - Mantenha histórico de mudanças
   - Use sufixo -v1, -v2, etc no slug

3. **Design:**
   - Templates responsivos (mobile-friendly)
   - Cores da marca da clínica
   - Fontes legíveis para impressão
   - Margem adequada para assinatura

4. **Conteúdo:**
   - Linguagem clara e objetiva
   - Todas as cláusulas legais necessárias
   - Destaque para informações importantes
   - Espaço adequado para assinaturas

### 9. Troubleshooting

**Template não aparece na lista:**
- Verifique se está ativo (`is_active = true`)
- Confirme o tipo de odontograma está correto

**Variáveis não são substituídas:**
- Use exatamente `{{variavel}}` com duplas chaves
- Verifique se a variável existe nos dados

**Erro ao adicionar template:**
- Slug deve ser único
- HTML deve ser válido
- Tipo de odontograma deve existir

### 10. Próximos Passos

1. **Adicionar rotas no frontend:**
```typescript
// Em App.tsx, adicionar:
<Route path="/templates" element={<TemplateManagementPage />} />
<Route path="/templates/:id" element={<TemplatePreviewPage />} />
```

2. **Adicionar item no menu:**
```typescript
// Na Sidebar, adicionar:
{role === 'admin' && (
  <Link to="/templates">
    <FileText className="w-5 h-5" />
    Templates de Contratos
  </Link>
)}
```

3. **Executar migração:**
```bash
# No diretório backend
python execute_migrations.py
```

---

## 📞 Suporte

Em caso de dúvidas:
1. Verifique os logs em `backend/logs/`
2. Consulte a documentação da API em `/api/docs`
3. Entre em contato com o suporte técnico

**Sistema desenvolvido com ❤️ para facilitar a gestão de contratos digitais**
