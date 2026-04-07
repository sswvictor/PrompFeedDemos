/**
 * BookingFlow — full in-app booking modal.
 *
 * Steps:
 *   1 → Date      pick a day from the next 14 days
 *   2 → Time      available slots for that day + service duration
 *   3 → Contact   guest name, email, phone
 *   4 → Confirm   summary + "Book now"
 *   5 → Done      confirmation screen
 */

import { useState, useCallback, useEffect } from 'react';
import {
  View, Text, ScrollView, Pressable, Modal,
  TextInput, ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '@/theme';
import { formatPrice } from '@/utils/currency';
import {
  getAvailableSlots, createGuestBooking,
  type TimeSlot, type ProviderPublicService,
} from '@/lib/api';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatSlotTime(iso: string) {
  return iso.includes('T') ? iso.split('T')[1].substring(0, 5) : iso.substring(0, 5);
}

function formatDateLabel(date: Date) {
  return date.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
}

function formatDateFull(date: Date) {
  return date.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
}

function toISODate(date: Date) {
  return date.toISOString().split('T')[0];
}

function buildDays(count = 21): Date[] {
  const days: Date[] = [];
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  for (let i = 0; i < count; i++) {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    days.push(d);
  }
  return days;
}

// ─── ProgressDots ────────────────────────────────────────────────────────────

function ProgressDots({ step, total }: { step: number; total: number }) {
  return (
    <View className="flex-row items-center justify-center gap-1.5 py-3">
      {Array.from({ length: total }).map((_, i) => (
        <View
          key={i}
          className={i < step
            ? 'w-6 h-1.5 rounded-full bg-fixme-accent'
            : 'w-1.5 h-1.5 rounded-full bg-fixme-border'
          }
        />
      ))}
    </View>
  );
}

// ─── Step 1 — Date ───────────────────────────────────────────────────────────

function StepDate({ onSelect }: { onSelect: (d: Date) => void }) {
  const days = buildDays(21);
  return (
    <View className="flex-1">
      <Text className="text-fixme-text-primary font-bold text-[26px] tracking-tight mb-1">
        Pick a date
      </Text>
      <Text className="text-fixme-text-muted text-sm mb-6">
        Choose a day for your appointment
      </Text>

      <ScrollView showsVerticalScrollIndicator={false}>
        <View className="gap-2">
          {days.map((day, i) => {
            const isToday = i === 0;
            return (
              <Pressable
                key={day.toISOString()}
                onPress={() => onSelect(day)}
                style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}
                className="flex-row items-center bg-fixme-card border border-fixme-border rounded-2xl px-5 py-4"
              >
                <View className="flex-1">
                  <Text className="text-fixme-text-primary font-semibold text-base">
                    {formatDateLabel(day)}
                    {isToday ? '  —  Today' : ''}
                  </Text>
                </View>
                <Text className="text-fixme-text-muted text-lg">›</Text>
              </Pressable>
            );
          })}
        </View>
      </ScrollView>
    </View>
  );
}

// ─── Step 2 — Time ───────────────────────────────────────────────────────────

