/** Design tokens - mobile readability tuned. */
export const colors = {
  bg: '#1B1B1A',
  card: '#262624',
  border: '#3A3A37',
  accent: '#C4B8A8',
  textPrimary: '#F5F5F5',
  textSecondary: '#D0CFCF',
  textMuted: '#8A8A8A',
  error: '#E53935',
  success: '#4CAF50',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  full: 9999,
} as const;

export const typography = {
  xs: 13,
  sm: 15,
  base: 17,
  md: 18,
  lg: 20,
  xl: 22,
  xxl: 26,
  xxxl: 30,
} as const;
