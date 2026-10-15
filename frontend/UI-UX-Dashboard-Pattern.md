# UI/UX Dashboard Pattern - Grupo JF Frontend

## Visão Geral
Este documento estabelece o padrão de design system baseado na análise do componente `CaixaDiario.tsx`, criando diretrizes replicáveis para dashboards administrativos seguindo padrões de grandes startups do Vale do Silício.

## 1. ARQUITETURA DE LAYOUT

### 1.1 Estrutura Base
```tsx
<div className="flex min-h-screen bg-slate-50 overflow-x-hidden">
  <Sidebar className="w-64 flex-shrink-0 fixed h-full" />
  <div className="flex-1 w-full pl-64 transition-all duration-300 ease-in-out flex flex-col">
    <Header />
    <Main />
    <Footer />
  </div>
</div>
```

### 1.2 Sistema de Grid Responsivo
- **Container Principal**: `max-w-6xl mx-auto` (1152px máximo)
- **Grid de Filtros**: `grid grid-cols-1 md:grid-cols-6 gap-6`
- **Grid de Métricas**: `grid grid-cols-1 md:grid-cols-3 gap-6`
- **Sidebar Fixa**: `w-64` (256px de largura)

### 1.3 Hierarquia Visual
1. **Header**: Título da página + informações do usuário
2. **Filtros**: Seção de controles em card destacado
3. **Métricas**: Cards de KPIs em grid
4. **Conteúdo Principal**: Tabelas e gráficos
5. **Footer**: Informações do sistema

## 2. DESIGN SYSTEM

### 2.1 Paleta de Cores
```css
/* Cores Primárias */
--primary: indigo-600, indigo-700, indigo-500
--primary-light: indigo-100

/* Cores Neutras */
--background: slate-50
--surface: white
--text-primary: slate-800
--text-secondary: slate-700
--text-muted: slate-500
--border: slate-200, slate-300

/* Cores Semânticas */
--success: emerald-600, emerald-100
--warning: amber-600, amber-100
--error: red-500, red-50
```

### 2.2 Tipografia
```css
/* Hierarquia de Texto */
--text-title: text-2xl font-bold
--text-heading: text-lg font-semibold
--text-body: text-sm
--text-caption: text-xs
--text-display: text-3xl font-bold

/* Cores de Texto */
--text-title-color: slate-800
--text-heading-color: slate-800
--text-body-color: slate-700
--text-muted-color: slate-500
```

### 2.3 Espaçamento e Bordas
```css
/* Sistema de Espaçamento (múltiplos de 4px) */
--spacing-xs: 2 (8px)
--spacing-sm: 4 (16px)
--spacing-md: 6 (24px)
--spacing-lg: 8 (32px)

/* Bordas */
--border-radius: rounded-lg (8px)
--border-radius-xl: rounded-xl (12px)
--border-width: border (1px)
```

## 3. COMPONENTES FUNDAMENTAIS

### 3.1 Card Container
```tsx
const CardContainer = ({ children, className = "" }) => (
  <div className={`bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow ${className}`}>
    {children}
  </div>
);
```

### 3.2 Metric Card
```tsx
const MetricCard = ({ icon, title, value, description, colorScheme = "indigo" }) => (
  <div className="bg-white rounded-xl shadow-sm p-6 border border-slate-100 hover:shadow-md transition-shadow">
    <div className="flex items-center mb-2">
      <div className={`rounded-full bg-${colorScheme}-100 p-2 mr-3`}>
        {icon}
      </div>
      <h3 className="text-sm font-medium text-slate-500">{title}</h3>
    </div>
    <p className="text-3xl font-bold text-slate-800">{value}</p>
    <p className="text-xs text-slate-500 mt-2">{description}</p>
  </div>
);
```

### 3.3 Filter Section
```tsx
const FilterSection = ({ children, onReset }) => (
  <CardContainer className="mb-8">
    <div className="flex justify-between items-center mb-6">
      <h2 className="text-lg font-semibold text-slate-800">Filtros</h2>
      <button 
        className="text-indigo-600 hover:text-indigo-800 text-sm font-medium flex items-center"
        onClick={onReset}
      >
        <ResetIcon className="h-4 w-4 mr-1" />
        Resetar Filtros
      </button>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-6 gap-6">
      {children}
    </div>
  </CardContainer>
);
```

