import { useState, useRef } from 'react';
import {
  View, Text, Pressable, ScrollView, TextInput,
  ActivityIndicator, Alert, Switch, Modal,
  KeyboardAvoidingView, Platform, Animated,
} from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as ImagePicker from 'expo-image-picker';
import {
  getProviderServices, createService, updateService, deleteService,
  scanPriceListPhoto,
  type Service,
  type ScannedServiceFromPhoto,
} from '@/lib/api';
import { colors } from '@/theme';

const DURATIONS = [30, 45, 60, 75, 90, 120];

function fmtDuration(min: number) {
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

import { formatPrice as fmtCurrency } from '@/utils/currency';
function fmtPrice(price: number, currency = 'SEK') {
  return fmtCurrency(price, currency);
}

// ─── Service form modal ────────────────────────────────────────────────────────

function ServiceFormModal({
  visible, initial, onSave, onClose, saving,
}: {
  visible: boolean;
  initial: Partial<Service>;
  onSave: (data: Omit<Service, 'service_id'>) => void;
  onClose: () => void;
  saving: boolean;
}) {
  const [name,      setName]      = useState(initial.name ?? '');
  const [price,     setPrice]     = useState(String(initial.price_ex_vat ?? ''));
  const [duration,  setDuration]  = useState(initial.duration_minutes ?? 60);
  const [homeAvail, setHomeAvail] = useState(initial.home_service_available ?? false);
  const [isActive,  setIsActive]  = useState(initial.is_active ?? true);
  const [category,  setCategory]  = useState(initial.category ?? '');

  const [lastVisible, setLastVisible] = useState(false);
  if (visible !== lastVisible) {
    setLastVisible(visible);
    if (visible) {
      setName(initial.name ?? '');
      setPrice(String(initial.price_ex_vat ?? ''));
      setDuration(initial.duration_minutes ?? 60);
      setHomeAvail(initial.home_service_available ?? false);
      setIsActive(initial.is_active ?? true);
      setCategory(initial.category ?? '');
    }
  }

  function handleSave() {
    if (!name.trim()) { Alert.alert('Required', 'Service name is required.'); return; }
    const priceNum = parseFloat(price);
    if (isNaN(priceNum) || priceNum < 0) { Alert.alert('Invalid', 'Enter a valid price.'); return; }
    onSave({
      name: name.trim(),
      category: category.trim() || undefined,
      price_ex_vat: priceNum,
      duration_minutes: duration,
      home_service_available: homeAvail,
      is_active: isActive,
    });
  }

  const isEdit = !!initial.service_id;

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView
        style={{ flex: 1, backgroundColor: '#0D0D0D' }}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <SafeAreaView style={{ flex: 1 }} edges={['top']}>

          {/* Header */}
          <View style={{
            flexDirection: 'row', alignItems: 'center',
            paddingHorizontal: 24, paddingTop: 20, paddingBottom: 20,
          }}>
            <Pressable onPress={onClose} hitSlop={12}>
              <Text style={{ color: '#666', fontSize: 15 }}>Cancel</Text>
            </Pressable>
            <Text style={{
              flex: 1, textAlign: 'center',
              color: '#F5F5F0', fontWeight: '700', fontSize: 17,
            }}>
              {isEdit ? 'Edit service' : 'New service'}
            </Text>
            <Pressable onPress={handleSave} disabled={saving} style={{ opacity: saving ? 0.5 : 1 }} hitSlop={12}>
              {saving
                ? <ActivityIndicator color="#F5F5F0" size="small" />
                : <Text style={{ color: '#F5F5F0', fontSize: 15, fontWeight: '700' }}>Save</Text>}
            </Pressable>
          </View>

          <ScrollView
            style={{ flex: 1 }}
            contentContainerStyle={{ paddingHorizontal: 24, paddingBottom: 48 }}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {/* Name */}
            <View style={sectionBlock}>
              <Text style={fieldLabel}>Service name</Text>
              <TextInput
                style={fieldInput}
                placeholder="e.g. Full head highlights"
                placeholderTextColor="#444"
                value={name}
                onChangeText={setName}
                autoFocus
                returnKeyType="next"
              />
            </View>

            {/* Category */}
            <View style={sectionBlock}>
              <Text style={fieldLabel}>Category</Text>
              <TextInput
                style={fieldInput}
                placeholder="e.g. Hair, Nails, Skin"
                placeholderTextColor="#444"
                value={category}
                onChangeText={setCategory}
                returnKeyType="next"
              />
            </View>

            {/* Price */}
            <View style={sectionBlock}>
              <Text style={fieldLabel}>Price ex. VAT</Text>
              <View>
                <TextInput
                  style={[fieldInput, { paddingRight: 50 }]}
                  placeholder="850"
                  placeholderTextColor="#444"
                  value={price}
                  onChangeText={setPrice}
                  keyboardType="decimal-pad"
                />
                <Text style={{
                  position: 'absolute', right: 16, top: 0, bottom: 0,
                  textAlignVertical: 'center', lineHeight: 52,
                  color: '#555', fontSize: 15,
                }}>kr</Text>
              </View>
            </View>

            {/* Duration */}
            <View style={sectionBlock}>
              <Text style={fieldLabel}>Duration</Text>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={{ gap: 8 }}
              >
                {DURATIONS.map(d => {
                  const active = duration === d;
                  return (
                    <Pressable
                      key={d}
                      onPress={() => setDuration(d)}
                      style={{
                        paddingHorizontal: 18, paddingVertical: 10, borderRadius: 24,
                        backgroundColor: active ? '#F5F5F0' : '#1A1A1A',
                        borderWidth: 1,
                        borderColor: active ? '#F5F5F0' : '#2A2A2A',
                      }}
                    >
                      <Text style={{
                        fontSize: 14, fontWeight: '600',
                        color: active ? '#0D0D0D' : '#666',
                      }}>
                        {fmtDuration(d)}
                      </Text>
                    </Pressable>
                  );
                })}
              </ScrollView>
            </View>

            {/* Toggles */}
            <View style={{ borderRadius: 16, overflow: 'hidden', marginTop: 8, gap: 1 }}>
              <View style={toggleRow}>
                <View style={{ flex: 1, marginRight: 12 }}>
                  <Text style={{ color: '#F5F5F0', fontSize: 15, fontWeight: '500' }}>Home visits</Text>
                  <Text style={{ color: '#555', fontSize: 12, marginTop: 2 }}>Available at client's location</Text>
                </View>
                <Switch
                  value={homeAvail}
                  onValueChange={setHomeAvail}
                  trackColor={{ false: '#2A2A2A', true: '#4ade80' }}
                  thumbColor="#F5F5F0"
                />
              </View>
              <View style={[toggleRow, { marginTop: 1 }]}>
                <View style={{ flex: 1, marginRight: 12 }}>
                  <Text style={{ color: '#F5F5F0', fontSize: 15, fontWeight: '500' }}>Active</Text>
                  <Text style={{ color: '#555', fontSize: 12, marginTop: 2 }}>Visible to clients when booking</Text>
                </View>
                <Switch
                  value={isActive}
                  onValueChange={setIsActive}
                  trackColor={{ false: '#2A2A2A', true: '#4ade80' }}
                  thumbColor="#F5F5F0"
                />
              </View>
            </View>

          </ScrollView>
        </SafeAreaView>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const sectionBlock: object = { marginBottom: 24 };

const fieldLabel: object = {
  color: '#555', fontSize: 12, fontWeight: '600',
  textTransform: 'uppercase', letterSpacing: 0.8,
  marginBottom: 10,
};
const fieldInput: object = {
  backgroundColor: '#1A1A1A',
  borderRadius: 14, paddingHorizontal: 16,
  color: '#F5F5F0', fontSize: 16,
  height: 52,
};
const toggleRow: object = {
  flexDirection: 'row', alignItems: 'center',
  backgroundColor: '#1A1A1A',
  paddingHorizontal: 18, paddingVertical: 16,
};

// ─── Service card ─────────────────────────────────────────────────────────────

function ServiceCard({
  service, onEdit, onDelete,
}: {
  service: Service;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const slideAnim = useRef(new Animated.Value(0)).current;
  const [revealed, setRevealed] = useState(false);

  function closeReveal() {
    Animated.spring(slideAnim, { toValue: 0, useNativeDriver: true, tension: 120, friction: 14 }).start();
    setRevealed(false);
  }

  function handlePress() {
    if (revealed) { closeReveal(); } else { onEdit(); }
  }

  function handleLongPress() {
    if (!revealed) {
      Animated.spring(slideAnim, { toValue: -76, useNativeDriver: true, tension: 120, friction: 14 }).start();
      setRevealed(true);
    }
  }

  function handleDelete() {
    Animated.spring(slideAnim, { toValue: 0, useNativeDriver: true }).start(() => {
      setRevealed(false);
      onDelete();
    });
  }

  return (
    <View style={{ marginBottom: 10, borderRadius: 18, overflow: 'hidden' }}>
      {/* Delete action revealed on long-press */}
      <View style={{
        position: 'absolute', right: 0, top: 0, bottom: 0,
        width: 76, alignItems: 'center', justifyContent: 'center',
        backgroundColor: 'rgba(239,68,68,0.15)',
      }}>
        <Pressable onPress={handleDelete} style={{ alignItems: 'center', padding: 8 }}>
          <Text style={{ fontSize: 20 }}>🗑</Text>
          <Text style={{ color: '#f87171', fontSize: 11, fontWeight: '600', marginTop: 2 }}>Delete</Text>
        </Pressable>
      </View>

      {/* Main card */}
      <Animated.View style={{ transform: [{ translateX: slideAnim }] }}>
        <Pressable
          onPress={handlePress}
          onLongPress={handleLongPress}
          delayLongPress={400}
          style={{
            backgroundColor: '#1A1A1A',
            borderRadius: 18,
            paddingHorizontal: 20, paddingVertical: 18,
            flexDirection: 'row', alignItems: 'center',
          }}
        >
          <View style={{ flex: 1, marginRight: 12 }}>
            <Text style={{ color: '#F5F5F0', fontWeight: '600', fontSize: 16, marginBottom: 6 }}>
              {service.name}
            </Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 4 }}>
              <Text style={{ color: '#666', fontSize: 13 }}>
                {fmtDuration(service.duration_minutes)}
              </Text>
              <Text style={{ color: '#333', fontSize: 13 }}> · </Text>
              <Text style={{ color: '#666', fontSize: 13 }}>
                {fmtPrice(service.price_ex_vat)}
              </Text>
              {service.category ? (
                <>
                  <Text style={{ color: '#333', fontSize: 13 }}> · </Text>
                  <Text style={{ color: '#555', fontSize: 13 }}>{service.category}</Text>
                </>
              ) : null}
              {service.home_service_available && (
                <Text style={{ fontSize: 13 }}> 🏠</Text>
              )}
            </View>
          </View>

          <View style={{ alignItems: 'flex-end', gap: 8 }}>
            <View style={{
              paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20,
              backgroundColor: service.is_active ? 'rgba(74,222,128,0.1)' : 'rgba(255,255,255,0.05)',
            }}>
              <Text style={{
                fontSize: 11, fontWeight: '600',
                color: service.is_active ? '#4ade80' : '#555',
              }}>
                {service.is_active ? 'Active' : 'Hidden'}
              </Text>
            </View>
            <Text style={{ color: '#333', fontSize: 18 }}>›</Text>
          </View>
        </Pressable>
      </Animated.View>
    </View>
  );
}

// ─── Category group ────────────────────────────────────────────────────────────

function CategoryHeader({ label, count }: { label: string; count: number }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 28, marginBottom: 12 }}>
      <Text style={{ color: '#F5F5F0', fontWeight: '700', fontSize: 12, letterSpacing: 1, flex: 1 }}>
        {label.toUpperCase()}
      </Text>
      <Text style={{ color: '#444', fontSize: 12 }}>{count}</Text>
    </View>
  );
}

