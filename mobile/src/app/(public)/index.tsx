import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { Notice } from '@/components/Card';
import { Logo, Wordmark } from '@/components/Logo';
import { PillButton } from '@/components/PillButton';
import { Screen } from '@/components/Screen';
import { Txt } from '@/components/Txt';
import { config } from '@/constants/config';
import { colors, spacing } from '@/constants/theme';

export default function WelcomeScreen() {
  const backend = config.supabaseConfigured;
  return (
    <Screen background="church" contentStyle={styles.content}>
      <View style={styles.hero}>
        <Logo size={104} />
        <Wordmark />
      </View>

      <View style={styles.actions}>
        {!backend ? (
          <Notice
            tone="warning"
            icon="cloud-offline-outline"
            title="Backend no configurado"
            message="Falta el archivo .env con la URL y la clave pública de Supabase. Puedes recorrer la app en modo demostración."
          />
        ) : null}
        <PillButton label="Iniciar sesión" onPress={() => router.push('/login')} disabled={!backend} />
        <PillButton label="Crear cuenta" variant="outline" onPress={() => router.push('/register')} disabled={!backend} />
        <PillButton label="Tengo un pase de acceso" variant="ghost" icon="ticket-outline" onPress={() => router.push('/pase')} />

        <View style={styles.divider}>
          <View style={styles.line} />
          <Txt variant="caption">o</Txt>
          <View style={styles.line} />
        </View>

        <PillButton
          label="Explorar en modo demostración"
          variant="outline"
          icon="flask-outline"
          onPress={() => router.push('/demo')}
        />
        <Txt variant="caption" align="center">
          El modo demostración usa datos simulados y no se conecta a Supabase.
        </Txt>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { justifyContent: 'space-between', paddingTop: spacing.xxl },
  hero: { alignItems: 'center', gap: spacing.lg },
  actions: { gap: spacing.md, paddingTop: spacing.xl },
  divider: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginVertical: spacing.xs },
  line: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: colors.glassBorder },
});
