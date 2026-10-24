import { Link } from 'expo-router';
import { useRef, useState } from 'react';
import { StyleSheet, View, type TextInputInstance } from 'react-native';

import { Notice } from '@/components/Card';
import { Logo, Wordmark } from '@/components/Logo';
import { PillButton } from '@/components/PillButton';
import { Screen } from '@/components/Screen';
import { Txt } from '@/components/Txt';
import { UnderlineField } from '@/components/UnderlineField';
import { spacing } from '@/constants/theme';
import { useSession } from '@/features/auth/SessionProvider';
import { friendlyError } from '@/utils/format';
import { hasErrors, validateEmail, type FieldErrors } from '@/utils/validation';

type Field = 'email' | 'password';

export default function LoginScreen() {
  const { signIn } = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<FieldErrors<Field>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const passwordRef = useRef<TextInputInstance>(null);

  async function submit() {
    const next: FieldErrors<Field> = {
      email: validateEmail(email),
      password: password ? undefined : 'Escribe tu contraseña.',
    };
    setErrors(next);
    setFormError(null);
    if (hasErrors(next)) return;
    setLoading(true);
    try {
      await signIn(email, password);
      // La redirección al panel la hace el layout cuando la sesión queda resuelta.
    } catch (e) {
      setFormError(friendlyError(e, 'No se pudo iniciar sesión.'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen background="church" back contentStyle={styles.content}>
      <View style={styles.hero}>
        <Logo size={92} />
        <Wordmark />
      </View>
      <View style={styles.form}>
        <UnderlineField
          label="Correo electrónico"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          textContentType="emailAddress"
          returnKeyType="next"
          onSubmitEditing={() => passwordRef.current?.focus()}
          error={errors.email}
        />
        <UnderlineField
          ref={passwordRef}
          label="Contraseña"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete="current-password"
          textContentType="password"
          returnKeyType="go"
          onSubmitEditing={() => void submit()}
          error={errors.password}
        />
        {formError ? <Notice tone="danger" icon="alert-circle-outline" title={formError} /> : null}
        <PillButton label="Ingresar" onPress={() => void submit()} loading={loading} style={styles.button} />
        <Link href="/register" replace style={styles.link}>
          <Txt variant="caption" align="center">
            ¿No tienes cuenta? <Txt variant="caption" style={styles.underline}>Crear cuenta</Txt>
          </Txt>
        </Link>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { justifyContent: 'center', gap: spacing.xl },
  hero: { alignItems: 'center', gap: spacing.md },
  form: { gap: spacing.lg, paddingHorizontal: spacing.md },
  button: { marginTop: spacing.sm },
  link: { alignSelf: 'center' },
  underline: { textDecorationLine: 'underline', color: '#fff' },
});