// ─── Scan review modal ────────────────────────────────────────────────────────

type ReviewRow = ScannedServiceFromPhoto & { id: string };

function ScanReviewModal({
  visible, services, onSave, onClose,
}: {
  visible: boolean;
  services: ScannedServiceFromPhoto[];
  onSave: (selected: ScannedServiceFromPhoto[]) => void;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Sync rows when modal opens
  const [lastVisible, setLastVisible] = useState(false);
  if (visible !== lastVisible) {
    setLastVisible(visible);
    if (visible) {
      setRows(services.map((s, i) => ({ ...s, id: String(i) })));
      setExpanded(null);
    }
  }

  function updateRow(id: string, patch: Partial<ReviewRow>) {
    setRows(prev => prev.map(r => r.id === id ? { ...r, ...patch } : r));
  }

  function removeRow(id: string) {
    setRows(prev => prev.filter(r => r.id !== id));
  }

  async function handleSave() {
    setSaving(true);
    await onSave(rows.map(({ id, ...s }) => s));
    setSaving(false);
  }

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>

        {/* Header */}
        <View className="flex-row items-center px-5 pt-5 pb-4 border-b border-fixme-border">
          <Pressable onPress={onClose} hitSlop={12}>
            <Text className="text-fixme-text-muted text-[15px]">Cancel</Text>
          </Pressable>
          <View className="flex-1 items-center">
            <Text className="text-fixme-text-primary font-bold text-[17px]">Review services</Text>
            <Text className="text-fixme-text-muted text-xs mt-0.5">{rows.length} found · tap to edit</Text>
          </View>
          <Pressable
            onPress={handleSave}
            disabled={saving || rows.length === 0}
            style={{ opacity: saving || rows.length === 0 ? 0.4 : 1 }}
            hitSlop={12}
          >
            {saving
              ? <ActivityIndicator size="small" color={colors.accent} />
              : <Text className="text-fixme-accent font-bold text-[15px]">Save all</Text>}
          </Pressable>
        </View>

        <ScrollView className="flex-1" contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 8, paddingBottom: 48 }} showsVerticalScrollIndicator={false}>
          {rows.map(row => {
            const isOpen = expanded === row.id;
            return (
              <View key={row.id} className="border-b border-fixme-border">
                <Pressable
                  onPress={() => setExpanded(isOpen ? null : row.id)}
                  className="flex-row items-center py-4"
                >
                  <View className="flex-1">
                    <Text className="text-fixme-text-primary font-medium text-[15px]">
                      {row.name || 'Unnamed service'}
                    </Text>
                    <Text className="text-fixme-text-muted text-xs mt-0.5">
                      {[row.price_ex_vat ? `${row.price_ex_vat} kr` : null, row.duration_minutes ? `${row.duration_minutes} min` : null].filter(Boolean).join('  ·  ') || 'No details'}
                    </Text>
                  </View>
                  <Text className="text-fixme-text-muted text-xs mr-3">{isOpen ? 'Done' : 'Edit'}</Text>
                  <Pressable onPress={() => removeRow(row.id)} hitSlop={12}>
                    <Text className="text-fixme-error text-lg leading-[20px]">×</Text>
                  </Pressable>
                </Pressable>

                {isOpen && (
                  <View className="pb-4 gap-2">
                    <TextInput
                      className="bg-fixme-card border border-fixme-border rounded-xl px-3 py-2.5 text-fixme-text-primary text-[14px]"
                      value={row.name}
                      onChangeText={v => updateRow(row.id, { name: v })}
                      placeholder="Service name"
                      placeholderTextColor={colors.textMuted}
                    />
                    <TextInput
                      className="bg-fixme-card border border-fixme-border rounded-xl px-3 py-2.5 text-fixme-text-primary text-[14px]"
                      value={row.category ?? ''}
                      onChangeText={v => updateRow(row.id, { category: v })}
                      placeholder="Category (e.g. Hair, Nails)"
                      placeholderTextColor={colors.textMuted}
                    />
                    <View className="flex-row gap-2">
                      <TextInput
                        className="flex-1 bg-fixme-card border border-fixme-border rounded-xl px-3 py-2.5 text-fixme-text-primary text-[14px]"
                        value={String(row.price_ex_vat ?? '')}
                        onChangeText={v => updateRow(row.id, { price_ex_vat: parseFloat(v) || 0 })}
                        placeholder="Price (kr)"
                        placeholderTextColor={colors.textMuted}
                        keyboardType="numeric"
                      />
                      <TextInput
                        className="flex-1 bg-fixme-card border border-fixme-border rounded-xl px-3 py-2.5 text-fixme-text-primary text-[14px]"
                        value={String(row.duration_minutes ?? '')}
                        onChangeText={v => updateRow(row.id, { duration_minutes: parseInt(v) || 0 })}
                        placeholder="Duration (min)"
                        placeholderTextColor={colors.textMuted}
                        keyboardType="numeric"
                      />
                    </View>
                  </View>
                )}
              </View>
            );
          })}

          {rows.length === 0 && (
            <View className="flex-1 items-center justify-center pt-20">
              <Text className="text-fixme-text-muted text-sm text-center">All services removed.</Text>
            </View>
          )}
        </ScrollView>

      </SafeAreaView>
    </Modal>
  );
}

