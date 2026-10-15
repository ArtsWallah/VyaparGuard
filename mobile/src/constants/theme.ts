
/**
 * VyaparGuard app theme.
 * Uses a consistent green-and-white color palette.
 */

import '@/global.css';

import { Platform } from 'react-native';

export const Colors = {
  light: {
    text: '#102A43',
    background: '#F8FAFC',
    backgroundElement: '#E4F3ED',
    backgroundSelected: '#D1E9DF',
    textSecondary: '#64748B',
  },
  dark: {
    text: '#102A43',
    background: '#F8FAFC',
    backgroundElement: '#E4F3ED',
    backgroundSelected: '#D1E9DF',
    textSecondary: '#64748B',
  },
} as const;

export type ThemeColor = keyof typeof Colors.light & keyof typeof Colors.dark;

export const Fonts = Platform.select({
  ios: {
    /** iOS system font */
    sans: 'system-ui',
    serif: 'ui-serif',
    rounded: 'ui-rounded',
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-serif)',
    rounded: 'var(--font-rounded)',
    mono: 'var(--font-mono)',
  },
});

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const BottomTabInset =
  Platform.select({ ios: 50, android: 80 }) ?? 0;

export const MaxContentWidth = 800;
