import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Switch, View } from 'react-native';

import { GlassCard, Notice } from '@/components/Card';
import { Logo } from '@/components/Logo';
import { PillButton } from '@/components/PillButton';
import { Screen } from '@/components/Screen';
import { Txt } from '@/components/Txt';
import { UnderlineField } from '@/components/UnderlineField';
import { colors, spacing } from '@/constants/theme';
import { useSession } from '@/features/auth/SessionProvider';
import { friendlyError } from '@/utils/format';
import { hasErrors, validateEmail, validateName, validatePassword, type FieldErrors } from '@/utils/validation';

type Field = 'nombre' | 'email' | 'telefono' | 'password' | 'confirm';

export default function RegisterScreen() {
  const { signUp } = useSession();
  const [values, setValues] = useState({ nombre: '', email: '', telefono: '', password: '', confirm: '' });
  const [consent, setConsent] = useState(false);
  const [errors, setErrors] = useState<FieldErrors<Field>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [needsConfirmation, setNeedsConfirmation] = useState(false);

  const set = (key: Field) => (text: string) => setValues((v) => ({ ...v, [key]: text }));

  async function submit() {
    const phone = values.telefono.trim();
    const next: FieldErrors<Field> = {
      nombre: validateName(values.nombre),
      email: validateEmail(values.email),
      telefono: phone && !/^\+?[0-9\s-]{7,15}$/.test(phone) ? 'Escribe un teléfono válido.' : undefined,
      password: validatePassword(values.password),
      confirm: values.confirm !== values.password ? 'Las contraseñas no coinciden.' : undefined,
    };
    setErrors(next);
    setFormError(null);
    if (hasErrors(next)) return;
    setLoading(true);
    try {
      const { needsEmailConfirmation } = await signUp({
        nombre: values.nombre,
        email: values.email,
        password: values.password,
        telefono: values.telefono,
        consentimientoBiometrico: consent,
      });
      setNeedsConfirmation(needsEmailConfirmation);
    } catch (e) {
      setFormError(friendlyError(e, 'No se pudo crear la cuenta.'));
    } finally {
      setLoading(false);
    }
  }

  if (needsConfirmation) {
    return (
      <Screen background="church" back contentStyle={styles.center}>
        <Logo />
        <Notice
          tone="success"
          icon="mail-outline"
          title="Revisa tu correo"
          message={`Enviamos un enlace de confirmación a ${values.email.trim()}. Después de confirmarlo, inicia sesión: tu perfil se crea en ese momento.`}
        />
        <PillButton label="Ir a iniciar sesión" onPress={() => router.replace('/login')} />
      </Screen>
    );
  }

  return (
    <Screen background="church" back title="Crear cuenta" dense>
      <Logo size={76} />
      <View style={styles.form}>
        <UnderlineField label="Nombre completo" value={values.nombre} onChangeText={set('nombre')} autoComplete="name" error={errors.nombre} />
        <UnderlineField
          label="Correo electrónico"
          value={values.email}
          onChangeText={set('email')}
          autoCapitalize="none"
          keyboardType="email-address"
          autoComplete="email"
          error={errors.email}
        />
        <UnderlineField
          label="Teléfono (opcional)"
          value={values.telefono}
          onChangeText={set('telefono')}
          keyboardType="phone-pad"
          autoComplete="tel"
          error={errors.telefono}
        />
        <UnderlineField
          label="Contraseña"
          value={values.password}
          onChangeText={set('password')}
          secureTextEntry
          autoComplete="new-password"
          hint="Mínimo 8 caracteres."
          error={errors.password}
        />
        <UnderlineField
          label="Confirmar contraseña"
          value={values.confirm}
          onChangeText={set('confirm')}
          secureTextEntry
          autoComplete="new-password"
          error={errors.confirm}
        />

        <GlassCard>
          <View style={styles.switchRow}>
            <View style={styles.flex}>
              <Txt variant="label">Autorizo el uso de mi imagen facial</Txt>
              <Txt variant="caption">
                Opcional (Ley 1581 de 2012). Solo sirve para que el robot de recepción te reconozca; siempre puedes
                ingresar con tu QR. Puedes retirarlo cuando quieras.
              </Txt>
            </View>
            <Switch
              value={consent}
              onValueChange={setConsent}
              accessibilityLabel="Consentimiento biométrico"
              trackColor={{ true: colors.goldLight, false: 'rgba(255,255,255,0.25)' }}
              thumbColor={colors.white}
            />
          </View>
        </GlassCard>

        <Txt variant="caption" align="center">
          Las cuentas nuevas quedan como miembro regular. El nivel VIP y el perfil de personal los asigna el club.
        </Txt>
        {formError ? <Notice tone="danger" icon="alert-circle-outline" title={formError} /> : null}
        <PillButton label="Crear cuenta" onPress={() => void submit()} loading={loading} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  center: { justifyContent: 'center', gap: spacing.lg },
  form: { gap: spacing.lg, paddingHorizontal: spacing.sm },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  flex: { flex: 1, gap: 4 },
});
