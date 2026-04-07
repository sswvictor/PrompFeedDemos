import { View, Text, ScrollView, Pressable } from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import Constants from 'expo-constants';

const version = Constants.expoConfig?.version ?? '1.0.0';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View className="mb-6">
      <Text className="text-fixme-text-primary font-bold text-base mb-2">{title}</Text>
      {children}
    </View>
  );
}

function Para({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <Text className={`text-fixme-text-muted text-sm leading-relaxed mb-2${className ? ` ${className}` : ''}`}>{children}</Text>
  );
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <View className="flex-row gap-2 mb-1 pl-2">
      <Text className="text-fixme-text-muted text-sm">\u2022</Text>
      <Text className="text-fixme-text-muted text-sm leading-relaxed flex-1">{children}</Text>
    </View>
  );
}

export default function PrivacyScreen() {
  return (
    <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>
      <ScrollView className="flex-1 px-5">
        {/* Header */}
        <View className="flex-row items-center gap-3 pt-6 mb-6">
          <Pressable onPress={() => router.back()}>
            <Text className="text-fixme-text-muted text-sm">\u2190</Text>
          </Pressable>
          <Text className="text-fixme-text-primary font-bold text-xl">Privacy Policy</Text>
        </View>

        <Text className="text-fixme-text-muted text-xs mb-6">
          Effective date: 1 January 2026 \u00B7 App version {version}
        </Text>

        <Section title="1. Data we collect">
          <Para>When you use FixMe we collect:</Para>
          <Bullet>Account data: email address, name, phone number, business name</Bullet>
          <Bullet>Profile data: bio, service catalogue, working hours, location</Bullet>
          <Bullet>Booking data: scheduled times, service details, customer notes</Bullet>
          <Bullet>Instagram identity: Instagram user ID (to link DMs to bookings)</Bullet>
          <Bullet>Device data: Expo push token for push notifications (stored per device)</Bullet>
          <Bullet>Usage data: app interactions, error logs (anonymised)</Bullet>
        </Section>

        <Section title="2. How we use your data">
          <Bullet>Booking management: creating, confirming, and tracking appointments</Bullet>
          <Bullet>Notifications: email confirmations, reminders, and push alerts for new bookings</Bullet>
          <Bullet>Calendar sync: creating Google Calendar events for your bookings (only if you connect)</Bullet>
          <Bullet>Analytics: aggregated revenue and booking statistics shown in your Finance page</Bullet>
          <Bullet>Platform safety: fraud detection and reliability scoring</Bullet>
        </Section>

        <Section title="3. Third-party services">
          <Para>We share data only with the services required to operate the platform:</Para>
          <Bullet>Stripe \u2014 payment processing (card data never stored by FixMe)</Bullet>
          <Bullet>Google \u2014 calendar integration (only if you authorise it)</Bullet>
          <Bullet>Meta / Instagram \u2014 DM webhook for booking requests via Instagram</Bullet>
          <Bullet>Resend \u2014 transactional emails (booking confirmations, reminders)</Bullet>
          <Bullet>Expo / EAS \u2014 app updates and push notification delivery</Bullet>
          <Bullet>Railway \u2014 cloud database hosting (EU region)</Bullet>
        </Section>

        <Section title="4. Your rights (GDPR Art. 15\u201321)">
          <Bullet>Right of access \u2014 request a copy of all data we hold about you</Bullet>
          <Bullet>Right to rectification \u2014 correct inaccurate data</Bullet>
          <Bullet>Right to erasure \u2014 delete your account and all associated data</Bullet>
          <Bullet>Right to restriction \u2014 limit how we process your data</Bullet>
          <Bullet>Right to portability \u2014 receive your data in a machine-readable format</Bullet>
          <Bullet>Right to object \u2014 object to processing based on legitimate interests</Bullet>
          <Para className="mt-2">
            To exercise any of these rights, contact: privacy@fixmeapp.ai
          </Para>
        </Section>

        <Section title="5. Data retention">
          <Para>
            Booking data is retained for 3 years from the date of the appointment, in line with
            Swedish bookkeeping requirements. Account data is deleted within 30 days of account
            closure. Push tokens are deleted immediately on logout.
          </Para>
        </Section>

        <Section title="6. Cookies &amp; tracking">
          <Para>
            The mobile app does not use browser cookies. We use anonymised crash reporting and
            performance monitoring which does not identify you personally.
          </Para>
        </Section>

        <Section title="7. Contact">
          <Para>
            Data controller: Fixmeapp AB, Stockholm, Sweden{'\n'}
            Privacy enquiries: privacy@fixmeapp.ai{'\n'}
            GDPR complaints can also be filed with the Swedish Authority for Privacy Protection
            (IMY): imy.se
          </Para>
        </Section>

        <View className="h-10" />
      </ScrollView>
    </SafeAreaView>
  );
}
