import { Ionicons } from '@expo/vector-icons';
import type { ComponentProps } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { colors, fonts, radius } from '@/constants/theme';

import { Txt } from './Txt';

type Variant = 'primary' | 'outline' | 'ghost' | 'danger';

interface PillButtonProps {
  label: string;
  onPress: () => void;
  variant?: Variant;
  icon?: ComponentProps<typeof Ionicons>['name'];
  loading?: boolean;
  disabled?: boolean;
  fullWidth?: boolean;
  style?: StyleProp<ViewStyle>;
  accessibilityHint?: string;
}

/** Botón blanco en forma de píldora del PDF, con variantes para acciones secundarias. */
export function PillButton({
  label,
  onPress,
  variant = 'primary',
  icon,
  loading = false,
  disabled = false,
  fullWidth = false,
  style,
  accessibilityHint,
}: PillButtonProps) {
  const inactive = disabled || loading;
  const textColor = variant === 'primary' ? colors.ink : variant === 'danger' ? colors.danger : colors.white;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={accessibilityHint}
      accessibilityState={{ disabled: inactive, busy: loading }}
      onPress={onPress}
      disabled={inactive}
      style={({ pressed }) => [
        styles.base,
        styles[variant],
        fullWidth ? styles.full : styles.auto,
        pressed && !inactive ? styles.pressed : null,
        inactive ? styles.disabled : null,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={textColor} />
      ) : (
        <View style={styles.row}>
          {icon ? <Ionicons name={icon} size={18} color={textColor} /> : null}
          <Txt style={[styles.text, { color: textColor }, variant === 'ghost' && styles.ghostText]}>{label}</Txt>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 46,
    borderRadius: radius.pill,
    paddingHorizontal: 22,
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'center',
  },
  auto: { width: '78%', maxWidth: 320 },
  full: { width: '100%' },
  primary: { backgroundColor: colors.white },
  outline: { borderWidth: 1.5, borderColor: colors.white, backgroundColor: 'rgba(0,0,0,0.15)' },
  ghost: { minHeight: 36, backgroundColor: 'transparent' },
  danger: { borderWidth: 1.5, borderColor: colors.danger, backgroundColor: 'rgba(0,0,0,0.2)' },
  pressed: { opacity: 0.8, transform: [{ scale: 0.98 }] },
  disabled: { opacity: 0.45 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  text: { fontFamily: fonts.medium, fontSize: 14 },
  ghostText: { textDecorationLine: 'underline', fontSize: 13 },
});
