/**
 * ThemeContext — user-controlled dark / light / system theme.
 *
 * Usage:
 *   const { isDark, mode, setMode } = useTheme();
 *   setMode('light')   → warm editorial light mode
 *   setMode('dark')    → Uber-style dark mode
 *   setMode('system')  → follows device setting
 *
 * NativeWind's useColorScheme() is the engine — setting it here
 * makes all `dark:` Tailwind classes activate/deactivate automatically.
 * Preference is persisted to AsyncStorage so it survives app restarts.
 */

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useColorScheme as useNativeColorScheme } from 'react-native';
import { useColorScheme } from 'nativewind';
import * as SecureStore from 'expo-secure-store';

export type ThemeMode = 'dark' | 'light' | 'system';

interface ThemeContextValue {
  /** What the user explicitly chose */
  mode: ThemeMode;
  /** Resolved value — true when dark is active */
  isDark: boolean;
  /** Call this to change theme and persist the choice */
  setMode: (mode: ThemeMode) => Promise<void>;
}

const STORAGE_KEY = '@fixme/theme-mode';

const ThemeContext = createContext<ThemeContextValue>({
  mode:    'dark',
  isDark:  true,
  setMode: async () => {},
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const systemScheme                    = useNativeColorScheme();      // 'dark' | 'light' | null
  const { colorScheme, setColorScheme } = useColorScheme();            // nativewind engine
  const [mode, setModeState]            = useState<ThemeMode>('dark'); // user's choice

  // Load persisted preference on first mount
  useEffect(() => {
    SecureStore.getItemAsync(STORAGE_KEY).then((saved) => {
      if (saved === 'dark' || saved === 'light' || saved === 'system') {
        applyMode(saved, false); // apply without re-saving
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function applyMode(newMode: ThemeMode, save = true) {
    setModeState(newMode);

    if (newMode === 'system') {
      // Let NativeWind follow the OS
      setColorScheme('system' as 'dark' | 'light'); // nativewind v4 accepts 'system'
    } else {
      setColorScheme(newMode);
    }

    if (save) {
      SecureStore.setItemAsync(STORAGE_KEY, newMode);
    }
  }

  const isDark =
    mode === 'system'
      ? systemScheme === 'dark'   // fall back to system
      : colorScheme === 'dark';   // trust nativewind's resolved value

  const setMode = async (newMode: ThemeMode) => applyMode(newMode);

  return (
    <ThemeContext.Provider value={{ mode, isDark, setMode }}>
      {children}
    </ThemeContext.Provider>
  );
}

/** Drop-in hook — use anywhere inside <ThemeProvider> */
export function useTheme() {
  return useContext(ThemeContext);
}
