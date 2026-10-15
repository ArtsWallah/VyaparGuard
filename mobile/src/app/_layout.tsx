
import { DarkTheme, DefaultTheme, ThemeProvider } from "expo-router";
import { Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useColorScheme } from "react-native";

import { AnimatedSplashOverlay } from "@/components/animated-icon";
import AppTabs from "@/components/app-tabs";

SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const colorScheme = useColorScheme();

  return (
    <ThemeProvider
      value={colorScheme === "dark" ? DarkTheme : DefaultTheme}
    >
      <AnimatedSplashOverlay />
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="scan" />
        <Stack.Screen name="camera" />
        <Stack.Screen name="upload" />
        <Stack.Screen name="result" />
      </Stack>
    </ThemeProvider>
  );
}
