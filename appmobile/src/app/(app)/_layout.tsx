import { Redirect, Stack } from 'expo-router';

import { colors } from '@/constants/theme';
import { isSignedIn, useSession } from '@/features/auth/SessionProvider';

/** Grupo protegido: sin sesión real, de pase o de demostración se vuelve a la bienvenida. */
export default function AppLayout() {
  const { session } = useSession();
  if (session.status === 'loading') return null;
  if (!isSignedIn(session)) return <Redirect href="/" />;
  return (
    <Stack
      screenOptions={{ headerShown: false, animation: 'slide_from_right', contentStyle: { backgroundColor: colors.background } }}
    />
  );
}
