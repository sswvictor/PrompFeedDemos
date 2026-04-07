/**
 * SegmentedControl — 2 or 3 option switcher with a sliding pill indicator.
 *
 * Design: sits on a soft bg track, the active pill slides with a spring
 * animation. Clean and tactile — like Uber's map/list toggle or the
 * iOS Photos grid/album switch, but custom-branded.
 *
 * Usage:
 *   const [view, setView] = useState(0);
 *
 *   <SegmentedControl
 *     options={['Provider', 'Customer']}
 *     activeIndex={view}
 *     onChange={setView}
 *   />
 *
 *   <SegmentedControl
 *     options={['Menu', 'Book', 'Reviews']}
 *     activeIndex={section}
 *     onChange={setSection}
 *   />
 */

import { useEffect, useRef, useState } from 'react';
import { Animated, LayoutChangeEvent, Pressable, Text, View } from 'react-native';

interface SegmentedControlProps {
  options: string[];
  activeIndex: number;
  onChange: (index: number) => void;
  className?: string;
}

export function SegmentedControl({
  options,
  activeIndex,
  onChange,
  className = '',
}: SegmentedControlProps) {
  const [trackWidth, setTrackWidth] = useState(0);
  const pillAnim = useRef(new Animated.Value(0)).current;

  const segmentWidth = trackWidth > 0 ? (trackWidth - 8) / options.length : 0;

  useEffect(() => {
    Animated.spring(pillAnim, {
      toValue: activeIndex * segmentWidth + 4, // 4px inset from track padding
      useNativeDriver: true,
      tension: 200,
      friction: 22,
    }).start();
  }, [activeIndex, segmentWidth, pillAnim]);

  function onTrackLayout(e: LayoutChangeEvent) {
    setTrackWidth(e.nativeEvent.layout.width);
  }

  return (
    <View
      onLayout={onTrackLayout}
      className={`
        relative flex-row
        bg-fixme-light-bg-soft dark:bg-fixme-bg-soft
        rounded-2xl p-1
        ${className}
      `}
    >
      {/* Sliding pill — rendered behind the labels */}
      {trackWidth > 0 && (
        <Animated.View
          style={{
            position: 'absolute',
            top: 4,
            bottom: 4,
            width: segmentWidth,
            borderRadius: 14,
            transform: [{ translateX: pillAnim }],
          }}
          className="
            bg-fixme-light-card dark:bg-fixme-card
            border border-fixme-light-border dark:border-fixme-border
          "
          // Subtle shadow to lift the pill off the track
          // eslint-disable-next-line react-native/no-inline-styles
          pointerEvents="none"
        />
      )}

      {/* Labels — sit above the animated pill */}
      {options.map((option, i) => {
        const isActive = i === activeIndex;
        return (
          <Pressable
            key={option}
            onPress={() => onChange(i)}
            className="flex-1 items-center justify-center py-2.5"
          >
            <Text
              className={`
                text-[13px] font-semibold tracking-tight
                ${isActive
                  ? 'text-fixme-light-text-primary dark:text-fixme-text-primary'
                  : 'text-fixme-light-text-muted dark:text-fixme-text-muted'
                }
              `}
            >
              {option}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
