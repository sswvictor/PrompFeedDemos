import '../global.css';
import { useEffect } from 'react';
import { View } from 'react-native';
import { Stack, router } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import * as SplashScreen from 'expo-splash-screen';
import * as Notifications from 'expo-notifications';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuth } from '@/stores/auth';
import { configureNotifications, NotificationData } from '@/lib/notifications';
import { getProviderSession } from '@/lib/api';
import { colors } from '@/theme';

SplashScreen.preventAutoHideAsync();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

configureNotifications();

export default function RootLayout() {
  const { token, isHydrated, rehydrate, clearAuth } = useAuth();

  useEffect(() => {
    rehydrate().then(() => SplashScreen.hideAsync());
  }, [rehydrate]);

  // Foreground notification: refresh home data when new booking arrives
  useEffect(() => {
    const sub = Notifications.addNotificationReceivedListener((notification) => {
      const data = notification.request.content.data as NotificationData;
      if (data?.type === 'new_booking' || data?.type === 'cancelled') {
        queryClient.invalidateQueries({ queryKey: ['home-dashboard'] });
      }
    });
    return () => sub.remove();
  }, []);

  // Background tap: navigate to home screen
  useEffect(() => {
    const sub = Notifications.addNotificationResponseReceivedListener((response) => {
      const data = response.notification.request.content.data as NotificationData;
      if (data?.type) {
        router.push('/(tabs)/');
      }
    });
    return () => sub.remove();
  }, []);

  // Route guard: wait until SecureStore hydration completes, then validate token.
  useEffect(() => {
    if (!isHydrated) return;
    let cancelled = false;

    const guard = async () => {
      if (!token) {
        router.replace('/(auth)/welcome');
        return;
      }

      try {
        await getProviderSession(token);
        if (!cancelled) router.replace('/(tabs)/');
      } catch {
        if (cancelled) return;
        await clearAuth();
        router.replace('/(auth)/welcome');
      }
    };

    guard();

    return () => {
      cancelled = true;
    };
  }, [isHydrated, token, clearAuth]);

  if (!isHydrated) return <View style={{ flex: 1, backgroundColor: colors.bg }} />;

  return (
    <QueryClientProvider client={queryClient}>
      <StatusBar style="light" backgroundColor={colors.bg} />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg } }} />
    </QueryClientProvider>
  );
}
