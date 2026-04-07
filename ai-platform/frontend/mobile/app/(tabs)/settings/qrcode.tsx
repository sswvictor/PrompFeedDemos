import { useCallback } from 'react';
import { View, Text, Pressable, Share, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import QRCode from 'react-native-qrcode-svg';
import { useAuth } from '@/stores/auth';

const BASE_URL = 'https://fixmeapp.ai';

export default function QRCodeScreen() {
  const { providerSlug, providerName } = useAuth();
  const url = providerSlug ? `${BASE_URL}/p/${providerSlug}` : null;

  const handleShare = useCallback(async () => {
    if (!url) return;
    try {
      await Share.share({
        message: `Book with ${providerName || 'us'}: ${url}`,
        url,
      });
    } catch {
      Alert.alert('Could not share', 'Please try again.');
    }
  }, [url, providerName]);

  return (
    <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>
      {/* Header */}
      <Pressable
        onPress={() => router.back()}
        className="flex-row items-center gap-2 px-5 pt-4 pb-2 active:opacity-60 self-start"
      >
        <Text className="text-fixme-text-secondary text-base">{'\u2190'}</Text>
        <Text className="text-fixme-text-secondary text-base">Back</Text>
      </Pressable>

      {/* Content */}
      <View className="flex-1 items-center justify-center px-8">
        <Text className="text-fixme-text-muted text-xs uppercase tracking-widest mb-10">
          Booking QR code
        </Text>

        {/* White card — white bg required for QR scanning */}
        <View
          className="bg-white rounded-3xl p-8 items-center"
          style={{
            shadowColor: '#F5F5F0',
            shadowOpacity: 0.12,
            shadowRadius: 40,
            shadowOffset: { width: 0, height: 0 },
            elevation: 12,
          }}
        >
          {url ? (
            <QRCode
              value={url}
              size={220}
              color="#0A0A0A"
              backgroundColor="white"
            />
          ) : (
            <View style={{ width: 220, height: 220 }} className="items-center justify-center">
              <Text className="text-gray-400 text-sm text-center leading-relaxed">
                Complete your profile{'\n'}to activate your booking link.
              </Text>
            </View>
          )}

          <View className="mt-6 items-center w-full border-t border-gray-100 pt-5">
            <Text className="text-gray-900 font-bold text-xl text-center">
              {providerName || 'Your salon'}
            </Text>
            <Text className="text-gray-500 text-sm mt-1">Scan to book an appointment</Text>
          </View>
        </View>

        <Text className="text-fixme-text-muted text-xs text-center leading-relaxed mt-8 px-2">
          Leave this open on your counter or tablet.{'\n'}
          Customers scan, pick a service, and book themselves.
        </Text>
      </View>

      {/* Share button */}
      <View className="px-5 pb-6">
        <Pressable
          onPress={handleShare}
          disabled={!url}
          className="bg-fixme-accent rounded-2xl py-4 items-center disabled:opacity-40"
        >
          <Text className="text-fixme-bg font-bold text-base">Share booking link</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}
