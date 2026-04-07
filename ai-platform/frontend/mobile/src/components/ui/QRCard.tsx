/**
 * QRCard — displays a QR code inside an elegant framed card.
 *
 * Design: pure white card on dark bg — the QR code needs white
 * surrounding it to scan. Generous padding, rounded corners,
 * subtle shadow on iOS. Below the card: a muted caption and share button.
 *
 * Usage:
 *   <QRCard value="https://fixmeapp.se/book/emma" onShare={handleShare} />
 *   <QRCard value={bookingUrl} label="Share with clients to book directly" onShare={handleShare} />
 *
 *   // Loading / not ready
 *   <QRCard value={null} />
 */

import { Share, Text, View } from 'react-native';
import QRCode from 'react-native-qrcode-svg';
import { Button } from './Button';

interface QRCardProps {
  value: string | null;
  label?: string;
  onShare?: () => void;
  size?: number;
}

export function QRCard({
  value,
  label = 'Share this code with clients so they can book directly.',
  onShare,
  size = 200,
}: QRCardProps) {
  async function handleShare() {
    if (onShare) { onShare(); return; }
    if (value) {
      await Share.share({ message: value, url: value });
    }
  }

  return (
    <View className="items-center px-5">

      {/* QR frame — always white so the scanner can read it */}
      <View
        className="rounded-3xl overflow-hidden mb-7"
        style={{
          backgroundColor: '#FFFFFF',
          padding: 24,
          // Lift the card with a subtle shadow (iOS)
          shadowColor: '#000000',
          shadowOpacity: 0.12,
          shadowRadius: 24,
          shadowOffset: { width: 0, height: 8 },
          elevation: 8, // Android
        }}
      >
        {value ? (
          <QRCode
            value={value}
            size={size}
            backgroundColor="#FFFFFF"
            color="#111110"
          />
        ) : (
          <View
            style={{ width: size, height: size }}
            className="items-center justify-center bg-fixme-light-bg-soft"
          >
            <Text className="text-fixme-light-text-muted text-[13px] text-center px-4 leading-[19px]">
              QR code not available yet
            </Text>
          </View>
        )}
      </View>

      {/* Caption */}
      <Text className="
        text-[13px] text-center leading-[19px] mb-7 px-6
        text-fixme-light-text-muted dark:text-fixme-text-muted
      ">
        {label}
      </Text>

      {/* Share button */}
      {value && (
        <Button size="lg" onPress={handleShare} fullWidth>
          Share booking link
        </Button>
      )}

    </View>
  );
}
