import { useState, useEffect } from 'react';
import {
  View, Text, TextInput, Pressable, ScrollView,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert,
} from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getMyProviderProfile, updateProviderProfile } from '@/lib/api';
import { colors } from '@/theme';

export default function ProfileSettingsScreen() {
  const queryClient = useQueryClient();
  const { data: profile, isLoading } = useQuery({
    queryKey: ['provider-profile'],
    queryFn:  () => getMyProviderProfile(),
  });

  const [name,      setName]      = useState('');
  const [bio,       setBio]       = useState('');
  const [phone,     setPhone]     = useState('');
  const [instagram, setInstagram] = useState('');
  const [address,   setAddress]   = useState('');
  const [city,      setCity]      = useState('');

  useEffect(() => {
    if (!profile) return;
    setName(profile.name ?? '');
    setBio(profile.bio ?? '');
    setPhone(profile.phone ?? '');
    setInstagram(profile.instagram_username ?? '');
    setAddress(profile.location_salon ?? '');
    setCity(profile.city ?? '');
  }, [profile]);

  const mutation = useMutation({
    mutationFn: () => updateProviderProfile({ name, bio, phone, instagram_username: instagram, location_salon: address, city }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['provider-profile'] });
      Alert.alert('Saved', 'Profile updated successfully.');
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
      <KeyboardAvoidingView className="flex-1" behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView className="flex-1 px-5" keyboardShouldPersistTaps="handled">
          <View className="flex-row items-center gap-3 pt-6 mb-6">
            <Pressable onPress={() => router.back()}>
              <Text className="text-fixme-text-muted text-sm">\u2190</Text>
            </Pressable>
            <Text className="text-fixme-text-primary font-bold text-xl">Profile</Text>
          </View>

          <Field label="Business name"    value={name}      onChange={setName}      placeholder="Your studio name" />
          <Field label="Bio"              value={bio}       onChange={setBio}       placeholder="Tell clients about your work..." multiline />
          <Field label="Phone"            value={phone}     onChange={setPhone}     placeholder="+46 70 000 00 00" keyboardType="phone-pad" />
          <Field label="Instagram handle" value={instagram} onChange={setInstagram} placeholder="@yourstudio" autoCapitalize="none" />
          <Field label="Address"          value={address}   onChange={setAddress}   placeholder="Street address" />
          <Field label="City"             value={city}      onChange={setCity}      placeholder="Stockholm" />

          <Pressable
            onPress={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="bg-fixme-accent rounded-2xl py-4 items-center mt-6 mb-10 active:opacity-80 disabled:opacity-50"
          >
            {mutation.isPending
              ? <ActivityIndicator color="#0D0D0D" />
              : <Text className="text-fixme-bg font-bold text-base">Save changes</Text>
            }
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Field({ label, value, onChange, placeholder, keyboardType = 'default', autoCapitalize = 'sentences', multiline = false }: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder: string; keyboardType?: any; autoCapitalize?: any; multiline?: boolean;
}) {
  return (
    <View className="mb-4">
      <Text className="text-fixme-text-secondary text-xs font-semibold mb-2 uppercase tracking-wider">{label}</Text>
      <TextInput
        className={`bg-fixme-card border border-fixme-border rounded-xl px-4 py-4 text-fixme-text-primary text-base ${multiline ? 'min-h-[100px]' : ''}`}
        style={multiline ? { textAlignVertical: 'top' } : undefined}
        placeholder={placeholder}
        placeholderTextColor="#666"
        value={value}
        onChangeText={onChange}
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize}
        multiline={multiline}
        numberOfLines={multiline ? 4 : 1}
      />
    </View>
  );
}
