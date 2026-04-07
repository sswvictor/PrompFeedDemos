import { useState } from 'react';
import {
  View, Text, Pressable, ScrollView,
  ActivityIndicator, Alert,
} from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as WebBrowser from 'expo-web-browser';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getProviderCalendarConnections, getCalendarConnectUrl,
  disconnectCalendar, exchangeCalendarCode,
  type CalendarConnection,
} from '@/lib/api';
import { colors } from '@/theme';

// Warm up the browser on Android for faster open
WebBrowser.maybeCompleteAuthSession();

// The redirect URI we tell Google to send back to.
// Must match what's registered in the Google Console and backend.
const REDIRECT_URI = 'fixmeapp://calendar-callback';

const CONNECTOR_LABEL: Record<string, string> = {
  google:    'Google Calendar',
  microsoft: 'Outlook / Microsoft 365',
};

const CONNECTOR_ICON: Record<string, string> = {
  google:    '\uD83D\uDCC5',
  microsoft: '\uD83D\uDCCB',
};

function ConnectionCard({
  connection,
  onDisconnect,
  disconnecting,
}: {
  connection: CalendarConnection;
  onDisconnect: () => void;
  disconnecting: boolean;
}) {
  const label = CONNECTOR_LABEL[connection.connector] ?? connection.connector;
  const icon  = CONNECTOR_ICON[connection.connector] ?? '\uD83D\uDD17';

  return (
    <View className="bg-fixme-card border border-fixme-border rounded-2xl px-4 py-4 mb-3">
      <View className="flex-row items-center gap-3 mb-3">
        <Text className="text-2xl">{icon}</Text>
        <View className="flex-1">
          <Text className="text-fixme-text-primary font-semibold text-sm">{label}</Text>
          {connection.display_name ? (
            <Text className="text-fixme-text-muted text-xs mt-0.5">{connection.display_name}</Text>
          ) : null}
        </View>
        <View className="px-2 py-1 rounded-full bg-green-900/30">
          <Text className="text-green-400 text-xs font-semibold">Connected</Text>
        </View>
      </View>

      <View className="flex-row items-center gap-2 mb-1">
        <View className={`w-2 h-2 rounded-full ${connection.sync_enabled ? 'bg-green-400' : 'bg-fixme-text-muted'}`} />
        <Text className="text-fixme-text-muted text-xs">
          {connection.sync_enabled ? 'Sync enabled \u2014 bookings push automatically' : 'Sync paused'}
        </Text>
      </View>

      <Pressable
        onPress={onDisconnect}
        disabled={disconnecting}
        className="mt-3 border border-red-800/40 rounded-xl py-2.5 items-center active:opacity-70 disabled:opacity-50"
      >
        {disconnecting
          ? <ActivityIndicator color="#E53935" size="small" />
          : <Text className="text-red-400 text-sm font-semibold">Disconnect</Text>
        }
      </Pressable>
    </View>
  );
}

function ConnectCard({
  connector,
  onConnect,
  connecting,
}: {
  connector: string;
  onConnect: () => void;
  connecting: boolean;
}) {
  const label = CONNECTOR_LABEL[connector] ?? connector;
  const icon  = CONNECTOR_ICON[connector] ?? '\uD83D\uDD17';

  return (
    <View className="bg-fixme-card border border-fixme-border rounded-2xl px-4 py-4 mb-3">
      <View className="flex-row items-center gap-3 mb-3">
        <Text className="text-2xl">{icon}</Text>
        <View className="flex-1">
          <Text className="text-fixme-text-primary font-semibold text-sm">{label}</Text>
          <Text className="text-fixme-text-muted text-xs mt-0.5">
            Bookings sync automatically as calendar events
          </Text>
        </View>
      </View>
      <Pressable
        onPress={onConnect}
        disabled={connecting}
        className="bg-fixme-accent rounded-xl py-3 items-center active:opacity-80 disabled:opacity-50"
      >
        {connecting
          ? <ActivityIndicator color="#0D0D0D" />
          : <Text className="text-fixme-bg text-sm font-bold">Connect {label}</Text>
        }
      </Pressable>
    </View>
  );
}

