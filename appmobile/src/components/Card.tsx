import { Ionicons } from '@expo/vector-icons';
import type { ComponentProps, ReactNode } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { colors, fonts, radius, spacing } from '@/constants/theme';

import { Txt } from './Txt';

/** Tarjeta translúcida sobre la fotografía de fondo. */
export function GlassCard({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.glass, style]}>{children}</View>;
}

export function SectionTitle({ children, right }: { children: string; right?: ReactNode }) {
  return (
    <View style={styles.sectionRow}>
      <Txt variant="overline">{children.toUpperCase()}</Txt>
      {right}
    </View>
  );
}

type Tone = 'success' | 'warning' | 'danger' | 'demo' | 'neutral' | 'gold';

const TONE: Record<Tone, { bg: string; fg: string }> = {
  success: { bg: 'rgba(127, 209, 160, 0.18)', fg: colors.success },
  warning: { bg: 'rgba(240, 195, 106, 0.18)', fg: colors.warning },
  danger: { bg: 'rgba(255, 138, 128, 0.18)', fg: colors.danger },
  demo: { bg: 'rgba(240, 195, 106, 0.22)', fg: colors.demo },
  neutral: { bg: 'rgba(255, 255, 255, 0.14)', fg: colors.white },
  gold: { bg: 'rgba(217, 189, 138, 0.22)', fg: colors.goldLight },
};

export function Badge({ label, tone = 'neutral' }: { label: string; tone?: Tone }) {
  const t = TONE[tone];
  return (
    <View style={[styles.badge, { backgroundColor: t.bg }]}>
      <Txt style={[styles.badgeText, { color: t.fg }]}>{label}</Txt>
    </View>
  );
}

interface NoticeProps {
  tone?: Tone;
  title: string;
  message?: string;
  icon?: ComponentProps<typeof Ionicons>['name'];
  children?: ReactNode;
}

/** Aviso destacado: funciones pendientes de backend, datos simulados o errores. */
export function Notice({ tone = 'neutral', title, message, icon = 'information-circle-outline', children }: NoticeProps) {
  const t = TONE[tone];
  return (
    <View style={[styles.notice, { borderLeftColor: t.fg, backgroundColor: t.bg }]} accessibilityRole="summary">
      <Ionicons name={icon} size={20} color={t.fg} />
      <View style={styles.noticeBody}>
        <Txt variant="label" color={t.fg}>
          {title}
        </Txt>
        {message ? <Txt variant="caption" color={colors.textMuted}>{message}</Txt> : null}
        {children}
      </View>
    </View>
  );
}

export function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Txt variant="label" color={colors.textMuted}>
        {label}:
      </Txt>
      <Txt variant="label" style={styles.infoValue}>
        {value}
      </Txt>
    </View>
  );
}

const styles = StyleSheet.create({
  glass: {
    backgroundColor: colors.glass,
    borderColor: colors.glassBorder,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
  },
  sectionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.sm,
  },
  badge: { borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 3, alignSelf: 'flex-start' },
  badgeText: { fontSize: 11, fontFamily: fonts.semibold, letterSpacing: 0.3 },
  notice: {
    flexDirection: 'row',
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.sm,
    borderLeftWidth: 3,
  },
  noticeBody: { flex: 1, gap: 2 },
  infoRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, alignItems: 'baseline' },
  infoValue: { flexShrink: 1 },
});
