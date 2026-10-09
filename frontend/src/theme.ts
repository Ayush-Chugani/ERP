import { createTheme } from '@mui/material/styles';

/**
 * Palette: white and warm neutrals with orange as the single accent. Semantic colours (success / error / info) are kept
 * muted and used only for status. Light and dark schemes share the same hues; the `class` selector lets the toggle
 * switch without a re-render flash.
 */
export const ORANGE = {
  50: '#FFF7ED', 100: '#FFEDD5', 200: '#FED7AA', 300: '#FDBA74', 400: '#FB923C',
  500: '#F97316', 600: '#EA580C', 700: '#C2410C', 800: '#9A3412', 900: '#7C2D12',
} as const;
export const STONE = {
  50: '#FAFAF9', 100: '#F5F5F4', 200: '#E7E5E4', 300: '#D6D3D1', 400: '#A8A29E',
  500: '#78716C', 600: '#57534E', 700: '#44403C', 800: '#292524', 900: '#1C1917',
} as const;

export const theme = createTheme({
  cssVariables: { colorSchemeSelector: 'class', disableCssColorScheme: false },
  defaultColorScheme: 'light',
  colorSchemes: {
    light: {
      palette: {
        primary: { main: ORANGE[600], light: ORANGE[300], dark: ORANGE[700], contrastText: '#FFFFFF' },
        secondary: { main: STONE[700], contrastText: '#FFFFFF' },
        success: { main: '#15803D' },
        warning: { main: '#B45309' },
        error: { main: '#B91C1C' },
        info: { main: '#0F766E' },
        background: { default: STONE[50], paper: '#FFFFFF' },
        text: { primary: STONE[900], secondary: STONE[600], disabled: STONE[400] },
        divider: STONE[200],
        action: { hover: ORANGE[50], selected: ORANGE[100], focus: ORANGE[100] },
      },
    },
    dark: {
      palette: {
        primary: { main: ORANGE[400], light: ORANGE[300], dark: ORANGE[600], contrastText: STONE[900] },
        secondary: { main: STONE[300], contrastText: STONE[900] },
        success: { main: '#4ADE80' },
        warning: { main: '#FBBF24' },
        error: { main: '#F87171' },
        info: { main: '#5EEAD4' },
        background: { default: '#171412', paper: '#211D1A' },
        text: { primary: STONE[50], secondary: STONE[300], disabled: STONE[500] },
        divider: '#3A3330',
        action: { hover: 'rgba(251,146,60,0.10)', selected: 'rgba(251,146,60,0.18)', focus: 'rgba(251,146,60,0.18)' },
      },
    },
  },
  typography: {
    fontFamily: '"Inter", "Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif',
    fontSize: 14,
    h4: { fontWeight: 700, fontSize: '1.6rem', letterSpacing: '-0.02em' },
    h5: { fontWeight: 700, fontSize: '1.25rem', letterSpacing: '-0.01em' },
    h6: { fontWeight: 650, fontSize: '1.05rem' },
    subtitle1: { fontWeight: 600 },
    overline: { fontWeight: 700, letterSpacing: '0.08em', fontSize: '0.7rem' },
    button: { fontWeight: 600, textTransform: 'none' },
  },
  shape: { borderRadius: 10 },
  components: {
    MuiCssBaseline: { styleOverrides: { body: { WebkitFontSmoothing: 'antialiased' }, '*::selection': { background: ORANGE[200], color: STONE[900] } } },
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { borderRadius: 10 } } },
    MuiPaper: { defaultProps: { variant: 'outlined' }, styleOverrides: { root: { backgroundImage: 'none' } } },
    MuiCard: { defaultProps: { variant: 'outlined' } },
    MuiTextField: { defaultProps: { size: 'small', fullWidth: true } },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
    MuiTableCell: { styleOverrides: { head: { fontWeight: 700, whiteSpace: 'nowrap', fontSize: '0.75rem', letterSpacing: '0.04em', textTransform: 'uppercase' } } },
    MuiDialog: { styleOverrides: { paper: { borderRadius: 16 } } },
    MuiTooltip: { defaultProps: { arrow: true } },
  },
});