function StepTime({
  providerId, date, service, onSelect,
}: {
  providerId: string;
  date: Date;
  service: ProviderPublicService;
  onSelect: (slot: TimeSlot) => void;
}) {
  const [slots, setSlots] = useState<TimeSlot[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [loaded, setLoaded] = useState(false);
  if (!loaded) {
    setLoaded(true);
    getAvailableSlots(providerId, toISODate(date), service.duration_minutes)
      .then(r => setSlots(Array.isArray(r) ? r : []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }

  return (
    <View className="flex-1">
      <Text className="text-fixme-text-primary font-bold text-[26px] tracking-tight mb-1">
        Pick a time
      </Text>
      <Text className="text-fixme-text-muted text-sm mb-6">
        {formatDateFull(date)}
      </Text>

      {loading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator color={colors.accent} />
          <Text className="text-fixme-text-muted text-sm mt-3">Checking availability…</Text>
        </View>
      ) : error ? (
        <View className="flex-1 items-center justify-center px-6">
          <Text className="text-fixme-text-muted text-sm text-center">{error}</Text>
        </View>
      ) : !slots || slots.length === 0 ? (
        <View className="flex-1 items-center justify-center px-6">
          <Text className="text-[44px] mb-4">😔</Text>
          <Text className="text-fixme-text-primary font-semibold text-lg text-center mb-2">
            No slots available
          </Text>
          <Text className="text-fixme-text-muted text-sm text-center">
            Try a different date
          </Text>
        </View>
      ) : (
        <ScrollView showsVerticalScrollIndicator={false}>
          <View className="flex-row flex-wrap gap-2">
            {slots.map((slot, i) => (
              <Pressable
                key={i}
                onPress={() => onSelect(slot)}
                style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}
                className="bg-fixme-card border border-fixme-border rounded-xl px-5 py-3"
              >
                <Text className="text-fixme-text-primary font-semibold text-base">
                  {formatSlotTime(slot.start)}
                </Text>
              </Pressable>
            ))}
          </View>
        </ScrollView>
      )}
    </View>
  );
}

// ─── Step 3 — Contact ────────────────────────────────────────────────────────

function StepContact({
  name, email, phone, notes,
  onChangeName, onChangeEmail, onChangePhone, onChangeNotes,
}: {
  name: string; email: string; phone: string; notes: string;
  onChangeName: (v: string) => void;
  onChangeEmail: (v: string) => void;
  onChangePhone: (v: string) => void;
  onChangeNotes: (v: string) => void;
}) {
  return (
    <KeyboardAvoidingView
      className="flex-1"
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
        <Text className="text-fixme-text-primary font-bold text-[26px] tracking-tight mb-1">
          Your details
        </Text>
        <Text className="text-fixme-text-muted text-sm mb-6">
          We'll send your confirmation here
        </Text>

        <View className="gap-4">
          <View>
            <Text className="text-fixme-text-muted text-xs font-semibold uppercase tracking-wider mb-2">
              Full name
            </Text>
            <TextInput
              className="bg-fixme-card border border-fixme-border rounded-xl px-4 h-[52px] text-fixme-text-primary text-base"
              placeholder="Your name"
              placeholderTextColor={colors.textMuted}
              value={name}
              onChangeText={onChangeName}
              autoCapitalize="words"
              returnKeyType="next"
            />
          </View>

          <View>
            <Text className="text-fixme-text-muted text-xs font-semibold uppercase tracking-wider mb-2">
              Email
            </Text>
            <TextInput
              className="bg-fixme-card border border-fixme-border rounded-xl px-4 h-[52px] text-fixme-text-primary text-base"
              placeholder="your@email.com"
              placeholderTextColor={colors.textMuted}
              value={email}
              onChangeText={onChangeEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              returnKeyType="next"
            />
          </View>

          <View>
            <Text className="text-fixme-text-muted text-xs font-semibold uppercase tracking-wider mb-2">
              Phone
            </Text>
            <TextInput
              className="bg-fixme-card border border-fixme-border rounded-xl px-4 h-[52px] text-fixme-text-primary text-base"
              placeholder="+46 70 000 00 00"
              placeholderTextColor={colors.textMuted}
              value={phone}
              onChangeText={onChangePhone}
              keyboardType="phone-pad"
              returnKeyType="next"
            />
          </View>

          <View>
            <Text className="text-fixme-text-muted text-xs font-semibold uppercase tracking-wider mb-2">
              Notes (optional)
            </Text>
            <TextInput
              className="bg-fixme-card border border-fixme-border rounded-xl px-4 py-3 text-fixme-text-primary text-base"
              placeholder="Anything we should know?"
              placeholderTextColor={colors.textMuted}
              value={notes}
              onChangeText={onChangeNotes}
              multiline
              numberOfLines={3}
              style={{ height: 88, textAlignVertical: 'top' }}
            />
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

// ─── Step 4 — Confirm ────────────────────────────────────────────────────────

function StepConfirm({
  service, date, slot, name, email, phone,
  loading, onBook,
}: {
  service: ProviderPublicService;
  date: Date;
  slot: TimeSlot;
  name: string; email: string; phone: string;
  loading: boolean;
  onBook: () => void;
}) {
  const price = service.price_ex_vat
    ? formatPrice(service.price_ex_vat, service.currency || 'SEK')
    : null;

  return (
    <View className="flex-1">
      <Text className="text-fixme-text-primary font-bold text-[26px] tracking-tight mb-1">
        Confirm booking
      </Text>
      <Text className="text-fixme-text-muted text-sm mb-6">
        Review your appointment details
      </Text>

      {/* Summary card */}
      <View className="bg-fixme-card border border-fixme-border rounded-2xl overflow-hidden mb-4">
        <View className="px-5 py-4 border-b border-fixme-border">
          <Text className="text-fixme-text-muted text-[11px] font-semibold uppercase tracking-wider mb-1">
            Service
          </Text>
          <Text className="text-fixme-text-primary font-semibold text-base">{service.name}</Text>
          <Text className="text-fixme-text-muted text-sm mt-0.5">
            {service.duration_minutes} min{price ? `  ·  ${price}` : ''}
          </Text>
        </View>

        <View className="px-5 py-4 border-b border-fixme-border">
          <Text className="text-fixme-text-muted text-[11px] font-semibold uppercase tracking-wider mb-1">
            Date & time
          </Text>
          <Text className="text-fixme-text-primary font-semibold text-base">
            {formatDateFull(date)}
          </Text>
          <Text className="text-fixme-text-muted text-sm mt-0.5">
            {formatSlotTime(slot.start)} — {formatSlotTime(slot.end)}
          </Text>
        </View>

        <View className="px-5 py-4">
          <Text className="text-fixme-text-muted text-[11px] font-semibold uppercase tracking-wider mb-1">
            Contact
          </Text>
          <Text className="text-fixme-text-primary font-semibold text-base">{name}</Text>
          <Text className="text-fixme-text-muted text-sm mt-0.5">{email}</Text>
          <Text className="text-fixme-text-muted text-sm">{phone}</Text>
        </View>
      </View>

      {/* Book button */}
      <Pressable
        onPress={onBook}
        disabled={loading}
        style={({ pressed }) => ({ opacity: pressed || loading ? 0.7 : 1 })}
        className="bg-fixme-accent rounded-2xl py-4 items-center"
      >
        {loading
          ? <ActivityIndicator color={colors.bg} />
          : <Text className="text-fixme-bg font-bold text-base">Book now</Text>}
      </Pressable>
    </View>
  );
}

// ─── Step 5 — Done ───────────────────────────────────────────────────────────

function StepDone({
  bookingNumber, service, date, slot, onClose,
}: {
  bookingNumber?: string;
  service: ProviderPublicService;
  date: Date;
  slot: TimeSlot;
  onClose: () => void;
}) {
  return (
    <View className="flex-1 items-center justify-center px-4">
      {/* Checkmark */}
      <View className="w-20 h-20 rounded-full bg-green-400/15 items-center justify-center mb-6">
        <Text style={{ fontSize: 36 }}>✓</Text>
      </View>

      <Text className="text-fixme-text-primary font-bold text-[26px] tracking-tight text-center mb-2">
        Booking confirmed!
      </Text>
      <Text className="text-fixme-text-muted text-sm text-center mb-6">
        Your appointment is all set
      </Text>

      {/* Booking ref */}
      {bookingNumber && (
        <View className="bg-fixme-card border border-fixme-border rounded-full px-5 py-2 mb-6">
          <Text className="text-fixme-text-muted text-xs">
            Booking <Text className="text-fixme-accent font-bold">#{bookingNumber}</Text>
          </Text>
        </View>
      )}

      {/* Details */}
      <View className="w-full bg-fixme-card border border-fixme-border rounded-2xl overflow-hidden mb-8">
        <View className="px-5 py-4 border-b border-fixme-border">
          <Text className="text-fixme-text-primary font-semibold text-base">{service.name}</Text>
          <Text className="text-fixme-text-muted text-sm mt-0.5">
            {service.duration_minutes} min
          </Text>
        </View>
        <View className="px-5 py-4">
          <Text className="text-fixme-text-primary font-semibold text-base">
            {formatDateFull(date)}
          </Text>
          <Text className="text-fixme-text-muted text-sm mt-0.5">
            {formatSlotTime(slot.start)} — {formatSlotTime(slot.end)}
          </Text>
        </View>
      </View>

      <Pressable
        onPress={onClose}
        style={({ pressed }) => ({ opacity: pressed ? 0.7 : 1 })}
        className="w-full bg-fixme-accent rounded-2xl py-4 items-center"
      >
        <Text className="text-fixme-bg font-bold text-base">Done</Text>
      </Pressable>
    </View>
  );
}

// ─── BookingFlow (main export) ────────────────────────────────────────────────

export interface BookingFlowProps {
  visible: boolean;
  onClose: () => void;
  providerId: string;
  service: ProviderPublicService;
  initialDate?: Date | null;
}

export function BookingFlow({ visible, onClose, providerId, service, initialDate = null }: BookingFlowProps) {
  const [step, setStep] = useState(1);

  // Step 1 — date
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  // Step 2 — slot
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null);
  // Step 3 — contact
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [notes, setNotes] = useState('');
  // Step 4/5 — booking
  const [booking, setBooking] = useState<{ booking_number?: string } | null>(null);
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingError, setBookingError] = useState<string | null>(null);

  function reset() {
    setStep(1);
    setSelectedDate(null);
    setSelectedSlot(null);
    setName(''); setEmail(''); setPhone(''); setNotes('');
    setBooking(null); setBookingLoading(false); setBookingError(null);
  }

  function handleClose() {
    reset();
    onClose();
  }

  useEffect(() => {
    if (!visible || !initialDate) return;
    setSelectedDate(initialDate);
    setSelectedSlot(null);
    setStep(2);
  }, [initialDate, visible]);

  const handleSelectDate = useCallback((d: Date) => {
    setSelectedDate(d);
    setSelectedSlot(null);
    setStep(2);
  }, []);

  const handleSelectSlot = useCallback((slot: TimeSlot) => {
    setSelectedSlot(slot);
    setStep(3);
  }, []);

  const handleContactNext = useCallback(() => {
    if (!name.trim()) return;
    setStep(4);
  }, [name]);

  async function handleBook() {
    if (!selectedDate || !selectedSlot) return;
    setBookingLoading(true);
    setBookingError(null);
    try {
      const result = await createGuestBooking({
        provider_id: providerId,
        service_name: service.name,
        price_ex_vat: service.price_ex_vat ?? 0,
        scheduled_start: selectedSlot.start,
        scheduled_end: selectedSlot.end,
        customer_name: name.trim(),
        customer_email: email.trim(),
        customer_phone: phone.trim(),
        notes: notes.trim() || undefined,
      });
      setBooking(result);
      setStep(5);
    } catch (err: any) {
      const msg = err.message || '';
      if (msg.toLowerCase().includes('time slot') || msg.toLowerCase().includes('no longer available')) {
        setBookingError('This time slot was just taken. Picking another time\u2026');
        setTimeout(() => { setBookingError(null); setStep(2); }, 2500);
      } else {
        setBookingError(msg || 'Something went wrong. Please try again.');
      }
    } finally {
      setBookingLoading(false);
    }
  }

  const canProceedContact = name.trim().length > 0 && email.trim().includes('@');

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={handleClose}>
      <SafeAreaView className="flex-1 bg-fixme-bg" edges={['top']}>

        {/* Header */}
        <View className="flex-row items-center px-5 pt-4 pb-2">
          {step > 1 && step < 5 ? (
            <Pressable onPress={() => setStep(s => s - 1)} hitSlop={16} style={({ pressed }) => ({ opacity: pressed ? 0.4 : 1 })}>
              <Text style={{ fontSize: 26, lineHeight: 26, color: colors.textMuted }}>‹</Text>
            </Pressable>
          ) : (
            <View style={{ width: 26 }} />
          )}

          <View className="flex-1 items-center">
            <Text className="text-fixme-text-primary font-semibold text-[15px]">
              {service.name}
            </Text>
          </View>

          {step < 5 ? (
            <Pressable onPress={handleClose} hitSlop={16}>
              <Text className="text-fixme-text-muted text-[15px]">Cancel</Text>
            </Pressable>
          ) : (
            <View style={{ width: 52 }} />
          )}
        </View>

        {/* Progress */}
        {step < 5 && <ProgressDots step={step} total={4} />}

        {/* Content */}
        <View className="flex-1 px-5 pb-6">

          {step === 1 && (
            <StepDate onSelect={handleSelectDate} />
          )}

          {step === 2 && selectedDate && (
            <StepTime
              providerId={providerId}
              date={selectedDate}
              service={service}
              onSelect={handleSelectSlot}
            />
          )}

          {step === 3 && (
            <>
              <StepContact
                name={name} email={email} phone={phone} notes={notes}
                onChangeName={setName} onChangeEmail={setEmail}
                onChangePhone={setPhone} onChangeNotes={setNotes}
              />
              <Pressable
                onPress={handleContactNext}
                disabled={!canProceedContact}
                style={({ pressed }) => ({ opacity: pressed || !canProceedContact ? 0.4 : 1 })}
                className="bg-fixme-accent rounded-2xl py-4 items-center mt-4"
              >
                <Text className="text-fixme-bg font-bold text-base">Continue</Text>
              </Pressable>
            </>
          )}

          {step === 4 && selectedDate && selectedSlot && (
            <>
              <StepConfirm
                service={service}
                date={selectedDate}
                slot={selectedSlot}
                name={name} email={email} phone={phone}
                loading={bookingLoading}
                onBook={handleBook}
              />
              {bookingError && (
                <Text className="text-fixme-error text-sm text-center mt-3">{bookingError}</Text>
              )}
            </>
          )}

          {step === 5 && selectedDate && selectedSlot && (
            <StepDone
              bookingNumber={booking?.booking_number}
              service={service}
              date={selectedDate}
              slot={selectedSlot}
              onClose={handleClose}
            />
          )}

        </View>
      </SafeAreaView>
    </Modal>
  );
}
