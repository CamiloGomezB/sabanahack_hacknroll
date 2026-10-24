-- =============================================================================================
-- PROPUESTA · NO APLICADA · Rol "informatica" para el panel web
--
-- Va en un archivo propio porque un valor nuevo de enum no puede usarse en la misma transacción
-- en la que se crea. No es destructiva: solo añade un valor a public.rol_app.
-- es_operador() NO cambia: informática no opera recepción y la app móvil sigue igual.
-- =============================================================================================

alter type public.rol_app add value if not exists 'informatica';