// ─── Main screen ─────────────────────────────────────────────────────────────

export default function ServicesSettingsScreen() {
  const queryClient = useQueryClient();
  const [modalVisible, setModalVisible] = useState(false);
  const [editing, setEditing] = useState<Partial<Service>>({});

  const { data: services = [], isLoading } = useQuery({
    queryKey: ['provider-services'],
    queryFn: getProviderServices,
  });

  const createMut = useMutation({
    mutationFn: (data: Omit<Service, 'service_id'>) => createService(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['provider-services'] });
      queryClient.invalidateQueries({ queryKey: ['provider-profile-public'] });
      setModalVisible(false);
    },
    onError: (err: Error) => Alert.alert('Error', err.message),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Service> }) => updateService(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['provider-services'] });
      queryClient.invalidateQueries({ queryKey: ['provider-profile-public'] });
      setModalVisible(false);
    },
    onError: (err: Error) => Alert.alert('Error', err.message),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteService(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['provider-services'] });
      queryClient.invalidateQueries({ queryKey: ['provider-profile-public'] });
    },
    onError: (err: Error) => Alert.alert('Error', err.message),
  });

  const [scanning, setScanning] = useState(false);
  const [scannedServices, setScannedServices] = useState<ScannedServiceFromPhoto[]>([]);
  const [scanReviewVisible, setScanReviewVisible] = useState(false);

  function openAdd() {
    Alert.alert(
      'Add services',
      'How would you like to add?',
      [
        { text: '📸 Upload screenshot', onPress: handleUploadScreenshot },
        { text: '✏️ Add manually', onPress: () => { setEditing({}); setModalVisible(true); } },
        { text: 'Cancel', style: 'cancel' },
      ],
    );
  }

  async function handleUploadScreenshot() {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('Permission needed', 'Please allow access to your photo library.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.85 });
    if (result.canceled || !result.assets?.[0]) return;
    const asset = result.assets[0];
    setScanning(true);
    try {
      const { services: extracted, services_found, note } = await scanPriceListPhoto(
        asset.uri, asset.mimeType ?? 'image/jpeg',
      );
      if (services_found === 0) {
        Alert.alert('No services found', note || 'Try a clearer photo of your price list.');
        return;
      }
      setScannedServices(extracted);
      setScanReviewVisible(true);
    } catch (err: any) {
      Alert.alert('Scan failed', err.message || 'Could not read the image. Please try again.');
    } finally {
      setScanning(false);
    }
  }

  async function handleSaveScanned(selected: ScannedServiceFromPhoto[]) {
    setScanReviewVisible(false);
    for (const s of selected) {
      await createService({
        name: s.name,
        category: s.category ?? undefined,
        price_ex_vat: s.price_ex_vat ?? 0,
        duration_minutes: s.duration_minutes ?? 60,
        home_service_available: false,
        is_active: true,
      }).catch(() => null);
    }
    queryClient.invalidateQueries({ queryKey: ['provider-services'] });
    queryClient.invalidateQueries({ queryKey: ['provider-profile-public'] });
  }

  function openEdit(service: Service) { setEditing(service); setModalVisible(true); }

  function confirmDelete(service: Service) {
    Alert.alert(
      'Delete service',
      `Remove "${service.name}" from your menu?`,
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: () => deleteMut.mutate(service.service_id) },
      ],
    );
  }

  function handleSave(data: Omit<Service, 'service_id'>) {
    if (editing.service_id) {
      updateMut.mutate({ id: editing.service_id, data });
    } else {
      createMut.mutate(data);
    }
  }

  // Group services by category
  const grouped = services.reduce<Record<string, Service[]>>((acc, s) => {
    const key = s.category?.trim() || 'Other';
    (acc[key] ??= []).push(s);
    return acc;
  }, {});
  const categories = Object.keys(grouped).sort((a, b) =>
    a === 'Other' ? 1 : b === 'Other' ? -1 : a.localeCompare(b),
  );
  const showCategories = categories.length > 1 || (categories.length === 1 && categories[0] !== 'Other');

  const isSaving = createMut.isPending || updateMut.isPending;

  return (
    <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>

      {/* Header */}
      <View className="flex-row items-center gap-4 px-5 pt-6 pb-2">
        <Pressable onPress={() => router.back()} hitSlop={16} style={({ pressed }) => ({ opacity: pressed ? 0.4 : 1 })}>
          <Text style={{ fontSize: 26, lineHeight: 26, color: '#888' }}>‹</Text>
        </Pressable>
        <Text className="flex-1 text-fixme-text-primary font-bold text-2xl">Services</Text>
        <Pressable
          onPress={openAdd}
          disabled={scanning}
          className="bg-fixme-accent rounded-full px-[18px] py-[9px]"
          style={{ opacity: scanning ? 0.6 : 1 }}
        >
          {scanning
            ? <ActivityIndicator size="small" color={colors.bg} />
            : <Text className="text-fixme-bg font-bold text-sm">+ Add</Text>}
        </Pressable>
      </View>

      {/* Subtitle */}
      {!isLoading && services.length > 0 && (
        <Text className="text-fixme-text-muted text-[13px] px-6 mb-1">
          {services.length} service{services.length !== 1 ? 's' : ''} · Hold a card to delete
        </Text>
      )}

      {isLoading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.accent} />
        </View>
      ) : services.length === 0 ? (
        /* Empty state */
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 40 }}>
          <Text style={{ fontSize: 44, marginBottom: 18 }}>✂️</Text>
          <Text style={{ color: '#F5F5F0', fontSize: 19, fontWeight: '700', marginBottom: 8, textAlign: 'center' }}>
            Your menu is empty
          </Text>
          <Text style={{ color: '#555', fontSize: 14, textAlign: 'center', lineHeight: 21 }}>
            Add your first service and start taking bookings
          </Text>
          <Pressable
            onPress={openAdd}
            style={{
              marginTop: 28,
              backgroundColor: '#F5F5F0', borderRadius: 24,
              paddingHorizontal: 28, paddingVertical: 14,
            }}
          >
            <Text style={{ color: '#0D0D0D', fontWeight: '700', fontSize: 15 }}>Add your first service</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ paddingHorizontal: 20, paddingTop: 16, paddingBottom: 48 }}
          showsVerticalScrollIndicator={false}
        >
          {showCategories ? (
            categories.map(cat => (
              <View key={cat}>
                <CategoryHeader label={cat} count={grouped[cat].length} />
                {grouped[cat].map(service => (
                  <ServiceCard
                    key={service.service_id}
                    service={service}
                    onEdit={() => openEdit(service)}
                    onDelete={() => confirmDelete(service)}
                  />
                ))}
              </View>
            ))
          ) : (
            services.map(service => (
              <ServiceCard
                key={service.service_id}
                service={service}
                onEdit={() => openEdit(service)}
                onDelete={() => confirmDelete(service)}
              />
            ))
          )}
        </ScrollView>
      )}

      <ServiceFormModal
        visible={modalVisible}
        initial={editing}
        saving={isSaving}
        onClose={() => setModalVisible(false)}
        onSave={handleSave}
      />

      <ScanReviewModal
        visible={scanReviewVisible}
        services={scannedServices}
        onClose={() => setScanReviewVisible(false)}
        onSave={handleSaveScanned}
      />
    </SafeAreaView>
  );
}