### 3.4 Form Controls

#### Input com Ícone
```tsx
const InputWithIcon = ({ icon, type = "text", ...props }) => (
  <div className="relative">
    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
      {icon}
    </div>
    <input
      type={type}
      className="w-full border border-slate-300 rounded-lg pl-10 p-2.5 text-sm text-slate-800 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
      {...props}
    />
  </div>
);
```

#### Select Customizado
```tsx
const CustomSelect = ({ options, value, onChange, placeholder = "Selecione..." }) => (
  <div className="relative">
    <select
      value={value}
      onChange={onChange}
      className="w-full border border-slate-300 rounded-lg p-2.5 text-sm text-slate-800 appearance-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
    >
      <option value="">{placeholder}</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
    <ChevronDownIcon className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none h-5 w-5 text-slate-400" />
  </div>
);
```

### 3.5 Buttons

#### Primary Button
```tsx
const PrimaryButton = ({ children, onClick, disabled = false, ...props }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className={`px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
      disabled ? 'opacity-50 cursor-not-allowed' : ''
    }`}
    {...props}
  >
    {children}
  </button>
);
```

#### Secondary Button
```tsx
const SecondaryButton = ({ children, onClick, ...props }) => (
  <button
    onClick={onClick}
    className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors"
    {...props}
  >
    {children}
  </button>
);
```

#### Icon Button
```tsx
const IconButton = ({ icon, children, onClick, variant = "primary" }) => (
  <button 
    className={`flex items-center text-sm font-medium ${
      variant === "primary" ? "text-indigo-600 hover:text-indigo-800" : 
      variant === "success" ? "text-emerald-600 hover:text-emerald-800" : 
      "text-slate-600 hover:text-slate-800"
    }`}
    onClick={onClick}
  >
    {icon}
    {children}
  </button>
);
```

## 4. PADRÕES DE TABELA

### 4.1 Responsive Table
```tsx
const ResponsiveTable = ({ columns, data, loading = false }) => (
  <div className="overflow-x-auto">
    <table className="min-w-full divide-y divide-slate-200">
      <thead className="bg-slate-50">
        <tr>
          {columns.map((column) => (
            <th key={column.key} className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
              {column.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="bg-white divide-y divide-slate-100">
        {loading ? (
          <LoadingRow colSpan={columns.length} />
        ) : data.length === 0 ? (
          <EmptyRow colSpan={columns.length} />
        ) : (
          data.map((row, index) => (
            <tr key={index} className="hover:bg-slate-50 transition-colors">
              {columns.map((column) => (
                <td key={column.key} className="px-6 py-4 whitespace-nowrap text-sm text-slate-700">
                  {column.render ? column.render(row[column.key], row) : row[column.key]}
                </td>
              ))}
            </tr>
          ))
        )}
      </tbody>
    </table>
  </div>
);
```

### 4.2 Pagination
```tsx
const Pagination = ({ currentPage, totalPages, onPageChange }) => (
  <div className="flex items-center justify-between mt-6">
    <div className="text-sm text-slate-500">
      Mostrando {((currentPage - 1) * itemsPerPage) + 1}-{Math.min(currentPage * itemsPerPage, totalItems)} de {totalItems} itens
    </div>
    <div className="flex space-x-2">
      <PaginationButton 
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
      >
        Anterior
      </PaginationButton>
      
      {/* Números das páginas */}
      {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
        const pageNum = calculatePageNumber(i, currentPage, totalPages);
        return (
          <PaginationButton
            key={i}
            onClick={() => onPageChange(pageNum)}
            active={currentPage === pageNum}
          >
            {pageNum}
          </PaginationButton>
        );
      })}
      
      <PaginationButton 
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
      >
        Próxima
      </PaginationButton>
    </div>
  </div>
);
```

## 5. ESTADOS DE INTERFACE

### 5.1 Loading States
```tsx
const LoadingSpinner = () => (
  <div className="flex justify-center items-center h-64">
    <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-indigo-600"></div>
  </div>
);

const LoadingRow = ({ colSpan }) => (
  <tr>
    <td colSpan={colSpan} className="px-6 py-8 text-center">
      <LoadingSpinner />
    </td>
  </tr>
);
```

