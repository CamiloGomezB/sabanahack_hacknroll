import * as Clipboard from 'expo-clipboard';
import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { Notice } from '@/components/Card';
import { Logo } from '@/components/Logo';
import { PillButton } from '@/components/PillButton';
import { Screen } from '@/components/Screen';
import { Txt } from '@/components/Txt';
import { UnderlineField } from '@/components/UnderlineField';
import { spacing } from '@/constants/theme';
import { useSession } from '@/features/auth/SessionProvider';
import { decodePassCode } from '@/features/temporary-access/pass';

/** Invitados y externos no tienen cuenta: abren el pase con el código que les compartieron. */
export default function OpenPassScreen() {
  const { openPass } = useSession();
  const params = useLocalSearchParams<{ c?: string }>();
  const [code, setCode] = useState(typeof params.c === 'string' ? params.c : '');
  const [error, setError] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);

  async function paste() {
    const text = await Clipboard.getStringAsync().catch(() => '');
    if (text) setCode(text);
  }

  async function submit() {
    const pass = decodePassCode(code);
    if (!pass) {
      setError('El código no es un pase válido de N Club. Cópialo completo, incluido "NC1.".');
      return;
    }
    setError(undefined);
    setLoading(true);
    try {
      await openPass(pass);
    } catch {
      setError('No se pudo guardar el pase en este teléfono.');
      setLoading(false);
    }
  }

  return (
    <Screen background="table" back title="Pase de acceso">
      <Logo size={84} />
      <Txt variant="body" align="center">
        Pega el código que te envió tu anfitrión o el personal del club.
      </Txt>
      <View style={styles.form}>
        <UnderlineField
          label="Código del pase"
          value={code}
          onChangeText={setCode}
          placeholder="NC1.…"
          autoCapitalize="none"
          autoCorrect={false}
          multiline
          error={error}
        />
        <PillButton label="Pegar del portapapeles" variant="ghost" icon="clipboard-outline" onPress={() => void paste()} />
        <PillButton label="Abrir pase" onPress={() => void submit()} loading={loading} disabled={!code.trim()} />
      </View>
      <Notice
        icon="shield-checkmark-outline"
        title="Tu pase solo sirve para la visita indicada"
        message="Recepción valida el código QR al ingresar. Desde un pase no se pueden crear invitaciones ni cambiar el nivel de acceso."
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  form: { gap: spacing.md, paddingHorizontal: spacing.sm },
});