export default function CalendarSettingsScreen() {
  const queryClient = useQueryClient();
  const [connectingId, setConnectingId] = useState<string | null>(null);

  const { data: connections = [], isLoading } = useQuery({
    queryKey: ['calendar-connections'],
    queryFn: getProviderCalendarConnections,
  });

  const disconnectMut = useMutation({
    mutationFn: (connectionId: string) => disconnectCalendar(connectionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['calendar-connections'] }),
    onError: (err: Error) => Alert.alert('Error', err.message),
  });

  async function handleConnect(connector: string) {
    setConnectingId(connector);
    try {
      // Step 1: get the Google OAuth URL + state token from our backend
      const { auth_url, state } = await getCalendarConnectUrl(connector);

      // Step 2: open an in-app browser session.
      // openAuthSessionAsync intercepts any redirect matching our app scheme
      // (fixmeapp://) and returns the full URL to us instead of navigating away.
      const result = await WebBrowser.openAuthSessionAsync(auth_url, REDIRECT_URI);

      if (result.type === 'cancel' || result.type === 'dismiss') {
        // User closed the browser — nothing to do
        return;
      }

      if (result.type !== 'success' || !result.url) {
        Alert.alert('Error', 'Calendar connection did not complete.');
        return;
      }

      // Step 3: parse code (and optionally error) from the redirect URL
      const redirectUrl = new URL(result.url);
      const oauthError = redirectUrl.searchParams.get('error');
      if (oauthError) {
        Alert.alert(
          'Connection cancelled',
          oauthError === 'access_denied'
            ? 'You declined access to Google Calendar.'
            : `Google returned an error: ${oauthError}`,
        );
        return;
      }

      const code = redirectUrl.searchParams.get('code');
      const returnedState = redirectUrl.searchParams.get('state') ?? state;

      if (!code) {
        Alert.alert('Error', 'No authorisation code returned from Google.');
        return;
      }

      // Step 4: exchange the code with our backend
      await exchangeCalendarCode(connector, code, returnedState);

      // Step 5: refresh the connections list
      await queryClient.invalidateQueries({ queryKey: ['calendar-connections'] });

    } catch (err: unknown) {
      Alert.alert('Error', (err as Error).message || 'Could not connect calendar.');
    } finally {
      setConnectingId(null);
    }
  }

  function confirmDisconnect(connection: CalendarConnection) {
    const label = CONNECTOR_LABEL[connection.connector] ?? connection.connector;
    Alert.alert(
      'Disconnect calendar',
      `Disconnect ${label}? Future bookings won\u2019t sync until you reconnect.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Disconnect',
          style: 'destructive',
          onPress: () => disconnectMut.mutate(connection.connection_id),
        },
      ],
    );
  }

  const connectedIds = new Set(connections.map(c => c.connector));
  const availableToConnect = ['google'].filter(c => !connectedIds.has(c));

  if (isLoading) {
    return (
      <SafeAreaView className="flex-1 bg-fixme-bg items-center justify-center">
        <ActivityIndicator color={colors.accent} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>
      <ScrollView className="flex-1 px-5">
        {/* Header */}
        <View className="flex-row items-center gap-3 pt-6 mb-6">
          <Pressable onPress={() => router.back()}>
            <Text className="text-fixme-text-muted text-sm">\u2190</Text>
          </Pressable>
          <Text className="text-fixme-text-primary font-bold text-xl">Calendar Sync</Text>
        </View>

        {/* Info banner */}
        <View className="bg-fixme-card border border-fixme-border rounded-2xl px-4 py-3 mb-6 flex-row items-start gap-3">
          <Text className="text-lg">\uD83D\uDCC5</Text>
          <Text className="text-fixme-text-muted text-xs leading-relaxed flex-1">
            Connect your calendar to automatically create events for each booking. Your clients will never see your calendar.
          </Text>
        </View>

        {/* Connected calendars */}
        {connections.length > 0 && (
          <>
            <Text className="text-fixme-text-secondary text-xs font-semibold mb-3 uppercase tracking-wider">
              Connected
            </Text>
            {connections.map(conn => (
              <ConnectionCard
                key={conn.connection_id}
                connection={conn}
                onDisconnect={() => confirmDisconnect(conn)}
                disconnecting={disconnectMut.isPending && disconnectMut.variables === conn.connection_id}
              />
            ))}
          </>
        )}

        {/* Available to connect */}
        {availableToConnect.length > 0 && (
          <>
            <Text className="text-fixme-text-secondary text-xs font-semibold mb-3 mt-2 uppercase tracking-wider">
              Add calendar
            </Text>
            {availableToConnect.map(connector => (
              <ConnectCard
                key={connector}
                connector={connector}
                onConnect={() => handleConnect(connector)}
                connecting={connectingId === connector}
              />
            ))}
          </>
        )}

        {connections.length === 0 && availableToConnect.length === 0 && (
          <View className="items-center py-12">
            <Text className="text-fixme-text-muted text-sm">No calendar integrations available.</Text>
          </View>
        )}

        <View className="h-10" />
      </ScrollView>
    </SafeAreaView>
  );
}
