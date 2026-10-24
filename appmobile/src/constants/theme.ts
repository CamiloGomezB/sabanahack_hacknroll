// Paleta, tipografía y medidas tomadas del PDF "Miembro Regular":
// fotografía a pantalla completa oscurecida, logotipo "N" dorado en círculo blanco,
// botones blancos en forma de píldora, campos con línea inferior y texto blanco en Poppins.

export const colors = {
  background: '#14100b',
  overlay: 'rgba(18, 12, 6, 0.58)',
  overlayStrong: 'rgba(14, 9, 4, 0.74)',
  white: '#ffffff',
  text: '#ffffff',
  textMuted: 'rgba(255, 255, 255, 0.72)',
  textFaint: 'rgba(255, 255, 255, 0.5)',
  ink: '#1a1a1a',
  gold: '#8b6f47',
  goldLight: '#d9bd8a',
  line: 'rgba(255, 255, 255, 0.85)',
  glass: 'rgba(255, 255, 255, 0.12)',
  glassBorder: 'rgba(255, 255, 255, 0.22)',
  qrInk: '#142a2c',
  success: '#7fd1a0',
  warning: '#f0c36a',
  danger: '#ff8a80',
  demo: '#f0c36a',
} as const;

export const fonts = {
  body: 'Poppins_400Regular',
  medium: 'Poppins_500Medium',
  semibold: 'Poppins_600SemiBold',
  display: 'PlayfairDisplay_400Regular',
  script: 'GreatVibes_400Regular',
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
  sm: 12,
  md: 20,
  lg: 28,
  pill: 999,
} as const;

/** Ancho máximo del contenido para que el diseño de teléfono se vea bien en tabletas y web. */
export const CONTENT_MAX_WIDTH = 440;
