import { Ionicons } from '@expo/vector-icons';
import type { ComponentProps } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { colors, spacing } from '@/constants/theme';

import { PillButton } from './PillButton';
import { Txt } from './Txt';

export function LoadingView({ message = 'Cargando…' }: { message?: string }) {
  return (
    <View style={styles.box} accessibilityLiveRegion="polite">
      <ActivityIndicator color={colors.white} />
      <Txt variant="caption" align="center">
        {message}
      </Txt>
    </View>
  );
}

export function ErrorView({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <View style={styles.box} accessibilityRole="alert">
      <Ionicons name="alert-circle-outline" size={28} color={colors.danger} />
      <Txt variant="body" align="center">
        {message}
      </Txt>
      {onRetry ? <PillButton label="Reintentar" variant="outline" icon="refresh" onPress={onRetry} /> : null}
    </View>
  );
}

export function EmptyView({
  message,
  icon = 'file-tray-outline',
}: {
  message: string;
  icon?: ComponentProps<typeof Ionicons>['name'];
}) {
  return (
    <View style={styles.box}>
      <Ionicons name={icon} size={26} color={colors.textMuted} />
      <Txt variant="caption" align="center">
        {message}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  box: { alignItems: 'center', justifyContent: 'center', gap: spacing.sm, paddingVertical: spacing.lg },
});
