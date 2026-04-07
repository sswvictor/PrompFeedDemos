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

function Para({ children }: { children: React.ReactNode }) {
  return (
    <Text className="text-fixme-text-muted text-sm leading-relaxed mb-2">{children}</Text>
  );
}

export default function TermsScreen() {
  return (
    <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>
      <ScrollView className="flex-1 px-5">
        {/* Header */}
        <View className="flex-row items-center gap-3 pt-6 mb-6">
          <Pressable onPress={() => router.back()}>
            <Text className="text-fixme-text-muted text-sm">\u2190</Text>
          </Pressable>
          <Text className="text-fixme-text-primary font-bold text-xl">Terms of Service</Text>
        </View>

        <Text className="text-fixme-text-muted text-xs mb-6">
          Effective date: 1 January 2026 \u00B7 App version {version}
        </Text>

        <Section title="1. Service description">
          <Para>
            FixMe (\u201Cthe Platform\u201D) is a marketplace that connects independent beauty and wellness
            providers with customers seeking appointments. FixMe provides software tools for booking
            management, client communication, and business analytics.
          </Para>
          <Para>
            FixMe is not a party to the service agreement between provider and customer. Providers
            are independent professionals responsible for the services they offer.
          </Para>
        </Section>

        <Section title="2. Provider obligations">
          <Para>
            As a provider you agree to: (a) provide accurate information about your services,
            pricing, and availability; (b) honour confirmed bookings or provide reasonable notice
            of cancellation; (c) treat all customers fairly and without discrimination; (d) comply
            with all applicable laws including tax obligations and professional licensing requirements.
          </Para>
        </Section>

        <Section title="3. Customer obligations">
          <Para>
            Customers agree to: (a) provide accurate contact information; (b) attend confirmed
            bookings or cancel with sufficient notice as per the provider\u2019s cancellation policy;
            (c) treat providers with respect.
          </Para>
        </Section>

        <Section title="4. Payments &amp; fees">
          <Para>
            FixMe charges a platform fee on each completed booking. Current fee schedules are
            communicated during onboarding and updated with 30 days\u2019 notice. Payments are
            processed by Stripe. FixMe never stores card numbers directly.
          </Para>
        </Section>

        <Section title="5. Cancellation policy">
          <Para>
            Each provider sets their own cancellation policy which is displayed to customers
            before booking. FixMe\u2019s default policy: cancellations made more than 24 hours before
            the appointment are free of charge. Late cancellations may incur a fee at the
            provider\u2019s discretion.
          </Para>
        </Section>

        <Section title="6. Data processing">
          <Para>
            By using FixMe you agree to our Privacy Policy (see Privacy screen). FixMe acts as a
            data processor for provider business data and a data controller for platform usage data.
            We process data in accordance with GDPR and applicable Swedish law.
          </Para>
        </Section>

        <Section title="7. Governing law">
          <Para>
            These terms are governed by the laws of Sweden. Any disputes shall be resolved in the
            courts of Stockholm, Sweden, unless mandatory consumer protection law requires otherwise.
          </Para>
        </Section>

        <Section title="8. Contact">
          <Para>
            Questions about these terms: legal@fixmeapp.ai
          </Para>
        </Section>

        <View className="h-10" />
      </ScrollView>
    </SafeAreaView>
  );
}
