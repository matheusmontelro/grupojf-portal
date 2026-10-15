# 📋 Templates de Contratos por Tipo de Odontograma

## 🎯 Resumo dos Templates Criados

Todos os templates estão configurados e funcionando no arquivo `/app/digital_contracts/templates.py`.

### 1️⃣ **Particular** (ID: 1)
- **Template**: `TEMPLATE_PARTICULAR`
- **Estilo**: Profissional azul com design clean
- **Características**: 
  - Orçamento simples e direto
  - Foco no valor e condições de pagamento
  - Visual moderno com gradientes azuis
  - Ideal para tratamentos avulsos

### 2️⃣ **Ortodontia** (ID: 2)  
- **Template**: `TEMPLATE_ORTODONTIA`
- **Estilo**: Roxo vibrante com fases do tratamento
- **Características**:
  - 4 fases numeradas do tratamento
  - Destaque para duração e manutenções
  - Visual atrativo com ícones de progresso
  - Observações sobre colaboração do paciente

### 3️⃣ **Contrato Odontológico + Akimais** (ID: 3)
- **Template**: `CONTRATO_AKIMAIS_TEMPLATE`
- **Estilo**: Formal com tabelas estruturadas
- **Características**:
  - Layout tradicional tipo contrato
  - Seções A, B, C, D bem definidas
  - Suporte para dependentes
  - Cláusulas detalhadas numeradas

### 4️⃣ **Contrato Ortodôntico** (ID: 4)
- **Template**: `TEMPLATE_CONTRATO_ORTODONTICO`
- **Estilo**: Jurídico formal (Times New Roman)
- **Características**:
  - Formato contrato tradicional
  - Cláusulas numeradas em romano
  - Área para testemunhas
  - Visual sóbrio e profissional

### 5️⃣ **Combo Orto + ODC** (ID: 5)
- **Template**: `TEMPLATE_COMBO_ORTO_ODC`
- **Estilo**: Colorido e promocional (laranja/amarelo)
- **Características**:
  - Destaque para economia de 25%
  - Cards comparativos de preços
  - Timeline de tratamento
  - Visual que transmite vantagem

### 6️⃣ **Taxa de Adesão** (ID: 6)
- **Template**: `TEMPLATE_TAXA_ADESAO`
- **Estilo**: Verde moderno com cards de benefícios
- **Características**:
  - Lista de benefícios em cards
  - Aviso claro de que NÃO é plano de saúde
  - Visual limpo e confiável
  - Foco nos benefícios do programa

## 🔧 Como Funciona

1. **Sistema Automático**: O `template_manager.py` escolhe automaticamente o template correto baseado no tipo de odontograma

2. **Fallback Inteligente**: Se não houver template no banco de dados, usa o template hardcoded específico do tipo

3. **Variáveis Padrão**: Todos os templates usam as mesmas variáveis:
   - `{{paciente_nome}}`, `{{paciente_cpf}}`, `{{paciente_telefone}}`
   - `{{valor_total}}`, `{{numero_parcelas}}`, `{{valor_parcela}}`
   - `{{razao_social}}`, `{{cnpj}}`, `{{endereco}}`
   - `{{dentista_nome}}`, `{{dentista_cro}}`
   - `{{data_contrato}}`, `{{forma_pagamento}}`
   - `{{signature_html}}` (para assinatura digital)

## 🚀 Uso no Sistema

O sistema automaticamente:
1. Identifica o tipo de odontograma da venda
2. Busca o template correspondente
3. Preenche as variáveis com os dados reais
4. Gera o HTML para assinatura digital

## 📝 Para Modificar Templates

### Opção 1: Editar Diretamente (Recomendado)
Edite o arquivo `/app/digital_contracts/templates.py` e modifique o template desejado.

### Opção 2: Criar Novo Template
```python
# Adicione no final do arquivo templates.py
TEMPLATE_MEU_NOVO = """
<!DOCTYPE html>
<html>
...
</html>
"""

# Adicione no mapeamento da função get_template_by_tipo_id
templates_map = {
    ...
    7: TEMPLATE_MEU_NOVO,  # Novo tipo
}
```

## 🎨 Dicas de Design

1. **Cores por Tipo**:
   - Particular: Azul profissional (#3498db)
   - Ortodontia: Roxo moderno (#9b59b6)
   - Akimais: Verde tradicional (#4CAF50)
   - Combo: Laranja vibrante (#e74c3c)
   - Taxa Adesão: Verde sucesso (#2ecc71)

2. **Manter Consistência**:
   - Sempre incluir dados do paciente no topo
   - Valor destacado e centralizado
   - Área de assinatura padrão no final
   - Footer com dados da empresa

3. **Mobile-Friendly**:
   - Todos os templates são responsivos
   - Testados em diferentes tamanhos de tela
   - Print-friendly com @media print

---

**✅ Todos os 6 tipos de odontograma agora têm templates personalizados e prontos para uso!**