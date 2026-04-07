import { useState } from 'react';
import { Image, Platform, Pressable, StyleSheet, View } from 'react-native';
import { Tabs } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors } from '@/theme';
import { FontAwesome6 } from '@expo/vector-icons';
import { AiCommandSheet } from '@/components/AiCommandSheet';
import { useProviderHomeUi } from '@/stores/providerHomeUi';

function TabIcon({ name, color }: { name: string; color: string }) {
  return <FontAwesome6 name={name} size={22} color={color} />;
}

const TAB_BAR_HEIGHT = Platform.OS === 'ios' ? 90 : 70;
const AI_BTN_SIZE = 78;
const AI_ICON_SIZE = 72;
const AI_BTN_RIGHT = 20;
const AI_BTN_OVERLAP = 24;

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
  },
  buttonAnchor: {
    flex: 1,
    justifyContent: 'flex-end',
    alignItems: 'flex-end',
  },
  button: {
    width: AI_BTN_SIZE,
    height: AI_BTN_SIZE,
    borderRadius: AI_BTN_SIZE / 2,
    backgroundColor: 'rgba(255, 255, 255, 0.12)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.22,
    shadowRadius: 10,
    elevation: 8,
    zIndex: 100,
  },
  buttonImage: {
    width: AI_ICON_SIZE,
    height: AI_ICON_SIZE,
    borderRadius: AI_ICON_SIZE / 2,
  },
});

export default function TabLayout() {
  const [aiOpen, setAiOpen] = useState(false);
  const insets = useSafeAreaInsets();
  const resetHomeToBookings = useProviderHomeUi((state) => state.resetToBookings);
  const aiButtonBottom = insets.bottom + TAB_BAR_HEIGHT - AI_BTN_OVERLAP;

  return (
    <View style={styles.root}>
      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarStyle: {
            backgroundColor: colors.bg,
            borderTopColor: colors.border,
            borderTopWidth: 1,
            paddingTop: 8,
            paddingBottom: Platform.OS === 'ios' ? 0 : 8,
            height: TAB_BAR_HEIGHT,
          },
          tabBarActiveTintColor: colors.accent,
          tabBarInactiveTintColor: colors.textMuted,
          tabBarLabelStyle: {
            fontSize: 11,
            fontWeight: '600',
            marginBottom: Platform.OS === 'ios' ? 0 : 4,
          },
        }}
      >
        <Tabs.Screen
          name="index"
          listeners={({ navigation }) => ({
            tabPress: () => {
              const state = navigation.getState();
              const activeRoute = state.routes[state.index]?.name;
              if (activeRoute === 'index') {
                resetHomeToBookings();
              }
            },
          })}
          options={{
            title: 'Home',
            tabBarIcon: ({ color }) => <TabIcon name="house" color={color} />,
          }}
        />
        <Tabs.Screen
          name="finance"
          options={{
            title: 'Finance',
            tabBarIcon: ({ color }) => <TabIcon name="wallet" color={color} />,
          }}
        />
        <Tabs.Screen
          name="profile"
          options={{
            title: 'Profile',
            tabBarIcon: ({ color }) => <TabIcon name="user" color={color} />,
          }}
        />
        <Tabs.Screen name="settings" options={{ href: null }} />
      </Tabs>

      {/* ── Floating AI button ── sits above the centre of the tab bar ── */}
      <View pointerEvents="box-none" style={styles.overlay}>
        <View
          pointerEvents="box-none"
          style={[
            styles.buttonAnchor,
            {
              paddingRight: AI_BTN_RIGHT,
              paddingBottom: aiButtonBottom,
            },
          ]}
        >
          <Pressable
            onPress={() => setAiOpen(true)}
            style={({ pressed }) => ({
              ...styles.button,
              opacity: pressed ? 0.85 : 1,
              transform: [{ scale: pressed ? 0.93 : 1 }],
            })}
          >
            <Image
              source={require('../../assets/ai-icon.png')}
              style={styles.buttonImage}
              resizeMode="cover"
            />
          </Pressable>
        </View>
      </View>

      {/* ── AI command sheet ── */}
      <AiCommandSheet
        visible={aiOpen}
        onClose={() => setAiOpen(false)}
        onDone={() => setAiOpen(false)}
      />
    </View>
  );
}
