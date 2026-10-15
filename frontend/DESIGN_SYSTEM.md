# Design System - GrupoJF

## Visão Geral

Este documento descreve o design system implementado para padronizar a UI/UX da aplicação GrupoJF, baseado no padrão visual do componente CaixaDiario.

## Princípios de Design

### 1. **Clareza e Simplicidade**
- Design limpo e profissional
- Hierarquia visual clara
- Espaçamento consistente
- Tipografia legível

### 2. **Consistência**
- Componentes reutilizáveis
- Padrões de interação uniformes
- Paleta de cores definida
- Estados visuais padronizados

### 3. **Acessibilidade**
- Contraste adequado
- Foco visível
- Áreas de clique generosas
- Feedback visual claro

## Estrutura de Arquivos

```
src/
├── components/
│   └── ui/
│       ├── Button.tsx
│       ├── Card.tsx
│       ├── Input.tsx
│       ├── Badge.tsx
│       ├── LoadingState.tsx
│       ├── ErrorState.tsx
│       ├── EmptyState.tsx
│       ├── PageHeader.tsx
│       ├── FilterCard.tsx
│       ├── MetricCard.tsx
│       ├── InfoCard.tsx
│       ├── SelectCard.tsx
│       ├── SummaryCard.tsx
│       ├── DataTable.tsx
│       └── index.ts
└── styles/
    └── tokens.ts
```

## Design Tokens

### Cores

#### Primary (Indigo)
- `primary-50`: #eef2ff
- `primary-100`: #e0e7ff
- `primary-500`: #6366f1
- `primary-600`: #4f46e5
- `primary-700`: #4338ca

#### Neutral (Slate)
- `neutral-50`: #f8fafc (background)
- `neutral-100`: #f1f5f9
- `neutral-200`: #e2e8f0 (borders)
- `neutral-500`: #64748b
- `neutral-800`: #1e293b

#### Semânticas
- **Success (Emerald)**: #10b981
- **Warning (Amber)**: #f59e0b
- **Danger (Red)**: #ef4444

### Espaçamento
- `xs`: 0.5rem (8px)
- `sm`: 1rem (16px)
- `md`: 1.5rem (24px)
- `lg`: 2rem (32px)
- `xl`: 3rem (48px)

### Border Radius
- `sm`: 0.125rem (2px)
- `default`: 0.25rem (4px)
- `md`: 0.375rem (6px)
- `lg`: 0.5rem (8px)
- `xl`: 0.75rem (12px)

### Sombras
- `sm`: 0 1px 2px rgba(0,0,0,0.05)
- `md`: 0 4px 6px rgba(0,0,0,0.07)
- `lg`: 0 10px 15px rgba(0,0,0,0.1)

## Componentes

### Button
```tsx
<Button variant="primary" size="md" icon={Save}>
  Salvar
</Button>
```

**Variantes**: primary, secondary, ghost, danger
**Tamanhos**: sm, md, lg

### Card
```tsx
<Card hover selected={isSelected} onClick={handleClick}>
  <CardHeader>
    <CardTitle>Título</CardTitle>
  </CardHeader>
  <CardContent>Conteúdo</CardContent>
</Card>
```

### Input & Select
```tsx
<Input 
  label="Nome" 
  icon={User} 
  error="Campo obrigatório"
/>

<Select 
  label="Estado"
  options={[
    { value: 'sp', label: 'São Paulo' },
    { value: 'rj', label: 'Rio de Janeiro' }
  ]}
/>
```

### Badge
```tsx
<Badge variant="success" size="md">
  Ativo
</Badge>
```

**Variantes**: default, primary, success, warning, danger

### Estados

#### LoadingState
```tsx
<LoadingState message="Carregando dados..." />
```

#### ErrorState
```tsx
<ErrorState 
  title="Erro"
  message="Algo deu errado"
  onRetry={() => window.location.reload()}
/>
```

#### EmptyState
```tsx
<EmptyState
  icon={Search}
  title="Nenhum resultado"
  description="Tente com outros filtros"
  action={{
    label: 'Resetar filtros',
    onClick: handleReset
  }}
/>
```

### Cards Especializados

#### MetricCard
```tsx
<MetricCard
  icon={DollarSign}
  iconColor="success"
  label="Faturamento"
  value="R$ 10.000,00"
  trend={{ value: 15, isPositive: true }}
/>
```

#### InfoCard
```tsx
<InfoCard
  icon={Info}
  iconColor="primary"
  title="Informação"
  description="Detalhes importantes"
  value="123"
/>
```

#### SelectCard
```tsx
<SelectCard
  icon={CreditCard}
  title="Cartão de Crédito"
  description="Em até 12x"
  selected={isSelected}
  onClick={handleSelect}
/>
```

#### SummaryCard
```tsx
<SummaryCard
  title="Resumo da Venda"
  icon={Calculator}
  items={[
    { label: 'Subtotal', value: 'R$ 100,00' },
    { label: 'Desconto', value: '-R$ 10,00', variant: 'success' },
    { label: 'Total', value: 'R$ 90,00', highlight: true }
  ]}
/>
```

### DataTable
```tsx
<DataTable
  columns={[
    { key: 'name', header: 'Nome' },
    { key: 'value', header: 'Valor', align: 'right' }
  ]}
  data={items}
  keyExtractor={(item) => item.id}
/>
```

## Padrões de Uso

### Formulários
1. Use `Card` para agrupar campos relacionados
2. Labels sempre acima dos campos
3. Mensagens de erro abaixo dos campos
4. Botões de ação alinhados à direita

### Feedback Visual
1. Estados de hover sutis (mudança de cor/sombra)
2. Transições suaves (200ms)
3. Estados disabled com opacity reduzida
4. Loading states centralizados

### Layout
1. Espaçamento vertical entre seções: `space-y-6`
2. Padding interno dos cards: `p-6`
3. Largura máxima de conteúdo: `max-w-6xl mx-auto`
4. Grid responsivo: `grid-cols-1 md:grid-cols-2`

## Migração

Para migrar componentes antigos:

1. Remova glassmorphism (`backdrop-blur`, transparências)
2. Substitua gradientes por cores sólidas
3. Use componentes do design system
4. Mantenha 100% da funcionalidade
5. Teste todos os estados e interações

## Exemplo de Refatoração

### Antes (Glassmorphism)
```tsx
<div className="bg-white/90 backdrop-blur-md rounded-3xl p-8 shadow-2xl border border-white/30">
  <div className="bg-gradient-to-r from-gray-800 to-blue-500 p-4 rounded-2xl">
    <Icon className="w-10 h-10 text-white" />
  </div>
  {/* conteúdo */}
</div>
```

### Depois (Design System)
```tsx
<Card>
  <div className="bg-indigo-100 p-3 rounded-lg">
    <Icon className="w-6 h-6 text-indigo-600" />
  </div>
  {/* conteúdo */}
</Card>
```

## Benefícios

1. **Performance**: Menos CSS, renderização mais rápida
2. **Manutenibilidade**: Código padronizado e modular
3. **Consistência**: UI uniforme em toda aplicação
4. **Produtividade**: Desenvolvimento mais rápido
5. **Acessibilidade**: Melhor suporte para leitores de tela