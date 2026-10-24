import { CameraView, useCameraPermissions } from 'expo-camera';
import { useRef, useState } from 'react';
import { Image, Linking, Modal, StyleSheet, View } from 'react-native';

import { Notice } from '@/components/Card';
import { PillButton } from '@/components/PillButton';
import { Txt } from '@/components/Txt';
import { colors, radius, spacing } from '@/constants/theme';

interface FaceCameraProps {
  visible: boolean;
  onClose: () => void;
  /** Recibe la foto aceptada en base64 (JPEG). */
  onAccept: (base64: string) => Promise<void>;
}

/**
 * Cámara frontal para la foto de registro: guía ovalada, vista previa y "usar" o "repetir".
 * La foto solo se sube si la persona la acepta.
 */
export function FaceCamera({ visible, onClose, onAccept }: FaceCameraProps) {
  const [permission, requestPermission] = useCameraPermissions();
  const camera = useRef<CameraView>(null);
  const [ready, setReady] = useState(false);
  const [shot, setShot] = useState<{ uri: string; base64: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function close() {
    setShot(null);
    setError(null);
    setReady(false);
    onClose();
  }

  async function take() {
    if (!camera.current || !ready) return;
    setError(null);
    setBusy(true);
    try {
      const pic = await camera.current.takePictureAsync({ quality: 0.6, base64: true, shutterSound: false });
      if (!pic?.base64) throw new Error('La cámara no entregó la foto.');
      setShot({ uri: pic.uri, base64: pic.base64 });
    } catch {
      setError('No se pudo tomar la foto. Inténtalo de nuevo.');
    } finally {
      setBusy(false);
    }
  }

  async function accept() {
    if (!shot) return;
    setBusy(true);
    setError(null);
    try {
      await onAccept(shot.base64);
      close();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo subir la foto.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={close}>
      <View style={styles.root}>
        <Txt variant="subtitle" align="center">
          Foto para el reconocimiento
        </Txt>
        <Txt variant="caption" align="center">
          De frente, con buena luz, sin gafas oscuras ni gorra. Solo tu cara dentro del óvalo.
        </Txt>

        {!permission ? null : !permission.granted ? (
          <View style={styles.center}>
            <Notice
              tone="warning"
              title="La app necesita permiso para usar la cámara"
              message="Solo se usa aquí, para la foto que tú decidas subir."
            />
            {permission.canAskAgain ? (
              <PillButton label="Dar permiso" icon="camera-outline" onPress={() => void requestPermission()} />
            ) : (
              <PillButton label="Abrir ajustes" icon="settings-outline" onPress={() => void Linking.openSettings()} />
            )}
          </View>
        ) : shot ? (
          <Image source={{ uri: shot.uri }} style={styles.frame} resizeMode="cover" />
        ) : (
          <View style={styles.frame}>
            <CameraView
              ref={camera}
              style={StyleSheet.absoluteFill}
              facing="front"
              animateShutter={false}
              onCameraReady={() => setReady(true)}
            />
            <View pointerEvents="none" style={styles.guide} />
          </View>
        )}

        {error ? <Notice tone="danger" title={error} /> : null}

        {permission?.granted ? (
          shot ? (
            <View style={styles.row}>
              <PillButton label="Repetir" variant="outline" icon="refresh-outline" disabled={busy} onPress={() => setShot(null)} />
              <PillButton label="Usar esta foto" icon="cloud-upload-outline" loading={busy} onPress={() => void accept()} />
            </View>
          ) : (
            <PillButton label="Tomar foto" icon="camera-outline" loading={busy} disabled={!ready} onPress={() => void take()} />
          )
        ) : null}
        <PillButton label="Cancelar" variant="ghost" disabled={busy} onPress={close} />
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
    padding: spacing.lg,
    paddingTop: spacing.xxl,
    gap: spacing.md,
    justifyContent: 'center',
  },
  center: { gap: spacing.md },
  frame: {
    width: '100%',
    aspectRatio: 3 / 4,
    borderRadius: radius.md,
    overflow: 'hidden',
    backgroundColor: colors.overlayStrong,
    alignItems: 'center',
    justifyContent: 'center',
  },
  guide: {
    width: '62%',
    aspectRatio: 3 / 4,
    borderRadius: 999,
    borderWidth: 3,
    borderColor: colors.goldLight,
  },
  row: { flexDirection: 'row', gap: spacing.sm, justifyContent: 'center' },
});
