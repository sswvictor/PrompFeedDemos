import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';
import { Platform } from 'react-native';
import { registerPushToken, unregisterPushToken } from './api';

/**
 * Configure how notifications are shown when the app is in the foreground.
 * Call this once at app startup (in _layout.tsx).
 */
export function configureNotifications() {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge:  true,
    }),
  });
}

/**
 * Request permission and register the Expo push token with our backend.
 * Returns the token string, or null if permission was denied.
 * Safe to call multiple times - only asks for permission once.
 */
export async function registerForPushNotifications(): Promise<string | null> {
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'Default',
      importance: Notifications.AndroidImportance.MAX,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#C8A97E',
    });
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    console.log('[Notifications] Permission denied by user');
    return null;
  }

  const projectId =
    Constants.expoConfig?.extra?.eas?.projectId ??
    Constants.easConfig?.projectId;

  if (!projectId) {
    console.warn('[Notifications] No EAS projectId found in app.json - skipping push registration');
    return null;
  }

  const token = await Notifications.getExpoPushTokenAsync({ projectId });
  return token.data;
}

/**
 * Register the push token with the backend. Fire-and-forget - never throws.
 */
export async function saveTokenToBackend(token: string): Promise<void> {
  try {
    await registerPushToken(token);
    console.log('[Notifications] Push token registered with backend');
  } catch (err) {
    console.warn('[Notifications] Failed to register push token:', err);
  }
}

/**
 * Unregister push token from backend. Call on logout. Never throws.
 */
export async function removeTokenFromBackend(): Promise<void> {
  try {
    await unregisterPushToken();
  } catch {
    // ignore - token may already be gone
  }
}

export type NotificationData = {
  type: 'new_booking' | 'cancelled' | 'reminder' | string;
  booking_id?: string;
  provider_id?: string;
};
