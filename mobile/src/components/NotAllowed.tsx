import { router } from 'expo-router';

import { Notice } from './Card';
import { PillButton } from './PillButton';
import { Screen } from './Screen';

/** Pantalla para funciones que el perfil actual no tiene (no basta con ocultar el botón). */
export function NotAllowed({ title, message }: { title: string; message: string }) {
  return (
    <Screen back title={title} contentStyle={{ justifyContent: 'center' }}>
      <Notice tone="danger" icon="lock-closed-outline" title="No disponible para tu perfil" message={message} />
      <PillButton label="Volver al inicio" variant="outline" onPress={() => router.replace('/home')} />
    </Screen>
  );
}
