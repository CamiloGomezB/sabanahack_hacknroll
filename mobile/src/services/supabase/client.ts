import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient, type SupabaseClient } from '@supabase/supabase-js';
import { AppState, Platform } from 'react-native';

import { config } from '@/constants/config';

/**
 * Cliente con la clave pública: todo pasa por RLS. Si faltan las variables de entorno el cliente
 * es null y la app solo ofrece el modo de demostración.
 */
export const supabase: SupabaseClient | null = config.supabaseConfigured
  ? createClient(config.supabaseUrl, config.supabaseKey, {
      auth: {
        storage: AsyncStorage,
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: false,
      },
    })
  : null;

if (supabase && Platform.OS !== 'web') {
  AppState.addEventListener('change', (state) => {
    if (state === 'active') supabase.auth.startAutoRefresh();
    else supabase.auth.stopAutoRefresh();
  });
}

export function requireSupabase(): SupabaseClient {
  if (!supabase) {
    throw new Error('Supabase no está configurado. Revisa el archivo .env.');
  }
  return supabase;
}
