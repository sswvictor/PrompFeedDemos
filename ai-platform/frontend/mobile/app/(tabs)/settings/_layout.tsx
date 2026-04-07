import { Stack } from 'expo-router';

/**
 * Settings nested stack — sits inside the Tabs group but behaves as a
 * proper push-navigation with back gestures between settings screens.
 * The Tabs layout registers "settings" as a single hidden tab (href: null).
 */
export default function SettingsLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
