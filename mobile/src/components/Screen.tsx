import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import type { ReactNode } from 'react';
import {
  ImageBackground,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { colors, CONTENT_MAX_WIDTH, fonts, spacing } from '@/constants/theme';
import { useSession } from '@/features/auth/SessionProvider';

import { Txt } from './Txt';

// Fotografías extraídas del PDF de referencia.
const BACKGROUNDS = {
  church: require('../../assets/images/bg-church.jpg'),
  table: require('../../assets/images/bg-table.jpg'),
} as const;

interface ScreenProps {
  children: ReactNode;
  background?: keyof typeof BACKGROUNDS;
  /** Título de la barra superior. Si se omite no se muestra la barra. */
  title?: string;
  /** Muestra el botón de volver en la barra superior. */
  back?: boolean;
  right?: ReactNode;
  scroll?: boolean;
  /** Oscurece más la foto (pantallas con mucho texto). */
  dense?: boolean;
  contentStyle?: StyleProp<ViewStyle>;
}

export function Screen({
  children,
  background = 'table',
  title,
  back = false,
  right,
  scroll = true,
  dense = false,
  contentStyle,
}: ScreenProps) {
  const body = (
    <View style={[styles.content, contentStyle]}>{children}</View>
  );
  return (
    <ImageBackground source={BACKGROUNDS[background]} resizeMode="cover" style={styles.root}>
      <View style={[StyleSheet.absoluteFill, { backgroundColor: dense ? colors.overlayStrong : colors.overlay }]} />
      <SafeAreaView style={styles.flex} edges={['top', 'bottom']}>
        <DemoBanner />
        {title !== undefined || back ? <TopBar title={title} back={back} right={right} /> : null}
        <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          {scroll ? (
            <ScrollView
              contentContainerStyle={styles.scroll}
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={false}
            >
              {body}
            </ScrollView>
          ) : (
            body
          )}
        </KeyboardAvoidingView>
      </SafeAreaView>
    </ImageBackground>
  );
}

function TopBar({ title, back, right }: { title?: string; back: boolean; right?: ReactNode }) {
  return (
    <View style={styles.topBar}>
      <View style={styles.side}>
        {back ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Volver"
            hitSlop={12}
            onPress={() => (router.canGoBack() ? router.back() : router.replace('/home'))}
            style={styles.iconButton}
          >
            <Ionicons name="chevron-back" size={24} color={colors.white} />
          </Pressable>
        ) : null}
      </View>
      <Txt style={styles.title} numberOfLines={1} accessibilityRole="header">
        {title ?? ''}
      </Txt>
      <View style={[styles.side, styles.sideRight]}>{right}</View>
    </View>
  );
}

/** Franja visible en todas las pantallas mientras se usa el modo de demostración. */
function DemoBanner() {
  const { session, signOut } = useSession();
  if (session.status !== 'demo') return null;
  return (
    <View style={styles.banner} accessibilityRole="alert">
      <Ionicons name="flask-outline" size={14} color={colors.ink} />
      <Txt style={styles.bannerText}>MODO DEMOSTRACIÓN · datos simulados, sin Supabase</Txt>
      <Pressable accessibilityRole="button" accessibilityLabel="Salir del modo demostración" onPress={() => void signOut()} hitSlop={10}>
        <Txt style={[styles.bannerText, styles.bannerExit]}>Salir</Txt>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  scroll: { flexGrow: 1 },
  content: {
    flexGrow: 1,
    width: '100%',
    maxWidth: CONTENT_MAX_WIDTH,
    alignSelf: 'center',
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xl,
    gap: spacing.md,
  },
  topBar: {
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.sm,
    width: '100%',
    maxWidth: CONTENT_MAX_WIDTH + spacing.lg,
    alignSelf: 'center',
  },
  side: { width: 56, flexDirection: 'row' },
  sideRight: { justifyContent: 'flex-end' },
  iconButton: { padding: 6 },
  title: { flex: 1, textAlign: 'center', fontFamily: fonts.medium, fontSize: 16 },
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: colors.demo,
    paddingVertical: 5,
    paddingHorizontal: spacing.md,
  },
  bannerText: { fontFamily: fonts.semibold, fontSize: 11, color: colors.ink },
  bannerExit: { textDecorationLine: 'underline', marginLeft: 6 },
});
