import { IconButton, Tooltip } from '@mui/material';
import { useColorScheme } from '@mui/material/styles';
import DarkMode from '@mui/icons-material/DarkModeOutlined';
import LightMode from '@mui/icons-material/LightModeOutlined';
import SettingsBrightness from '@mui/icons-material/SettingsBrightnessOutlined';

const NEXT = { light: 'dark', dark: 'system', system: 'light' } as const;

/** Cycles light → dark → follow system. The choice is remembered by MUI in localStorage (per browser). */
export function ColorModeToggle() {
  const { mode, setMode } = useColorScheme();
  if (!mode) return null;
  const label = { light: 'Light theme', dark: 'Dark theme', system: 'Match system theme' }[mode];
  return (
    <Tooltip title={`${label} (click to change)`}>
      <IconButton aria-label={`${label}. Change theme`} onClick={() => setMode(NEXT[mode])} color="inherit">
        {mode === 'light' ? <LightMode /> : mode === 'dark' ? <DarkMode /> : <SettingsBrightness />}
      </IconButton>
    </Tooltip>
  );
}
