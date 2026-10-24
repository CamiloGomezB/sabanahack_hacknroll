import { Ionicons } from '@expo/vector-icons';
import type { ComponentProps } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Notice } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { Txt } from '@/components/Txt';
import type { ProfileKind } from '@/constants/profiles';
import { colors, radius, spacing } from '@/constants/theme';
import { useSession } from '@/features/auth/SessionProvider';
import { DEMO_PROFILE_OPTIONS } from '@/features/demo/demoData';

const ICONS: Record<ProfileKind, ComponentProps<typeof Ionicons>['name']> = {
  regular: 'person-outline',
  vip: 'diamond-outline',
  personal: 'briefcase-outline',
  invitado: 'ticket-outline',
  externo: 'construct-outline',
};

export default function DemoPickerScreen() {
  const { enterDemo } = useSession();
  return (
    <Screen background="church" back title="Modo demostración" dense>
      <Notice
        tone="demo"
        icon="flask-outline"
        title="Datos simulados"
        message="Elige un perfil para recorrer la app. Nada se guarda en Supabase y los códigos QR de este modo no autorizan el ingreso."
      />
      <View style={styles.list}>
        {DEMO_PROFILE_OPTIONS.map((o) => (
          <Pressable
            key={o.profile}
            accessibilityRole="button"
            accessibilityLabel={`Entrar como ${o.title}`}
            onPress={() => enterDemo(o.profile)}
            style={({ pressed }) => [styles.card, pressed && styles.pressed]}
          >
            <View style={styles.icon}>
              <Ionicons name={ICONS[o.profile]} size={22} color={colors.gold} />
            </View>
            <View style={styles.text}>
              <Txt variant="subtitle">{o.title}</Txt>
              <Txt variant="caption">{o.subtitle}</Txt>
            </View>
            <Ionicons name="chevron-forward" size={20} color={colors.textMuted} />
          </Pressable>
        ))}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: { gap: spacing.sm },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.glass,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.glassBorder,
  },
  pressed: { opacity: 0.75 },
  icon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  text: { flex: 1, gap: 2 },
});
