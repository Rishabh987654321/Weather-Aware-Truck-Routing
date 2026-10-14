import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: 'var(--primary)',
      light: 'var(--primary)',
      dark: 'var(--primary-press)',
      contrastText: 'var(--white)',
    },
    text: { primary: 'var(--ink)', secondary: 'var(--ink-2)' },
    background: { default: 'var(--ground)', paper: 'var(--panel)' },
  },
  shape: { borderRadius: 4 },
  typography: {
    fontFamily: "'Barlow', system-ui, sans-serif",
    button: { textTransform: 'none', fontWeight: 600 },
  },
  components: {
    MuiButtonBase: { defaultProps: { disableRipple: true } },
    MuiPaper: { defaultProps: { elevation: 0 } },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 'var(--r-sm)',
          background: 'var(--field)',
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: 'var(--line)',
          },
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: 'var(--ink-2)',
          },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: 'var(--primary)',
            borderWidth: '2px',
          },
        },
      },
    },
  },
});
