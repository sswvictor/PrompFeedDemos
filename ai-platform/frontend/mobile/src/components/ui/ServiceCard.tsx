/**
 * ServiceCard — displays a single service with metadata.
 *
 * Interactions:
 *   - Tap        → opens edit modal
 *   - Long press → slides left to reveal delete action
 *   - Tap again  → closes the reveal
 *
 * Design: generous padding, clear hierarchy, subtle border.
 * Active/Hidden badge uses green tint. Home visit shows 🏠 inline.
 *
 * Usage:
 *   <ServiceCard
 *     service={service}
 *     onEdit={() => openEdit(service)}
 *     onDelete={() => confirmDelete(service)}
 *   />
 */

import { useRef, useState } from 'react';
import { Animated, Pressable, Text, View } from 'react-native';

interface Service {
  service_id: string;
  name: string;
  category?: string;
  price_ex_vat: number;
  duration_minutes: number;
  home_service_available?: boolean;
  is_active: boolean;
}

interface ServiceCardProps {
  service: Service;
  onEdit: () => void;
  onDelete: () => void;
}

function fmtDuration(min: number) {
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

function fmtPrice(price: number, currency = 'SEK') {
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(Math.round(price));
  } catch {
    return `${Math.round(price)} ${currency}`;
  }
}

const DELETE_WIDTH = 80;

export function ServiceCard({ service, onEdit, onDelete }: ServiceCardProps) {
  const slideAnim = useRef(new Animated.Value(0)).current;
  const [revealed, setRevealed] = useState(false);

  function closeReveal() {
    Animated.spring(slideAnim, {
      toValue: 0, useNativeDriver: true, tension: 120, friction: 14,
    }).start();
    setRevealed(false);
  }

  function handlePress() {
    if (revealed) { closeReveal(); } else { onEdit(); }
  }

  function handleLongPress() {
    if (!revealed) {
      Animated.spring(slideAnim, {
        toValue: -DELETE_WIDTH, useNativeDriver: true, tension: 120, friction: 14,
      }).start();
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
    <View className="mb-3 rounded-2xl overflow-hidden">

      {/* ── Delete zone (revealed on long-press) ── */}
      <View
        style={{
          position: 'absolute', right: 0, top: 0, bottom: 0,
          width: DELETE_WIDTH,
          alignItems: 'center', justifyContent: 'center',
          backgroundColor: 'rgba(239,68,68,0.10)',
        }}
      >
        <Pressable onPress={handleDelete} className="items-center px-3 py-2">
          <Text style={{ fontSize: 22 }}>🗑</Text>
          <Text className="text-red-400 text-[11px] font-semibold mt-1">
            Delete
          </Text>
        </Pressable>
      </View>

      {/* ── Main card (slides left on long-press) ── */}
      <Animated.View style={{ transform: [{ translateX: slideAnim }] }}>
        <Pressable
          onPress={handlePress}
          onLongPress={handleLongPress}
          delayLongPress={380}
          className="
            bg-fixme-light-card dark:bg-fixme-card
            border border-fixme-light-border dark:border-fixme-border
            rounded-2xl px-5 py-5
            flex-row items-center
          "
        >
          {/* Left — name + meta */}
          <View className="flex-1 mr-4">
            <Text className="
              text-[15px] font-semibold mb-2
              text-fixme-light-text-primary dark:text-fixme-text-primary
            ">
              {service.name}
            </Text>

            <View className="flex-row items-center flex-wrap gap-1">
              <Text className="text-[13px] text-fixme-light-text-muted dark:text-fixme-text-muted">
                {fmtDuration(service.duration_minutes)}
              </Text>
              <Text className="text-[13px] text-fixme-light-border dark:text-fixme-border"> · </Text>
              <Text className="text-[13px] text-fixme-light-text-muted dark:text-fixme-text-muted">
                {fmtPrice(service.price_ex_vat)}
              </Text>
              {service.category ? (
                <>
                  <Text className="text-[13px] text-fixme-light-border dark:text-fixme-border"> · </Text>
                  <Text className="text-[13px] text-fixme-light-text-muted dark:text-fixme-text-muted">
                    {service.category}
                  </Text>
                </>
              ) : null}
              {service.home_service_available && (
                <Text style={{ fontSize: 13 }}> 🏠</Text>
              )}
            </View>
          </View>

          {/* Right — status badge + chevron */}
          <View className="items-end gap-2.5">
            <View
              className={
                service.is_active
                  ? 'px-3 py-1 rounded-full bg-green-400/10'
                  : 'px-3 py-1 rounded-full bg-white/5'
              }
            >
              <Text
                className={
                  service.is_active
                    ? 'text-[11px] font-semibold text-green-400'
                    : 'text-[11px] font-semibold text-fixme-light-text-muted dark:text-fixme-text-muted'
                }
              >
                {service.is_active ? 'Active' : 'Hidden'}
              </Text>
            </View>

            <Text className="text-fixme-light-text-muted dark:text-fixme-text-muted text-lg">
              ›
            </Text>
          </View>
        </Pressable>
      </Animated.View>
    </View>
  );
}
