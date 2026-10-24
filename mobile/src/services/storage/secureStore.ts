import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// Los tokens de QR son credenciales: en el teléfono van al llavero (Keychain / Keystore).
// En la vista web de desarrollo no hay llavero y se usa AsyncStorage.
const useFallback = Platform.OS === 'web';

export async function secureGet(key: string): Promise<string | null> {
  return useFallback ? AsyncStorage.getItem(key) : SecureStore.getItemAsync(key);
}

export async function secureSet(key: string, value: string): Promise<void> {
  if (useFallback) await AsyncStorage.setItem(key, value);
  else await SecureStore.setItemAsync(key, value);
}

export async function secureDelete(key: string): Promise<void> {
  if (useFallback) await AsyncStorage.removeItem(key);
  else await SecureStore.deleteItemAsync(key);
}

/** SecureStore solo admite [A-Za-z0-9._-] en las claves. */
export function storageKey(...parts: string[]): string {
  return parts.join('_').replace(/[^A-Za-z0-9._-]/g, '');
}
