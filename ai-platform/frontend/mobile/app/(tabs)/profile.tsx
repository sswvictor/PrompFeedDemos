import { useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  Pressable,
  ScrollView,
  ActivityIndicator,
  Share,
  Linking,
  Alert,
  Image,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@tanstack/react-query';
import { router } from 'expo-router';

import {
  getProviderProfileById,
  getProviderProfileBySlug,
  type ProviderPublicProfile,
  type ProviderPublicService,
} from '@/lib/api';
import { useAuth } from '@/stores/auth';
import { colors } from '@/theme';
import { SegmentedControl, Avatar, Badge, Tabs, Pill, SectionHeader, Card, Button, EmptyState } from '@/components/ui';
import { BookingFlow } from './booking-flow';

type ProfileTab = 'about' | 'services' | 'reviews';
type ServiceSubTab = 'menu' | 'book';
type ProfileMode = 'provider' | 'customer';

const DAY_ORDER = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const;

const AMENITY_LABELS: Record<string, string> = {
  dog_friendly: 'Dogs welcome',
  wheelchair_accessible: 'Accessible',
  parking: 'Free parking',
  wifi: 'Free Wi-Fi',
  coffee: 'Coffee and tea',
  wine: 'Wine and drinks',
  eco_friendly: 'Eco friendly',
  home_visits: 'Home visits',
  private_studio: 'Private studio',
  child_friendly: 'Child friendly',
  evening_hours: 'Evening hours',
  card_payment: 'Card payment',
};

function toInitials(name?: string | null) {
  const src = (name || '?').trim();
  if (!src) return '?';
  return src
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('');
}

function fmtCount(value?: number | null) {
  if (value == null) return '-';
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(value);
}

import { formatPrice } from '@/utils/currency';
function fmtSek(value?: number | null, currency = 'SEK') {
  if (value == null) return '-';
  return formatPrice(value, currency);
}

function resolveBookingUrl(profile?: ProviderPublicProfile | null): string | null {
  const raw = profile?.booking_url?.trim();
  if (!raw) return null;
  if (raw.startsWith('http://') || raw.startsWith('https://')) return raw;
  if (raw.startsWith('/')) return `https://fixmeapp.ai${raw}`;
  return `https://fixmeapp.ai/${raw}`;
}

function StatItem({ value, label }: { value: string; label: string }) {
  return (
    <View className="flex-1 items-center px-2 py-2">
      <Text className="text-fixme-text-primary font-bold text-base">{value}</Text>
      <Text className="text-fixme-text-muted text-[11px] mt-0.5">{label}</Text>
    </View>
  );
}

// SectionTitle + ServiceMenuCard removed — using library components

export default function ProfileScreen() {
  const { providerId, providerSlug, providerName } = useAuth();

  const [tab, setTab] = useState<ProfileTab>('about');
  const [serviceSubTab, setServiceSubTab] = useState<ServiceSubTab>('menu');
  const [profileMode, setProfileMode] = useState<ProfileMode>('provider');
  const [activeCategory, setActiveCategory] = useState('all');
  const [selectedService, setSelectedService] = useState<ProviderPublicService | null>(null);
  const [bookingFlowVisible, setBookingFlowVisible] = useState(false);
  const [bookingFlowService, setBookingFlowService] = useState<ProviderPublicService | null>(null);
  const [isFollowing, setIsFollowing] = useState(false);
  const [followerDelta, setFollowerDelta] = useState(0);

  const profileQuery = useQuery({
    queryKey: ['provider-profile-public', providerId, providerSlug],
    enabled: Boolean(providerId || providerSlug),
    queryFn: async () => {
      if (providerId) return getProviderProfileById(providerId);
      if (providerSlug) return getProviderProfileBySlug(providerSlug);
      throw new Error('Provider session missing');
    },
  });

  const hasSession = Boolean(providerId || providerSlug);
  const fallbackProfile = useMemo<ProviderPublicProfile>(() => ({
    provider_id: providerId || providerSlug || 'pending-provider',
    name: providerName || 'Your business',
    city: null,
    bio: '',
    image_url: null,
    ig_profile_picture_url: null,
    instagram_username: null,
    slug: providerSlug || null,
    services: [],
    amenities: [],
    categories: [],
    working_hours: {},
    booking_policy: null,
    cancellation_policy: null,
    booking_url: null,
    fixmeapp_followers_count: 0,
    ig_followers_count: 0,
    ig_following_count: 0,
    is_verified: false,
    level_badge: 'Member',
    trust: {
      rating: 5.0,
      review_count: 0,
      revisit_rate: 0,
      total_completed_bookings: 0,
    },
  }), [providerId, providerSlug, providerName]);

  const profile = profileQuery.data ?? fallbackProfile;
  const hasRealProfile = Boolean(profileQuery.data);
  const bookingUrl = resolveBookingUrl(profile);
  const avatarUrl = profile?.ig_profile_picture_url || profile?.image_url || null;
  const baseFollowers = profile?.ig_followers_count ?? profile?.fixmeapp_followers_count ?? 0;
  const shownFollowers = Math.max(0, baseFollowers + followerDelta);
  const shownFollowing = profile?.ig_following_count ?? null;

  useEffect(() => {
    setFollowerDelta(0);
    setIsFollowing(false);
  }, [profile?.provider_id]);

  const categories = useMemo(() => {
    const serviceCategories = (profile?.services ?? [])
      .map((service) => (service.category || '').trim())
      .filter(Boolean);
    return ['all', ...Array.from(new Set(serviceCategories))];
  }, [profile?.services]);

  const filteredServices = useMemo(() => {
    const services = profile?.services ?? [];
    if (activeCategory === 'all') return services;
    return services.filter(
      (service) => (service.category || '').toLowerCase() === activeCategory.toLowerCase(),
    );
  }, [profile?.services, activeCategory]);

  async function handleShareBookingLink() {
    if (!bookingUrl) return;
    try {
      await Share.share({ message: bookingUrl, url: bookingUrl });
    } catch {
      Alert.alert('Could not share', 'Please try again.');
    }
  }

  async function handleOpenBookingPage() {
    if (!bookingUrl) return;
    try {
      await Linking.openURL(bookingUrl);
    } catch {
      Alert.alert('Could not open link', bookingUrl);
    }
  }

  function openBookingForService(service: ProviderPublicService) {
    setSelectedService(service);
    setBookingFlowService(service);
    setBookingFlowVisible(true);
  }

  function openBookingFlow(service: ProviderPublicService) {
    setBookingFlowService(service);
    setBookingFlowVisible(true);
  }

  function toggleFollow() {
    if (isFollowing) {
      setIsFollowing(false);
      setFollowerDelta((v) => v - 1);
      return;
    }
    setIsFollowing(true);
    setFollowerDelta((v) => v + 1);
  }

  if (profileQuery.isLoading && hasSession) {
    return (
      <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator color={colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  const hours = DAY_ORDER.map((day) => {
    const slot = profile.working_hours?.[day];
    if (!slot?.open) return { day, text: 'Closed' };
    return {
      day,
      text: `${slot.start || '--:--'} - ${slot.end || '--:--'}`,
    };
  });

  return (
    <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>
      <ScrollView className="flex-1" contentContainerStyle={{ paddingBottom: 22 }}>
        <View className="px-5 pt-6 pb-3 flex-row items-center justify-between">
          <Text className="text-fixme-text-primary font-bold text-2xl">Profile</Text>
          {profileMode === 'provider' ? (
            <Pressable
              onPress={() => router.push('/(tabs)/settings' as any)}
              className="w-9 h-9 rounded-full border border-fixme-border bg-fixme-card items-center justify-center"
            >
              <Text className="text-fixme-text-secondary text-base">{"\u2699"}</Text>
            </Pressable>
          ) : (
            <View className="w-9 h-9" />
          )}
        </View>

        <View className="px-5">
          <SegmentedControl
            options={['Provider view', 'Customer view']}
            activeIndex={profileMode === 'provider' ? 0 : 1}
            onChange={(i) => setProfileMode(i === 0 ? 'provider' : 'customer')}
            className="mb-3"
          />
          <View className="px-2 mt-2">
            <View className="flex-row">
              <StatItem value={profile.level_badge || 'Member'} label="Level" />
              <StatItem value={fmtCount(shownFollowing)} label="Following" />
              <StatItem value={fmtCount(shownFollowers)} label="Followers" />
            </View>
          </View>

          <View className="flex-row items-center gap-4 mt-4">
            <Avatar
              name={profile.name || 'Provider'}
              uri={avatarUrl}
              size="xl"
            />
            <View className="flex-1">
              <View className="flex-row items-center flex-wrap gap-2">
                <Text className="text-fixme-text-primary font-bold text-lg">{profile.name || 'Provider'}</Text>
                {profile.is_verified ? (
                  <Badge variant="success" dot>Verified</Badge>
                ) : null}
              </View>
              {profile.instagram_username ? (
                <Text className="text-fixme-text-muted text-sm mt-0.5">@{profile.instagram_username}</Text>
              ) : null}
              <Text className="text-fixme-text-secondary text-xs mt-1.5">
                ⭐ {(profile.trust?.rating || 5.0).toFixed(1)}
              </Text>
              {profile.city ? (
                <Text className="text-fixme-text-muted text-xs mt-0.5">📍 {profile.city}</Text>
              ) : null}
            </View>
          </View>

          {profileMode === 'provider' ? (
            <>
              <View className="flex-row gap-3 mt-8 mb-5 justify-center">
                <Button variant="ghost" size="xs" onPress={() => router.push('/settings/profile' as any)} className="flex-1">
                  Edit profile
                </Button>
                <Button variant="ghost" size="xs" onPress={handleShareBookingLink} disabled={!bookingUrl} className="flex-1">
                  Share link
                </Button>
                <Button variant="ghost" size="xs" onPress={() => router.push('/settings/qrcode' as any)} className="flex-1">
                  📲 QR code
                </Button>
              </View>
            </>
          ) : (
            <View className="flex-row gap-3 mt-8 mb-5 justify-center">
              <Button variant="ghost" size="xs" onPress={() => Alert.alert('Coming soon', 'Unified inbox for customer messages is coming soon.')} className="flex-1">
                Message
              </Button>
              <Button size="xs" onPress={toggleFollow} className="flex-1">
                {isFollowing ? 'Following' : 'Follow'}
              </Button>
            </View>
          )}
        </View>

        <Tabs
          tabs={['About', 'Services', 'Reviews']}
          activeIndex={['about', 'services', 'reviews'].indexOf(tab)}
          onChange={(i) => setTab((['about', 'services', 'reviews'] as const)[i])}
          className="mt-5"
        />

        {tab === 'about' ? (
          <View className="px-5">
            <SectionHeader label="About" className="mt-4 mb-2" />
            <Text className="text-fixme-text-secondary text-sm leading-relaxed">
              {profile.bio || 'No bio yet. Add one in Settings → Profile.'}
            </Text>

            <SectionHeader label="Working hours" />
            <Card padding="none">
              {hours.map((row, idx) => (
                <View
                  key={row.day}
                  className="flex-row items-center justify-between px-4 py-3"
                  style={idx < hours.length - 1 ? { borderBottomWidth: 1, borderBottomColor: colors.border } : {}}
                >
                  <Text className="text-fixme-text-muted text-xs">{row.day}</Text>
                  <Text className="text-fixme-text-secondary text-xs font-medium">{row.text}</Text>
                </View>
              ))}
            </Card>

            <SectionHeader label="Policies" />
            <Card className="gap-4">
              <View>
                <Text className="text-fixme-text-muted text-[11px] uppercase tracking-wider">Booking policy</Text>
                <Text className="text-fixme-text-secondary text-sm mt-1 leading-relaxed">
                  {profile.booking_policy || 'Not specified'}
                </Text>
              </View>
              <View>
                <Text className="text-fixme-text-muted text-[11px] uppercase tracking-wider">Cancellation policy</Text>
                <Text className="text-fixme-text-secondary text-sm mt-1 leading-relaxed">
                  {profile.cancellation_policy || 'Not specified'}
                </Text>
              </View>
            </Card>

            <SectionHeader label="Amenities" count={(profile.amenities ?? []).length || undefined} />
            <View className="flex-row flex-wrap gap-2">
              {(profile.amenities ?? []).length > 0 ? (
                (profile.amenities ?? []).map((key) => (
                  <Pill
                    key={key}
                    label={AMENITY_LABELS[key] || key.replace(/_/g, ' ')}
                    selected={false}
                    onPress={() => {}}
                    size="sm"
                  />
                ))
              ) : (
                <Text className="text-fixme-text-muted text-xs">No amenities listed.</Text>
              )}
            </View>

            <SectionHeader label="Location" />
            <Text className="text-fixme-text-secondary text-sm">
              {profile.location_salon || profile.city || 'No location set'}
            </Text>

            <SectionHeader label="Certifications" />
            {profileMode === 'provider' ? (
              <Card padding="sm">
                <View className="flex-row items-center gap-3">
                  <Text style={{ fontSize: 28 }}>📜</Text>
                  <View className="flex-1">
                    <Text className="text-fixme-text-primary text-sm font-semibold">Add your certifications</Text>
                    <Text className="text-fixme-text-muted text-xs mt-0.5">
                      Diplomas, licenses and certificates build trust with customers
                    </Text>
                  </View>
                </View>
                <Button variant="ghost" size="xs" onPress={() => Alert.alert('Coming soon', 'Certification upload will be available soon.')} fullWidth className="mt-3">
                  Upload certification
                </Button>
              </Card>
            ) : (
              <View className="mb-6">
                {profile.is_verified ? (
                  <View className="flex-row items-center gap-2">
                    <Badge variant="success" dot>Verified professional</Badge>
                  </View>
                ) : (
                  <Text className="text-fixme-text-muted text-xs">No certifications uploaded yet.</Text>
                )}
              </View>
            )}
          </View>
        ) : null}

        {tab === 'services' ? (
          <View className="px-5 pt-5 gap-4">
            <Tabs
              tabs={['Menu', 'Book']}
              activeIndex={serviceSubTab === 'menu' ? 0 : 1}
              onChange={(i) => setServiceSubTab(i === 0 ? 'menu' : 'book')}
              underlineInset={25}
            />

            {serviceSubTab === 'menu' ? (
              <>
                {categories.length > 1 ? (
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }} className="py-3">
                    {categories.map((category) => (
                      <Pill
                        key={category}
                        label={category === 'all' ? 'All' : category}
                        selected={activeCategory === category}
                        onPress={() => setActiveCategory(category)}
                        size="sm"
                      />
                    ))}
                  </ScrollView>
                ) : null}

                {filteredServices.length > 0 ? (
                  <View className="gap-3">
                    {filteredServices.map((service) => (
                      <Card key={service.service_id} padding="sm">
                        <View className="flex-row items-center justify-between">
                          <View className="flex-1 pr-3">
                            <Text className="text-fixme-text-primary text-sm font-semibold">{service.name}</Text>
                            <Text className="text-fixme-text-muted text-xs mt-1">
                              {service.duration_minutes} min · {fmtSek(service.price_ex_vat)}
                            </Text>
                          </View>
                          <Button size="sm" onPress={() => openBookingForService(service)}>
                            Book
                          </Button>
                        </View>
                      </Card>
                    ))}
                  </View>
                ) : (
                  <EmptyState
                    icon="✂️"
                    title="No services yet"
                    body="Add your first service and start taking bookings."
                    action="Add service"
                    onAction={() => router.push('/settings/services' as any)}
                    compact
                  />
                )}
              </>
            ) : (
              <View className="gap-3">
                {selectedService ? (
                  <>
                    <Card padding="sm">
                      <Text className="text-fixme-text-muted text-[10px] font-semibold uppercase tracking-wider mb-1">
                        Selected service
                      </Text>
                      <Text className="text-fixme-text-primary font-semibold text-base">{selectedService.name}</Text>
                      <Text className="text-fixme-text-muted text-sm mt-1">
                        {selectedService.duration_minutes} min · {fmtSek(selectedService.price_ex_vat)}
                      </Text>
                    </Card>

                    <Button size="lg" onPress={() => openBookingFlow(selectedService)} fullWidth>
                      Book now
                    </Button>

                    <Button variant="ghost" size="sm" onPress={handleShareBookingLink} disabled={!bookingUrl} fullWidth>
                      Share booking link
                    </Button>
                  </>
                ) : (
                  <EmptyState
                    icon="📅"
                    title="Choose a service first"
                    body="Go to Menu and tap Book on any service."
                    action="Browse Menu"
                    onAction={() => setServiceSubTab('menu')}
                    compact
                  />
                )}
              </View>
            )}
          </View>
        ) : null}

        {tab === 'reviews' ? (
          <View className="px-5 pt-5">
            <Card>
              <Text className="text-fixme-text-primary font-semibold text-base mb-1">
                ⭐ {(profile.trust?.rating || 5.0).toFixed(1)} from {profile.trust?.review_count || 0} reviews
              </Text>
              <Text className="text-fixme-text-muted text-sm leading-relaxed">
                Customer reviews and highlights will appear here.
              </Text>
            </Card>
          </View>
        ) : null}
      </ScrollView>

      {/* ── In-app booking flow modal ── */}
      {bookingFlowService && providerId && (
        <BookingFlow
          visible={bookingFlowVisible}
          onClose={() => setBookingFlowVisible(false)}
          providerId={providerId}
          service={bookingFlowService}
        />
      )}
    </SafeAreaView>
  );
}

