import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { colors, spacing } from '@/constants/theme';

import { Logo } from './Logo';
import { Txt } from './Txt';

/** Cabecera de los paneles: acceso al perfil, logotipo, saludo e insignias. */
export function ProfileHeader({ name, badges, showProfileButton = true }: { name: string; badges?: ReactNode; showProfileButton?: boolean }) {
  return (
    <View style={styles.wrapper}>
      {showProfileButton ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Mi perfil y cerrar sesión"
          hitSlop={12}
          onPress={() => router.push('/perfil')}
          style={styles.profileButton}
        >
          <Ionicons name="person-circle-outline" size={30} color={colors.white} />
        </Pressable>
      ) : null}
      <Logo size={88} />
      <Txt variant="title" align="center" style={styles.name}>
        {name}
      </Txt>
      {badges ? <View style={styles.badges}>{badges}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { alignItems: 'center', gap: spacing.sm, paddingTop: spacing.lg },
  profileButton: { position: 'absolute', right: 0, top: spacing.sm, zIndex: 1, padding: 4 },
  name: { marginTop: spacing.xs },
  badges: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, justifyContent: 'center' },
});
