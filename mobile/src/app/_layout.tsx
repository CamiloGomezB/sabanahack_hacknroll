import { GreatVibes_400Regular } from '@expo-google-fonts/great-vibes';
import { PlayfairDisplay_400Regular } from '@expo-google-fonts/playfair-display';
import { Poppins_400Regular, Poppins_500Medium, Poppins_600SemiBold } from '@expo-google-fonts/poppins';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View } from 'react-native';

import { colors } from '@/constants/theme';
import { SessionProvider } from '@/features/auth/SessionProvider';

export default function RootLayout() {
  const [loaded, error] = useFonts({
    Poppins_400Regular,
    Poppins_500Medium,
    Poppins_600SemiBold,
    PlayfairDisplay_400Regular,
    GreatVibes_400Regular,
  });

  // Si las fuentes fallan se sigue con las del sistema: no se bloquea la app.
  if (!loaded && !error) return <View style={{ flex: 1, backgroundColor: colors.background }} />;

  return (
    <SessionProvider>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerShown: false,
          animation: 'fade',
          contentStyle: { backgroundColor: colors.background },
        }}
      />
    </SessionProvider>
  );
}
