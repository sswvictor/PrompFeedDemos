/**
 * Tabs — horizontal tab bar with an animated underline indicator.
 *
 * Design: no background pill, no box — just clean labels and a precise
 * accent-coloured underline that slides between tabs. Editorial and airy,
 * like LTK's content tabs or The New York Times app.
 *
 * Usage:
 *   const [tab, setTab] = useState(0);
 *
 *   <Tabs
 *     tabs={['About', 'Services', 'Reviews']}
 *     activeIndex={tab}
 *     onChange={setTab}
 *   />
 *
 *   // With counts
 *   <Tabs
 *     tabs={['Services', 'Reviews']}
 *     counts={[services.length, reviews.length]}
 *     activeIndex={tab}
 *     onChange={setTab}
 *   />
 */

import { useEffect, useRef } from 'react';
import { Animated, Pressable, ScrollView, Text, View } from 'react-native';
import { colors } from '@/theme';

interface TabsProps {
  tabs: string[];
  activeIndex: number;
  onChange: (index: number) => void;
  /** Optional count badge shown after each label */
  counts?: number[];
  /** Inset percentage — shrinks underline from each side (0 = full width, 25 = half width centered) */
  underlineInset?: number;
  className?: string;
}

export function Tabs({ tabs, activeIndex, onChange, counts, underlineInset = 0, className = '' }: TabsProps) {

  // Track measured widths + positions of each tab for the sliding underline
  const tabLayouts = useRef<{ x: number; width: number }[]>([]);
  const underlineX     = useRef(new Animated.Value(0)).current;
  const underlineWidth = useRef(new Animated.Value(0)).current;

  function onTabLayout(index: number, x: number, width: number) {
    tabLayouts.current[index] = { x, width };

    // Animate when the active tab's layout is measured
    if (index === activeIndex) {
      underlineX.setValue(x);
      underlineWidth.setValue(width);
    }
  }

  useEffect(() => {
    const layout = tabLayouts.current[activeIndex];
    if (!layout) return;

    const insetPx = layout.width * (underlineInset / 100);

    Animated.spring(underlineX, {
      toValue: layout.x + insetPx,
      useNativeDriver: false,
      tension: 180,
      friction: 20,
    }).start();

    Animated.spring(underlineWidth, {
      toValue: layout.width - insetPx * 2,
      useNativeDriver: false,
      tension: 180,
      friction: 20,
    }).start();
  }, [activeIndex, underlineX, underlineWidth, underlineInset]);

  return (
    <View className={`${className}`}>
      <View className="flex-row">
        {tabs.map((tab, i) => {
          const isActive = i === activeIndex;
          return (
            <Pressable
              key={tab}
              onPress={() => onChange(i)}
              className="flex-1 items-center pb-3 pt-1"
              onLayout={e => onTabLayout(i, e.nativeEvent.layout.x, e.nativeEvent.layout.width)}
            >
              <View className="flex-row items-center gap-1.5">
                <Text
                  className={`
                    text-[15px] font-semibold tracking-tight
                    ${isActive
                      ? 'text-fixme-light-text-primary dark:text-fixme-text-primary'
                      : 'text-fixme-light-text-muted dark:text-fixme-text-muted'
                    }
                  `}
                >
                  {tab}
                </Text>

                {/* Count badge */}
                {counts?.[i] !== undefined && (
                  <View className="
                    bg-fixme-light-bg-soft dark:bg-fixme-bg-soft
                    rounded-full px-1.5 py-px
                  ">
                    <Text className="
                      text-[10px] font-semibold
                      text-fixme-light-text-muted dark:text-fixme-text-muted
                    ">
                      {counts[i]}
                    </Text>
                  </View>
                )}
              </View>
            </Pressable>
          );
        })}
      </View>

      {/* Animated underline — sits below the label row */}
      <View className="relative h-px bg-fixme-light-border dark:bg-fixme-border">
        <Animated.View
          style={{
            position: 'absolute',
            bottom: 0,
            left: underlineX,
            width: underlineWidth,
            height: 2,
            borderRadius: 2,
            backgroundColor: colors.accent,
          }}
        />
      </View>
    </View>
  );
}
