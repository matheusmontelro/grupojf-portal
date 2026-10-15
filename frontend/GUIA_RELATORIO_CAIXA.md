# 📊 Guia do Relatório de Caixa

## O que é o Relatório de Caixa?
Este relatório mostra **todas as vendas e cobranças** da clínica em um só lugar, incluindo vendas normais, carnês, faturas online e mensalidades automáticas.

---

## 💳 Tipos de Transação (Badges Coloridos)

### 🔵 **Venda** 
- **O que é**: Venda tradicional feita na recepção 
- **Pagamento**: Parcelas controladas pela clínica
- **Exemplo**: Cliente aprova orçamento e paga em 6x no cartão

### 🟣 **Carnê**
- **O que é**: Parcelamento via carnê de cobrança
- **Pagamento**: Boletos ou PIX automáticos
- **Exemplo**: Cliente escolhe pagar em 12x via carnê

### 🟢 **Fatura Avulsa**
- **O que é**: Cobrança única online
- **Pagamento**: Pagamento imediato via link
- **Exemplo**: Taxa de adesão paga online

### 🟠 **Fatura Recorrente**
- **O que é**: Mensalidade automática
- **Pagamento**: Débito automático mensal
- **Exemplo**: Plano ortodôntico com cobrança mensal

---

## 📈 Entendendo os Números

### **Cards do Resumo**

#### 📊 **Total de Vendas**
- Quantidade total de todas as operações
- Inclui vendas + carnês + faturas + mensalidades

#### 💰 **Valor Bruto**
- Valor "cheio" antes de descontos
- Soma de tudo que foi orçado

#### 💵 **Valor Líquido** 
- Valor real após descontos
- **Este é o valor que a clínica deve receber**

#### ✅ **Valor Pago**
- Dinheiro que já entrou no caixa
- **Atenção**: Carnês aparecem como não pagos porque o controle é externo

#### 🏦 **Valor Entrada**
- Sinais pagos durante orçamentos
- Valores pagos antes da venda ser finalizada

#### 🎯 **Ticket Médio**
- Valor médio por cliente
- Calculado: Valor Líquido ÷ Total de Vendas

---

## 📋 Informações da Tabela

### **Colunas Principais**

#### **Documento**
- **Vendas**: V-12345 (código único)
- **Carnês**: Nome do arquivo do carnê
- **Faturas**: FATURA-123 ou RECORRENTE-456

#### **Tipo Transação**
- Badge colorido que mostra a origem
- Ajuda a identificar como o cliente está pagando

#### **Status**
- **Ativa**: Venda aprovada, aguardando pagamento
- **Finalizada**: Totalmente paga
- **PAID**: Fatura paga online
- **PENDING**: Aguardando pagamento online

#### **Valores**
- **Valor principal**: Quanto o cliente deve pagar
- **Valor riscado**: Valor original (se houve desconto)

---

## 🤔 Perguntas Frequentes

### **Por que carnês aparecem como "não pagos"?**
Carnês são pagos via sistema externo (banco). O controle de pagamento não fica na clínica, por isso aparecem como pendentes.

### **O que são as "entradas"?**
São sinais que clientes pagam durante o orçamento, antes de aprovar o tratamento. Esses valores são contados separadamente.

### **Por que o valor pago é menor que o valor total?**
- Vendas parceladas: só mostra parcelas já recebidas
- Carnês: pagamentos controlados externamente
- Mensalidades: ainda não vencidas

### **Como interpretar o ticket médio?**
- **Alto**: Clientes gastam mais por visita
- **Baixo**: Tratamentos mais simples ou promoções

---

## 🎯 Como Usar os Filtros

### **Por Período**
- Escolha data inicial e final
- Use atalhos: "Hoje", "Este mês", "Últimos 30 dias"

### **Por Unidade**
- Filtre por clínica específica
- Útil para comparar performance entre unidades

### **Por Dentista**
- Veja vendas de um profissional específico
- Útil para avaliar produtividade

### **Por Tipo de Plano**
- Filtre por "Particular", "Ortodontia", etc.
- Veja quais contratos estão vendendo mais

---

## 📊 Dicas de Interpretação

### **Para Administradores**
- **Foque no Valor Líquido**: É a receita real
- **Compare períodos**: Use filtros para análises mensais
- **Observe tipos**: Veja se carnês/online estão crescendo

### **Para Recepcionistas**
- **Vendas Ativas**: Precisam de acompanhamento de pagamento
- **Entradas**: Sinais que já foram pagos
- **Status**: Identifica o que precisa de ação

### **Para Dentistas**
- **Suas vendas**: Filtre por seu nome
- **Ticket médio**: Sua performance comercial
- **Tipos de plano**: Quais contratos você mais vende

---

## ⚠️ Observações Importantes

### **Valores podem não bater com outros relatórios porque:**
- Este relatório inclui **TODAS** as formas de cobrança
- Relatórios antigos podem mostrar apenas vendas tradicionais
- Carnês e faturas online antes não apareciam consolidados

### **Timing dos dados:**
- Vendas: Atualizadas em tempo real
- Carnês: Criação imediata, pagamento externo
- Faturas online: Status atualizado via webhook
- Mensalidades: Cobranças automáticas mensais

---

## 🆘 Precisa de Ajuda?

Se algum número parecer estranho ou inconsistente:

1. **Verifique os filtros**: Período, unidade, etc.
2. **Observe os tipos**: Cada badge representa um fluxo diferente
3. **Compare com período anterior**: Para validar tendências
4. **Entre em contato**: Com o suporte técnico se necessário

**Lembre-se**: Este é o relatório mais completo disponível, mostrando toda a realidade financeira da clínica de forma consolidada! 🎉