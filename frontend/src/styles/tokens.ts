// Design Tokens - Sistema de Design GrupoJF
// Baseado no padrão visual do CaixaDiario.tsx

export const colors = {
  // Primary Colors
  primary: {
    50: '#eef2ff',   // indigo-50
    100: '#e0e7ff',  // indigo-100
    200: '#c7d2fe',  // indigo-200
    300: '#a5b4fc',  // indigo-300
    400: '#818cf8',  // indigo-400
    500: '#6366f1',  // indigo-500
    600: '#4f46e5',  // indigo-600
    700: '#4338ca',  // indigo-700
    800: '#3730a3',  // indigo-800
    900: '#312e81',  // indigo-900
  },
  
  // Neutral Colors (Slate)
  neutral: {
    50: '#f8fafc',   // slate-50
    100: '#f1f5f9',  // slate-100
    200: '#e2e8f0',  // slate-200
    300: '#cbd5e1',  // slate-300
    400: '#94a3b8',  // slate-400
    500: '#64748b',  // slate-500
    600: '#475569',  // slate-600
    700: '#334155',  // slate-700
    800: '#1e293b',  // slate-800
    900: '#0f172a',  // slate-900
  },
  
  // Semantic Colors
  success: {
    50: '#ecfdf5',   // emerald-50
    100: '#d1fae5',  // emerald-100
    500: '#10b981',  // emerald-500
    600: '#059669',  // emerald-600
    700: '#047857',  // emerald-700
  },
  
  warning: {
    50: '#fffbeb',   // amber-50
    100: '#fef3c7',  // amber-100
    500: '#f59e0b',  // amber-500
    600: '#d97706',  // amber-600
    700: '#b45309',  // amber-700
  },
  
  danger: {
    50: '#fef2f2',   // red-50
    100: '#fee2e2',  // red-100
    500: '#ef4444',  // red-500
    600: '#dc2626',  // red-600
    700: '#b91c1c',  // red-700
  },
  
  // Background
  background: '#f8fafc', // slate-50
  surface: '#ffffff',
};

export const spacing = {
  xs: '0.5rem',   // 8px
  sm: '1rem',     // 16px
  md: '1.5rem',   // 24px
  lg: '2rem',     // 32px
  xl: '3rem',     // 48px
  '2xl': '4rem',  // 64px
};

export const borderRadius = {
  none: '0',
  sm: '0.125rem',     // 2px
  default: '0.25rem', // 4px
  md: '0.375rem',     // 6px
  lg: '0.5rem',       // 8px
  xl: '0.75rem',      // 12px
  '2xl': '1rem',      // 16px
  '3xl': '1.5rem',    // 24px
  full: '9999px',
};

export const shadows = {
  none: 'none',
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  default: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
  xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
  '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
};

export const transitions = {
  fast: '150ms ease-in-out',
  base: '200ms ease-in-out',
  slow: '300ms ease-in-out',
  slower: '500ms ease-in-out',
};

export const typography = {
  fontSize: {
    xs: '0.75rem',     // 12px
    sm: '0.875rem',    // 14px
    base: '1rem',      // 16px
    lg: '1.125rem',    // 18px
    xl: '1.25rem',     // 20px
    '2xl': '1.5rem',   // 24px
    '3xl': '1.875rem', // 30px
    '4xl': '2.25rem',  // 36px
  },
  fontWeight: {
    normal: '400',
    medium: '500',
    semibold: '600',
    bold: '700',
  },
  lineHeight: {
    tight: '1.25',
    normal: '1.5',
    relaxed: '1.75',
  },
};