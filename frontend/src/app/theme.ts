import { createTheme } from '@mui/material';
import type {} from '@mui/x-data-grid/themeAugmentation';

/**
 * SIMS theme — clean, flat and high-contrast.
 * One calm blue accent on white surfaces over a light grey canvas.
 * Comfortable base size (15px), generous touch targets, no gradients.
 */
export const BRAND = '#1f4fa3';
export const BRAND_DARK = '#173d80';
export const BRAND_TINT = '#eaf0fa';
export const CANVAS = '#f5f7fa';
export const LINE = '#e3e8ef';
export const INK = '#1b2733';
export const INK_SOFT = '#5b6b7b';

// Back-compat aliases for modules that still import the previous palette names.
export const NAVY = INK;
export const NAVY_DEEP = INK;
export const EMERALD = BRAND;
export const EMERALD_DARK = BRAND_DARK;
export const GOLD = BRAND;
export const GOLD_SOFT = BRAND_TINT;
export const IVORY = CANVAS;

export const theme = createTheme({
  palette: {
    primary: { main: BRAND, dark: BRAND_DARK, light: BRAND_TINT, contrastText: '#ffffff' },
    secondary: { main: '#4b5d70', contrastText: '#ffffff' },
    success: { main: '#1e7a4c' },
    warning: { main: '#b26a00' },
    error: { main: '#b3261e' },
    info: { main: BRAND },
    background: { default: CANVAS, paper: '#ffffff' },
    text: { primary: INK, secondary: INK_SOFT },
    divider: LINE,
  },
  typography: {
    fontFamily: '"Segoe UI", Inter, system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif',
    fontSize: 15,
    h1: { fontWeight: 600 },
    h4: { fontWeight: 600, fontSize: '1.5rem', letterSpacing: '-0.01em' },
    h5: { fontWeight: 600, fontSize: '1.2rem' },
    h6: { fontWeight: 600, fontSize: '1.05rem' },
    subtitle1: { fontWeight: 600 },
    overline: { fontWeight: 600, letterSpacing: '0.08em', fontSize: '0.72rem' },
    button: { fontWeight: 600, textTransform: 'none' },
  },
  shape: { borderRadius: 8 },
  breakpoints: { values: { xs: 0, sm: 600, md: 960, lg: 1280, xl: 1600 } },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { backgroundColor: CANVAS, textRendering: 'optimizeLegibility', WebkitFontSmoothing: 'antialiased' },
        code: {
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
          fontSize: '0.85em',
          background: '#eef1f5',
          padding: '1px 5px',
          borderRadius: 4,
        },
        'a': { color: BRAND },
        '::selection': { backgroundColor: 'rgba(59,91,219,.18)' },
        ':focus-visible': { outline: `2px solid ${BRAND}`, outlineOffset: 2 },
        '*::-webkit-scrollbar': { width: 10, height: 10 },
        '*::-webkit-scrollbar-thumb': { background: '#cbd3e0', borderRadius: 8, border: '2px solid transparent', backgroundClip: 'content-box' },
        '*::-webkit-scrollbar-thumb:hover': { background: '#aab4c5', backgroundClip: 'content-box' },
        // Several feature screens derive labels from API field names ("is active"); show them capitalised.
        '.MuiInputLabel-root::first-letter, .MuiFormControlLabel-label::first-letter, .MuiSelect-select::first-letter, .MuiMenuItem-root::first-letter, .MuiTableCell-head::first-letter': { textTransform: 'uppercase' },
      },
    },
    MuiAppBar: {
      defaultProps: { elevation: 0, color: 'inherit' },
      styleOverrides: {
        root: { backgroundColor: '#ffffff', color: INK, borderBottom: `1px solid ${LINE}` },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { textTransform: 'none', borderRadius: 8, fontWeight: 600, minHeight: 36 },
        contained: { '&.Mui-disabled': { backgroundColor: '#e3e8ef', color: '#7a8796' } },
        outlined: { borderColor: '#cfd7e2', color: INK, '&:hover': { borderColor: BRAND, backgroundColor: BRAND_TINT } },
        // Plain buttons read as quiet secondary actions; inside tables they stay as compact links.
        text: {
          color: INK,
          backgroundColor: '#ffffff',
          border: '1px solid #d5dbe6',
          '&:hover': { borderColor: BRAND, backgroundColor: BRAND_TINT, color: BRAND_DARK },
          '&.Mui-disabled': { borderColor: LINE, backgroundColor: '#fafbfc' },
        },
        sizeSmall: { minHeight: 32 },
      },
    },
    MuiPaper: {
      defaultProps: { variant: 'outlined' },
      styleOverrides: {
        root: { backgroundImage: 'none' },
        outlined: { borderColor: LINE, borderRadius: 10, boxShadow: '0 1px 2px rgba(16,24,40,.04)' },
      },
    },
    MuiCard: {
      defaultProps: { variant: 'outlined' },
      styleOverrides: {
        root: { borderColor: LINE, borderRadius: 10, boxShadow: 'none' },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          '&.Mui-selected': {
            backgroundColor: BRAND_TINT,
            color: BRAND_DARK,
            '&:hover': { backgroundColor: '#dfe8f6' },
          },
        },
      },
    },
    MuiListSubheader: {
      styleOverrides: { root: { backgroundColor: 'transparent', lineHeight: '30px' } },
    },
    MuiTable: {
      defaultProps: { size: 'small' },
      styleOverrides: { root: { '& .MuiTableCell-root': { paddingTop: 10, paddingBottom: 10 } } },
    },
    MuiTableContainer: {
      styleOverrides: { root: { maxWidth: '100%' } },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          '& .MuiTableCell-head': {
            backgroundColor: '#f6f8fb',
            fontWeight: 600,
            fontSize: '0.78rem',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            color: INK_SOFT,
            borderBottom: `1px solid ${LINE}`,
            whiteSpace: 'nowrap',
          },
        },
      },
    },
    MuiTableRow: {
      styleOverrides: { root: { '&:hover': { backgroundColor: '#fafbfd' } } },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderColor: LINE,
          '& .MuiButton-text': { border: 'none', backgroundColor: 'transparent', color: BRAND, minHeight: 28, padding: '2px 8px', '&:hover': { backgroundColor: BRAND_TINT, color: BRAND_DARK } },
        },
      },
    },
    MuiChip: {
      styleOverrides: { root: { borderRadius: 6, fontWeight: 500 } },
    },
    MuiDialog: {
      styleOverrides: { paper: { borderRadius: 14, boxShadow: '0 24px 60px rgba(20,33,61,.22)' } },
    },
    MuiDialogTitle: { styleOverrides: { root: { fontWeight: 600, fontSize: '1.15rem' } } },
    MuiMenu: {
      styleOverrides: { paper: { borderRadius: 10, border: `1px solid ${LINE}`, boxShadow: '0 12px 32px rgba(20,33,61,.14)' } },
    },
    MuiPopover: {
      styleOverrides: { paper: { borderRadius: 12, border: `1px solid ${LINE}`, boxShadow: '0 12px 32px rgba(20,33,61,.14)' } },
    },
    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: 10, alignItems: 'center' },
        action: { '& .MuiButton-text': { border: 'none', backgroundColor: 'transparent', color: 'inherit', '&:hover': { backgroundColor: 'rgba(0,0,0,.05)', color: 'inherit' } } },
      },
    },
    MuiTabs: {
      styleOverrides: { indicator: { height: 3, borderRadius: 3 } },
    },
    MuiTab: {
      styleOverrides: { root: { textTransform: 'none', fontWeight: 600, minHeight: 44 } },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: '#ffffff',
          '& fieldset': { borderColor: '#cfd7e2', transition: 'border-color .15s, box-shadow .15s' },
          '&:hover fieldset': { borderColor: '#9fb0cf' },
          '&.Mui-focused': { boxShadow: '0 0 0 3px rgba(31,79,163,.14)' },
          '&.Mui-error': { boxShadow: '0 0 0 3px rgba(179,38,30,.1)' },
        },
      },
    },
    MuiTextField: {
      defaultProps: { size: 'small' },
    },
    MuiDataGrid: {
      styleOverrides: {
        root: {
          border: `1px solid ${LINE}`,
          borderRadius: 10,
          backgroundColor: '#ffffff',
          '--DataGrid-t-header-background-base': '#f6f8fb',
          '& .MuiDataGrid-columnHeaders': { backgroundColor: '#f6f8fb' },
          '& .MuiDataGrid-columnHeaderTitle': {
            fontWeight: 600,
            fontSize: '0.78rem',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            color: INK_SOFT,
          },
          '& .MuiDataGrid-cell': { borderColor: LINE, '& .MuiButton-text': { border: 'none', backgroundColor: 'transparent', color: BRAND, minHeight: 28, padding: '2px 8px', '&:hover': { backgroundColor: BRAND_TINT, color: BRAND_DARK } } },
          '& .MuiDataGrid-row:hover': { backgroundColor: '#f9fafc' },
          '& .MuiDataGrid-cell:focus, & .MuiDataGrid-columnHeader:focus': { outline: 'none' },
        },
      },
    },
  },
});
