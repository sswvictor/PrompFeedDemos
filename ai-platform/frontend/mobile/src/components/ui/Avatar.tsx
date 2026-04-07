/**
 * Avatar — profile image with automatic initials fallback.
 *
 * Sizes:
 *   xs  → 28px  (inline mentions, compact lists)
 *   sm  → 36px  (list rows)
 *   md  → 48px  (cards)                            ← default
 *   lg  → 64px  (profile headers)
 *   xl  → 88px  (profile screen hero)
 *
 * Usage:
 *   <Avatar name="Emma Svensson" />
 *   <Avatar name="Emma Svensson" uri={profile.avatar_url} size="xl" />
 *   <Avatar name="Emma" size="sm" />
 *   <Avatar name="Fixme Bot" size="md" online />
 */

import { Image, Text, View } from 'react-native';

interface AvatarProps {
  name: string;
  uri?: string | null;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  /** Show a green online dot */
  online?: boolean;
  className?: string;
}

const sizeMap = {
  xs: { box: 28, font: 11, dot: 8,  dotOffset: -1 },
  sm: { box: 36, font: 13, dot: 9,  dotOffset: -1 },
  md: { box: 48, font: 17, dot: 11, dotOffset: 0  },
  lg: { box: 64, font: 22, dot: 13, dotOffset: 1  },
  xl: { box: 88, font: 30, dot: 16, dotOffset: 2  },
} as const;

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function Avatar({ name, uri, size = 'md', online = false, className = '' }: AvatarProps) {
  const { box, font, dot, dotOffset } = sizeMap[size];
  const initials = getInitials(name);

  return (
    <View style={{ width: box, height: box }} className={`relative ${className}`}>

      {/* Circle */}
      <View
        style={{ width: box, height: box, borderRadius: box / 2 }}
        className="
          overflow-hidden items-center justify-center
          bg-fixme-light-bg-soft dark:bg-fixme-bg-soft
          border border-fixme-light-border dark:border-fixme-border
        "
      >
        {uri ? (
          <Image
            source={{ uri }}
            style={{ width: box, height: box }}
            resizeMode="cover"
          />
        ) : (
          <Text
            style={{ fontSize: font, lineHeight: font * 1.2 }}
            className="font-semibold text-fixme-light-text-secondary dark:text-fixme-text-secondary"
          >
            {initials}
          </Text>
        )}
      </View>

      {/* Online dot */}
      {online && (
        <View
          style={{
            position: 'absolute',
            bottom: dotOffset,
            right: dotOffset,
            width: dot,
            height: dot,
            borderRadius: dot / 2,
            borderWidth: 2,
          }}
          className="bg-fixme-light-success dark:bg-fixme-success border-fixme-light-bg dark:border-fixme-bg"
        />
      )}
    </View>
  );
}
