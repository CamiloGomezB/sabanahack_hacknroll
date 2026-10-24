import { Redirect, Stack } from 'expo-router';

import { Logo } from '@/components/Logo';
import { PillButton } from '@/components/PillButton';
import { Screen } from '@/components/Screen';
import { LoadingView } from '@/components/StateViews';
import { Notice } from '@/components/Card';
import { colors } from '@/constants/theme';
import { isSignedIn, useSession } from '@/features/auth/SessionProvider';

export default function PublicLayout() {
  const { session, signOut } = useSession();

  if (session.status === 'loading') {
    return (
      <Screen background="church" scroll={false} contentStyle={{ justifyContent: 'center' }}>
        <Logo />
        <LoadingView message="Preparando N Club…" />
      </Screen>
    );
  }
  if (isSignedIn(session)) return <Redirect href="/home" />;
  if (session.status === 'noAccess') {
    return (
      <Screen background="church" scroll={false} contentStyle={{ justifyContent: 'center' }}>
        <Logo />
        <Notice tone="danger" icon="lock-closed-outline" title="No puedes ingresar" message={session.message} />
        <PillButton label="Cerrar sesión" variant="outline" onPress={() => void signOut()} />
      </Screen>
    );
  }
  return (
    <Stack
      screenOptions={{ headerShown: false, animation: 'fade', contentStyle: { backgroundColor: colors.background } }}
    />
  );
}
