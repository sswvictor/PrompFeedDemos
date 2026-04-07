/**
 * ModalSheet — bottom sheet / page sheet modal wrapper.
 *
 * Design: clean header row (cancel left, title centre, action right),
 * generous content area, keyboard-aware. Consistent across all modals
 * in the app — services form, confirmations, pickers.
 *
 * Usage:
 *   <ModalSheet
 *     visible={modalVisible}
 *     title="New service"
 *     onClose={() => setModalVisible(false)}
 *     action={<Button size="sm" loading={saving} onPress={handleSave}>Save</Button>}
 *   >
 *     …form content…
 *   </ModalSheet>
 *
 *   // Scroll content
 *   <ModalSheet visible={…} title="Edit service" onClose={…} scroll>
 *     …long form…
 *   </ModalSheet>
 */

import React from 'react';
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  ScrollView,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { IconButton } from './IconButton';

interface ModalSheetProps {
  visible: boolean;
  title: string;
  onClose: () => void;
  /** Right-side action — typically a Button with size="sm" */
  action?: React.ReactNode;
  children: React.ReactNode;
  /** Wrap content in a ScrollView */
  scroll?: boolean;
}

export function ModalSheet({
  visible,
  title,
  onClose,
  action,
  children,
  scroll = false,
}: ModalSheetProps) {
  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView
        className="flex-1 bg-fixme-light-bg dark:bg-fixme-bg"
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <SafeAreaView className="flex-1" edges={['top']}>

          {/* ── Header ── */}
          <View className="flex-row items-center px-5 pt-5 pb-4">

            {/* Cancel */}
            <IconButton onPress={onClose} hitSlop={16}>
              <Text className="
                text-[15px] font-medium
                text-fixme-light-text-muted dark:text-fixme-text-muted
              ">
                Cancel
              </Text>
            </IconButton>

            {/* Title — centred between cancel and action */}
            <Text className="
              flex-1 text-center
              text-[17px] font-bold tracking-tight
              text-fixme-light-text-primary dark:text-fixme-text-primary
              mx-3
            ">
              {title}
            </Text>

            {/* Right action — or invisible spacer to keep title centred */}
            <View style={{ minWidth: 56, alignItems: 'flex-end' }}>
              {action ?? null}
            </View>
          </View>

          {/* ── Content ── */}
          {scroll ? (
            <ScrollView
              className="flex-1"
              contentContainerClassName="px-5 pb-12"
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={false}
            >
              {children}
            </ScrollView>
          ) : (
            <View className="flex-1 px-5">
              {children}
            </View>
          )}

        </SafeAreaView>
      </KeyboardAvoidingView>
    </Modal>
  );
}
