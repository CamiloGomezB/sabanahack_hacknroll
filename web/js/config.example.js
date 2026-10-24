'use strict';
// Copia este archivo como js/config.js (no se sube al repositorio) y completa los datos del MISMO
// proyecto de Supabase que usan la app móvil y la simulación: son EXPO_PUBLIC_SUPABASE_URL y
// EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY de appmobile/.env. Solo la clave PÚBLICA: nunca la
// service_role ni una sb_secret_, porque este archivo lo descarga el navegador.
// Sin js/config.js el panel abre en modo demostración.
window.NCLUB_SUPABASE_CONFIG = window.NCLUB_SUPABASE_CONFIG || {
  url: 'https://TU-PROYECTO.supabase.co',
  publishableKey: 'sb_publishable_xxxxxxxxxxxxxxxx',
};