### 5.2 Empty States
```tsx
const EmptyState = ({ title, description, action }) => (
  <div className="text-center py-12">
    <EmptyIcon className="mx-auto h-12 w-12 text-slate-400" />
    <h3 className="mt-2 text-sm font-medium text-slate-900">{title}</h3>
    <p className="mt-1 text-sm text-slate-500">{description}</p>
    {action && <div className="mt-6">{action}</div>}
  </div>
);
```

### 5.3 Error States
```tsx
const ErrorMessage = ({ message, onRetry }) => (
  <div className="bg-red-50 border-l-4 border-red-500 text-red-700 p-4 mb-6 rounded-lg">
    <div className="flex">
      <div className="flex-shrink-0">
        <ErrorIcon className="h-5 w-5 text-red-400" />
      </div>
      <div className="ml-3">
        <p className="text-sm">{message}</p>
        {onRetry && (
          <button 
            className="mt-2 text-sm underline hover:text-red-800"
            onClick={onRetry}
          >
            Tentar novamente
          </button>
        )}
      </div>
    </div>
  </div>
);
```

## 6. PATTERNS DE HOOKS

### 6.1 useAuth Hook
```tsx
const useAuth = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    if (token) {
      setIsAuthenticated(true);
      const userData = localStorage.getItem('userData');
      if (userData) {
        setUser(JSON.parse(userData));
      }
    }
    setLoading(false);
  }, []);

  const logout = () => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('userData');
    setIsAuthenticated(false);
    setUser(null);
    window.location.href = '/login';
  };

  return { isAuthenticated, user, loading, logout };
};
```

### 6.2 useFilters Hook
```tsx
const useFilters = (initialFilters = {}) => {
  const [filters, setFilters] = useState(initialFilters);
  const [pendingFilters, setPendingFilters] = useState(null);

  const updateFilter = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const resetFilters = () => {
    setFilters(initialFilters);
    setPendingFilters(null);
  };

  const applyPendingFilters = () => {
    if (pendingFilters) {
      setFilters(prev => ({ ...prev, ...pendingFilters }));
      setPendingFilters(null);
    }
  };

  return {
    filters,
    pendingFilters,
    updateFilter,
    resetFilters,
    setPendingFilters,
    applyPendingFilters
  };
};
```

### 6.3 useApi Hook
```tsx
const useApi = (apiFunction, dependencies = []) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await apiFunction();
      setData(result);
    } catch (err) {
      setError(err.message || 'Erro ao carregar dados');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, dependencies);

  return { data, loading, error, refetch: fetchData };
};
```

## 7. GUIDELINES DE IMPLEMENTAÇÃO

### 7.1 Acessibilidade
- Usar `aria-label` e `aria-describedby` quando necessário
- Manter contraste mínimo de 4.5:1 para texto
- Garantir navegação por teclado em todos os componentes
- Usar elementos semânticos HTML apropriados

### 7.2 Performance
- Implementar lazy loading para tabelas grandes
- Usar React.memo para componentes que renderizam listas
- Implementar debounce em filtros de busca
- Paginar dados quando apropriado

### 7.3 Responsividade
- Mobile-first approach
- Breakpoints: sm (640px), md (768px), lg (1024px), xl (1280px)
- Usar overflow-x-auto para tabelas em mobile
- Ajustar grid columns conforme tamanho da tela

### 7.4 Consistência
- Manter padrões de nomenclatura de classes CSS
- Usar o mesmo sistema de cores em toda aplicação
- Seguir hierarquia visual estabelecida
- Documentar variações de componentes

## 8. ESTRUTURA DE ARQUIVOS

```
src/
├── components/
│   ├── ui/           # Componentes base reutilizáveis
│   ├── layout/       # Componentes de layout (Header, Sidebar, Footer)
│   ├── forms/        # Componentes de formulário
│   └── tables/       # Componentes de tabela e paginação
├── hooks/            # Custom hooks
├── utils/            # Funções utilitárias
├── styles/           # Estilos globais e variáveis CSS
└── pages/            # Páginas/telas da aplicação
```

Este padrão garante consistência visual, experiência de usuário otimizada e código maintível em toda a aplicação.