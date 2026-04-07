import { useState, useEffect } from 'react';
import {
  View, Text, Pressable, ScrollView,
  ActivityIndicator, Alert,
} from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProviderAmenities, updateProviderAmenities } from '@/lib/api';
import { colors } from '@/theme';

// ─── Amenity catalogue ────────────────────────────────────────────────────────

const AMENITY_GROUPS: Array<{
  group: string;
  items: Array<{ key: string; label: string; icon: string }>;
}> = [
  {
    group: 'Accessibility',
    items: [
      { key: 'wheelchair_accessible', label: 'Wheelchair accessible',  icon: '\u267F' },
      { key: 'elevator',              label: 'Elevator',               icon: '\uD83C\uDFE2' },
      { key: 'street_level',          label: 'Street level entry',      icon: '\uD83D\uDEAA' },
    ],
  },
  {
    group: 'Comfort',
    items: [
      { key: 'wifi',          label: 'Free Wi-Fi',          icon: '\uD83D\uDCF6' },
      { key: 'parking',       label: 'Free parking',        icon: '\uD83D\uDE97' },
      { key: 'kids_welcome',  label: 'Kids welcome',        icon: '\uD83D\uDC76' },
      { key: 'pets_welcome',  label: 'Pets welcome',        icon: '\uD83D\uDC36' },
      { key: 'music',         label: 'Relaxing music',      icon: '\uD83C\uDFB5' },
    ],
  },
  {
    group: 'Refreshments',
    items: [
      { key: 'coffee',        label: 'Coffee & tea',        icon: '\u2615' },
      { key: 'beverages',     label: 'Beverages',           icon: '\uD83E\uDD64' },
      { key: 'snacks',        label: 'Snacks',              icon: '\uD83C\uDF6A' },
    ],
  },
  {
    group: 'Services',
    items: [
      { key: 'home_service',  label: 'Home visits',         icon: '\uD83C\uDFE0' },
      { key: 'contactless',   label: 'Contactless payment', icon: '\uD83D\uDCF2' },
      { key: 'card_payment',  label: 'Card payment',        icon: '\uD83D\uDCB3' },
      { key: 'vegan_products',label: 'Vegan products',      icon: '\uD83C\uDF31' },
      { key: 'private_room',  label: 'Private room',        icon: '\uD83D\uDD10' },
    ],
  },
  {
    group: 'Atmosphere',
    items: [
      { key: 'instagram_worthy', label: 'Instagram-worthy space', icon: '\uD83D\uDCF8' },
      { key: 'scented',          label: 'Scented / aromatherapy', icon: '\uD83D\uDC90' },
      { key: 'natural_light',    label: 'Natural light',          icon: '\u2600\uFE0F' },
    ],
  },
];

// ─── Pill chip ────────────────────────────────────────────────────────────────

function AmenityChip({
  icon, label, selected, onPress,
}: { icon: string; label: string; selected: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      className={`flex-row items-center gap-2 px-4 py-2.5 rounded-xl border mr-2 mb-2 ${selected ? 'bg-fixme-accent border-fixme-accent' : 'bg-fixme-card border-fixme-border'}`}
    >
      <Text className="text-base">{icon}</Text>
      <Text className={`text-sm font-semibold ${selected ? 'text-fixme-bg' : 'text-fixme-text-secondary'}`}>
        {label}
      </Text>
      {selected && (
        <Text className="text-fixme-bg text-xs font-bold">\u2713</Text>
      )}
    </Pressable>
  );
}

// ─── Main screen ─────────────────────────────────────────────────────────────

export default function AmenitiesSettingsScreen() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [dirty,    setDirty]    = useState(false);

  const { data: savedAmenities = [], isLoading } = useQuery({
    queryKey: ['provider-amenities'],
    queryFn: getProviderAmenities,
  });

  useEffect(() => {
    if (savedAmenities.length > 0 || !isLoading) {
      setSelected(new Set(savedAmenities));
      setDirty(false);
    }
  }, [savedAmenities, isLoading]);

  function toggle(key: string) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
    setDirty(true);
  }

  const mutation = useMutation({
    mutationFn: () => updateProviderAmenities(Array.from(selected)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['provider-amenities'] });
      setDirty(false);
      Alert.alert('Saved', 'Amenities updated on your profile.');
    },
    onError: (err: Error) => Alert.alert('Error', err.message),
  });

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
        <View className="flex-row items-center gap-3 pt-6 mb-2">
          <Pressable onPress={() => router.back()}>
            <Text className="text-fixme-text-muted text-sm">\u2190</Text>
          </Pressable>
          <Text className="text-fixme-text-primary font-bold text-xl flex-1">Amenities</Text>
          {dirty && (
            <View className="w-2 h-2 rounded-full bg-fixme-accent" />
          )}
        </View>

        <Text className="text-fixme-text-muted text-sm mb-6">
          Show clients what makes your space special. Selected amenities appear on your public profile.
        </Text>

        {/* Count badge */}
        {selected.size > 0 && (
          <View className="flex-row items-center gap-2 mb-4">
            <View className="bg-fixme-accent/20 border border-fixme-accent/30 rounded-full px-3 py-1">
              <Text className="text-fixme-accent text-xs font-semibold">
                {selected.size} selected
              </Text>
            </View>
            <Pressable onPress={() => { setSelected(new Set()); setDirty(true); }}>
              <Text className="text-fixme-text-muted text-xs underline">Clear all</Text>
            </Pressable>
          </View>
        )}

        {/* Groups */}
        {AMENITY_GROUPS.map(group => (
          <View key={group.group} className="mb-6">
            <Text className="text-fixme-text-secondary text-xs font-semibold mb-3 uppercase tracking-wider">
              {group.group}
            </Text>
            <View className="flex-row flex-wrap">
              {group.items.map(item => (
                <AmenityChip
                  key={item.key}
                  icon={item.icon}
                  label={item.label}
                  selected={selected.has(item.key)}
                  onPress={() => toggle(item.key)}
                />
              ))}
            </View>
          </View>
        ))}

        {/* Save */}
        <Pressable
          onPress={() => mutation.mutate()}
          disabled={mutation.isPending || !dirty}
          className="bg-fixme-accent rounded-2xl py-4 items-center mb-10 active:opacity-80 disabled:opacity-40"
        >
          {mutation.isPending
            ? <ActivityIndicator color="#0D0D0D" />
            : <Text className="text-fixme-bg font-bold text-base">Save changes</Text>
          }
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}
