-- Generado por simulation/semilla_supabase.py. Datos de DEMOSTRACIÓN: personas inventadas
-- y huellas simuladas (modelo 'simulado-v1'). No son fotos ni huellas reales.
begin;

create or replace function pg_temp.c(s text) returns float8[] language sql as $$
  select array_agg(((('x' || substr(md5(s || ':' || i), 1, 8))::bit(32)::bigint)::float8
                    / 4294967295 * 2 - 1) order by i) from generate_series(0, 511) i $$;
create or replace function pg_temp.huella(r jsonb) returns extensions.vector
language sql as $$
  select (select array_agg(s order by i) from (
    select i, sum((e ->> 1)::float8 * (pg_temp.c(e ->> 0))[i]) as s
      from jsonb_array_elements(r) e, generate_series(1, 512) i group by i) t
  )::extensions.vector $$;

delete from public.fotografias where id in ('305b2bc2-c6a4-5e94-be43-20faf90296d4', '73ff7818-8154-5095-a2dd-ab5b1be751f8', '9971b024-58ba-5044-a814-c1516e39cc19', '7162b632-7987-5d08-be1a-780a69375b3c', 'dbcb0a6d-af10-5988-b4bc-9abd9e8c6904', '99601778-c910-5544-993b-f7e7dac4cecb', '7b540980-ed0d-5149-a4bc-371fc0362829', '9b4bc2d2-3bb1-5684-ac6e-c8f846e86681', '77642d18-61fb-516d-b97d-5b3b0567049c', '37beca17-0218-550b-bd8e-ca28cd66827a', '6f18e3c6-d2c4-5aeb-82b3-303173fd5607', '404c6d3d-a0f7-577f-9f67-6c3761482c4b', 'f9024762-d860-579c-8dbf-077e46a49798', '00fe12cb-1d35-55df-8804-3cde00f6fa4f', '571400b4-4626-5af5-9817-1776be6d0e56', '96c885fe-053b-533e-979f-908a6bd2dab6', '86ba34f1-0c66-5703-9f4b-c254b7ceb22a', '1c96a5c5-2fad-54da-9026-eca35885b3e8', '64751fea-08a5-53f8-b1c8-4ac30a284934', 'f3c7f047-0348-5251-8a90-ccd6ac813e66', '584043bb-5abc-544e-970b-f173f06fbec1', '747d3234-a510-5d50-a3a7-5b9f038e98a4', '457e83b4-17f3-5d73-af92-a0bf48b31461', 'd5b7cf82-6633-50a5-87d3-f8797b2780bf', '48650ca5-2405-5492-848d-e804117370ab', '8631e10b-375d-5fac-9381-dee8941667cc', '7fb12447-bfd6-5b36-b9e7-10c635b5f2c8', 'da00cf41-211f-5d2d-b66d-d3c118821067', '31d49913-ddc5-5c6d-b246-d6261c0ef558', 'b75889dc-2cd0-5255-ab2c-032a9da2530b', '6cc2bfcf-3284-5e01-8c62-0b5bad7a611e', 'c860f4ab-14b2-54dd-8da4-0ad8cc7b67a0', 'e5622a6a-4ffd-53bb-9848-6b2bdc5a1e9c', '0bb52f7d-f847-57d3-addf-0b5006c84dd7', '38120e53-0efc-5902-ae88-c4ada99dc698', '04fc8696-f440-50cc-aaee-00760fa054f8', '712bd70f-09cd-5ff7-9148-f9f25c0503da', '094eadb4-6365-5da4-ad61-fa85c07390f2', '027ae36f-b55d-5221-84a3-de1c7252f7ad', '6b5b1c99-f0a1-580c-a4d6-bf17cbefb4f8', '61f54a2b-876f-5333-8b84-cc2eb8454b15', '1ef84841-cf68-5f13-872f-1e995044e182', 'de226acd-dd9f-5e6b-8dca-1d12c13afefd', 'f27a4dd4-7de6-5e1d-afcf-e0502a1e44cd', 'b25d678e-d032-58da-917d-35aaee8cb060', '7d9dc0b1-677a-51fe-bdf4-56da10675e77', '5fcd789f-09dc-5072-90db-052038256816', 'df24ef0a-7d2f-5c96-8678-fdae8492c4d3', '51fdcf61-91dd-5f36-9c25-803b488aeb6d', '30d71d4f-62c5-5d90-9bde-ba2be2227083', 'e823a343-9cb3-52c1-9db3-91b7a9cfd862', 'fe6d346e-f391-5665-9943-ad5a41e069e1', 'c96ed96f-12ea-52e7-a64b-6b03a37dfd52', '26bcd1ec-3ac1-55ce-95e1-c44cbe0e896c', '8444b7d3-20d3-5732-9c05-cf045409abf0');
delete from public.personas where id in ('5a7baece-feee-50ae-acd8-84bfc989866b', '22532efc-230d-54c8-abe2-7600e2fd8ad9', '80c95c9d-9d82-5d74-b5da-7fe8b3a85fad', '6e4fa7cb-6ce5-5b79-b10d-897844931dbb', '945cb89f-78f7-5ef0-9138-7c67fc66c10a', '0412ee61-0040-52c9-8827-b7a4870924fd', '34adc026-71ae-5b73-bb72-190b49b60df1', 'ff5ff60c-79c3-56da-9c59-82d7e1f9c714', '33365230-63f3-53da-bee9-2a5fe95fbaa9', 'fd30b56b-4bdc-5b45-b989-9db236845351', '547f5f08-cb57-5920-ae1c-f8fc21861a4a', '03762c99-dca0-570c-80cf-a777673b7b8e', '59701761-53ff-56c3-8e03-61d545440ba6', 'bc55e545-46e1-5873-8628-87c6082bad5c', 'e8ea80c8-b150-56df-877f-4e0591c89e01');

insert into public.personas (id, nombre_demo, vinculo, estado, requiere_tour, horario_inicio, horario_fin, vinculo_hasta, consentimiento_biometrico, consentimiento_fecha) values
  ('5a7baece-feee-50ae-acd8-84bfc989866b', 'Valentina Rojas', 'vip', 'activa', false, '06:00:00', '21:00:00', null, true, now()),
  ('22532efc-230d-54c8-abe2-7600e2fd8ad9', 'Andrés Gómez', 'regular', 'activa', true, '06:00:00', '21:00:00', null, true, now()),
  ('80c95c9d-9d82-5d74-b5da-7fe8b3a85fad', 'Carlos Pérez', 'personal', 'activa', false, '06:00:00', '14:00:00', null, true, now()),
  ('6e4fa7cb-6ce5-5b79-b10d-897844931dbb', 'Laura Martínez', 'regular', 'activa', false, '06:00:00', '21:00:00', null, false, null),
  ('945cb89f-78f7-5ef0-9138-7c67fc66c10a', 'Diana López', 'personal', 'activa', false, '14:00:00', '22:00:00', null, true, now()),
  ('0412ee61-0040-52c9-8827-b7a4870924fd', 'Tomás Herrera', 'regular', 'activa', false, '06:00:00', '21:00:00', null, true, now()),
  ('34adc026-71ae-5b73-bb72-190b49b60df1', 'Mateo Castro', 'regular', 'activa', false, '06:00:00', '21:00:00', null, true, now()),
  ('ff5ff60c-79c3-56da-9c59-82d7e1f9c714', 'Lucía Vargas', 'regular', 'activa', false, '06:00:00', '21:00:00', null, true, now()),
  ('33365230-63f3-53da-bee9-2a5fe95fbaa9', 'Julián Mora', 'regular', 'activa', false, '06:00:00', '21:00:00', null, true, now()),
  ('fd30b56b-4bdc-5b45-b989-9db236845351', 'Ricardo Silva', 'regular', 'activa', false, '06:00:00', '21:00:00', current_date - 10, true, now()),
  ('547f5f08-cb57-5920-ae1c-f8fc21861a4a', 'Sofía Herrera', 'ninguno', 'activa', false, null, null, null, false, null),
  ('03762c99-dca0-570c-80cf-a777673b7b8e', 'Jorge Ramírez', 'ninguno', 'activa', false, null, null, null, false, null),
  ('59701761-53ff-56c3-8e03-61d545440ba6', 'Pedro Castillo', 'ninguno', 'activa', false, null, null, null, false, null),
  ('bc55e545-46e1-5873-8628-87c6082bad5c', 'Ana Torres', 'ninguno', 'activa', false, null, null, null, false, null),
  ('e8ea80c8-b150-56df-877f-4e0591c89e01', 'Marta Ruiz', 'ninguno', 'activa', false, null, null, null, false, null);

insert into public.visitas (id, persona_id, responsable_id, categoria, motivo, empresa, destino, inicio, fin, estado) values
  ('9353d7fc-114c-5726-82b4-0313a2df3c60', '547f5f08-cb57-5920-ae1c-f8fc21861a4a', '5a7baece-feee-50ae-acd8-84bfc989866b', 'invitado', 'Almuerzo', null, 'restaurante', now() + interval '-3600 seconds', now() + interval '10800 seconds', 'programada'),
  ('2f0c6204-2560-5166-afd8-2e5733fbc4f2', '03762c99-dca0-570c-80cf-a777673b7b8e', '80c95c9d-9d82-5d74-b5da-7fe8b3a85fad', 'externo', 'Orden de trabajo OT-1042: revisar el aire', 'Climatizar SAS', 'mantenimiento', now() + interval '-1800 seconds', now() + interval '14400 seconds', 'programada'),
  ('79a14bd0-8029-5930-85f4-7e67659d95d5', '59701761-53ff-56c3-8e03-61d545440ba6', '6e4fa7cb-6ce5-5b79-b10d-897844931dbb', 'invitado', null, null, 'piscina', now() + interval '-97200 seconds', now() + interval '-86400 seconds', 'programada'),
  ('c3c10de5-5928-5ccb-994b-7de4f73f127b', 'bc55e545-46e1-5873-8628-87c6082bad5c', '22532efc-230d-54c8-abe2-7600e2fd8ad9', 'invitado', null, null, 'piscina', now() + interval '0 seconds', now() + interval '7200 seconds', 'cancelada'),
  ('a52b7125-b7ec-56a9-a317-c6beda1357c9', 'e8ea80c8-b150-56df-877f-4e0591c89e01', '6e4fa7cb-6ce5-5b79-b10d-897844931dbb', 'invitado', null, null, 'piscina', now() + interval '-3600 seconds', now() + interval '7200 seconds', 'programada');

insert into public.credenciales (id, persona_id, visita_id, tipo, token_hash, valido_desde, valido_hasta, revocada_en, motivo_revocacion) values
  ('c2e9ef68-43bc-5a23-8ffa-1e7b4390457a', '5a7baece-feee-50ae-acd8-84bfc989866b', null, 'qr_personal', 'c8cedc716077fb166385efefe1a863b261e36282f7e4dd58e93ea223c26d2f03', now() + interval '-1080000 seconds', null, null, null),
  ('2b36d342-1027-5a5a-86f2-47b05275e066', '22532efc-230d-54c8-abe2-7600e2fd8ad9', null, 'qr_personal', '8c13253e3f9281862831009fd0144224783b805a62ef22abf9190f965f0332d2', now() + interval '-1080000 seconds', null, null, null),
  ('9b4641c0-b20d-5f11-aec3-c97619917577', '80c95c9d-9d82-5d74-b5da-7fe8b3a85fad', null, 'qr_personal', '91fa8e9f705ff3fe2cbabd89e8a265ce6bdf44bb2142a5a74d02e4f0fd7fa5e2', now() + interval '-1080000 seconds', null, null, null),
  ('1ebc364f-3a3d-5d14-98bd-bac4020a5878', '6e4fa7cb-6ce5-5b79-b10d-897844931dbb', null, 'qr_personal', '24c56713bc79366e321c786673e7c4755b05cc007ced524eeeddbd2dd53547e2', now() + interval '-1080000 seconds', null, null, null),
  ('30433cea-4827-50a4-b7d8-a6ea27e8d49d', '945cb89f-78f7-5ef0-9138-7c67fc66c10a', null, 'qr_personal', '36df70b16edb1ff3aa91fabee7f55c7f2e0ebc291b9d789db7c946cde663f7c2', now() + interval '-1080000 seconds', null, null, null),
  ('438eb1a8-3392-5ca0-8b8f-8c2f99da91c0', '0412ee61-0040-52c9-8827-b7a4870924fd', null, 'qr_personal', 'bd7c30bbdf130709d4cfff4daec93ee3c08fbd4af1730588122e937ff52b93c4', now() + interval '-1080000 seconds', null, null, null),
  ('c3db7128-068c-52e3-92ca-8f3ecec44542', '34adc026-71ae-5b73-bb72-190b49b60df1', null, 'qr_personal', '8babf139629eefca61411e582eb06dbcbca9da8106a685dda7089b59d5af6b30', now() + interval '-1080000 seconds', null, null, null),
  ('7e4f0076-3d39-53ef-ac85-d4c2f13b8fe1', 'ff5ff60c-79c3-56da-9c59-82d7e1f9c714', null, 'qr_personal', '137ea9273c0284f20ab71c29a4a4bd4c865c831ee5139cc189935f7c71132dd3', now() + interval '-1080000 seconds', null, null, null),
  ('0e541db5-1234-51b7-98b1-de2cdb094727', '33365230-63f3-53da-bee9-2a5fe95fbaa9', null, 'qr_personal', 'eb7aa54b133a2b050b6ace66055be67f4474b00cdf6f06c2581f4d8e46c9599a', now() + interval '-1080000 seconds', null, null, null),
  ('6079aa87-f083-53e6-9bc1-bb764632e95f', 'fd30b56b-4bdc-5b45-b989-9db236845351', null, 'qr_personal', '156b08f6e276d99c97d4701ffb1ba4edacf8f27612a651fcc5b4f7870a054c13', now() + interval '-1080000 seconds', null, null, null),
  ('40f2fa09-c1ee-5512-986d-9b99a01d4f5f', '547f5f08-cb57-5920-ae1c-f8fc21861a4a', '9353d7fc-114c-5726-82b4-0313a2df3c60', 'qr_visita', '2b5ea8113d78b8cb9eab6954e005582c6ce971f391c9cbb2a62fd639832c582b', now() + interval '-3600 seconds', now() + interval '10800 seconds', null, null),
  ('ef12d70e-aee9-5eea-b6c7-979a2eb02280', '03762c99-dca0-570c-80cf-a777673b7b8e', '2f0c6204-2560-5166-afd8-2e5733fbc4f2', 'qr_visita', '7ce7df8d16f5c53f4f90616a837d555cd63fdccfd27d3f41fdf5ef34976cb221', now() + interval '-1800 seconds', now() + interval '14400 seconds', null, null),
  ('b97c6593-9f8a-5792-afe7-ecdd8e09d19c', '59701761-53ff-56c3-8e03-61d545440ba6', '79a14bd0-8029-5930-85f4-7e67659d95d5', 'qr_visita', '4c232a338f86b3a866b43f0c795bef9b11c981da2ad7c0eee95fc6c102776827', now() + interval '-97200 seconds', now() + interval '-86400 seconds', null, null),
  ('de1ae114-a28a-52f7-a10f-08f84107b828', 'bc55e545-46e1-5873-8628-87c6082bad5c', 'c3c10de5-5928-5ccb-994b-7de4f73f127b', 'qr_visita', 'f47a0a4fe2716640b09df617ef3ac62eed950d8dc3d692d9238b7bb5dd5365ac', now() + interval '0 seconds', now() + interval '7200 seconds', now() + interval '-3600 seconds', 'Visita cancelada por el anfitrión'),
  ('fc255469-bd3b-5b12-9245-5038c044713c', 'e8ea80c8-b150-56df-877f-4e0591c89e01', 'a52b7125-b7ec-56a9-a317-c6beda1357c9', 'qr_visita', 'a895520f0d37f6b3ef56f20b936c387104371c648783acc16b9648baf58dd6a5', now() + interval '-3600 seconds', now() + interval '7200 seconds', null, null);

insert into public.fotografias (id, persona_id, ruta, uso, autorizada, autorizacion_fecha, embedding, modelo) values
  ('305b2bc2-c6a4-5e94-be43-20faf90296d4', '5a7baece-feee-50ae-acd8-84bfc989866b', 'demo/registro/valentina_r1.jpg', 'registro', true, now(), pg_temp.huella('[["valentina", 1.0], ["valentina_r1", 0.4]]'), 'simulado-v1'),
  ('73ff7818-8154-5095-a2dd-ab5b1be751f8', '5a7baece-feee-50ae-acd8-84bfc989866b', 'demo/registro/valentina_r2.jpg', 'registro', true, now(), pg_temp.huella('[["valentina", 1.0], ["valentina_r2", 0.4]]'), 'simulado-v1'),
  ('9971b024-58ba-5044-a814-c1516e39cc19', '5a7baece-feee-50ae-acd8-84bfc989866b', 'demo/registro/valentina_r3.jpg', 'registro', true, now(), pg_temp.huella('[["valentina", 1.0], ["valentina_r3", 0.4]]'), 'simulado-v1'),
  ('7162b632-7987-5d08-be1a-780a69375b3c', '5a7baece-feee-50ae-acd8-84bfc989866b', 'demo/prueba/valentina_p1.jpg', 'prueba', true, now(), null, null),
  ('dbcb0a6d-af10-5988-b4bc-9abd9e8c6904', '5a7baece-feee-50ae-acd8-84bfc989866b', 'demo/prueba/valentina_p2.jpg', 'prueba', true, now(), null, null),
  ('99601778-c910-5544-993b-f7e7dac4cecb', '22532efc-230d-54c8-abe2-7600e2fd8ad9', 'demo/registro/andres_r1.jpg', 'registro', true, now(), pg_temp.huella('[["andres", 1.0], ["andres_r1", 0.4]]'), 'simulado-v1'),
  ('7b540980-ed0d-5149-a4bc-371fc0362829', '22532efc-230d-54c8-abe2-7600e2fd8ad9', 'demo/registro/andres_r2.jpg', 'registro', true, now(), pg_temp.huella('[["andres", 1.0], ["andres_r2", 0.4]]'), 'simulado-v1'),
  ('9b4bc2d2-3bb1-5684-ac6e-c8f846e86681', '22532efc-230d-54c8-abe2-7600e2fd8ad9', 'demo/registro/andres_r3.jpg', 'registro', true, now(), pg_temp.huella('[["andres", 1.0], ["andres_r3", 0.4]]'), 'simulado-v1'),
  ('77642d18-61fb-516d-b97d-5b3b0567049c', '22532efc-230d-54c8-abe2-7600e2fd8ad9', 'demo/prueba/andres_p1.jpg', 'prueba', true, now(), null, null),
  ('37beca17-0218-550b-bd8e-ca28cd66827a', '22532efc-230d-54c8-abe2-7600e2fd8ad9', 'demo/prueba/andres_p2.jpg', 'prueba', true, now(), null, null),
  ('6f18e3c6-d2c4-5aeb-82b3-303173fd5607', '80c95c9d-9d82-5d74-b5da-7fe8b3a85fad', 'demo/registro/carlos_r1.jpg', 'registro', true, now(), pg_temp.huella('[["carlos", 1.0], ["carlos_r1", 0.4]]'), 'simulado-v1'),
  ('404c6d3d-a0f7-577f-9f67-6c3761482c4b', '80c95c9d-9d82-5d74-b5da-7fe8b3a85fad', 'demo/registro/carlos_r2.jpg', 'registro', true, now(), pg_temp.huella('[["carlos", 1.0], ["carlos_r2", 0.4]]'), 'simulado-v1'),
  ('f9024762-d860-579c-8dbf-077e46a49798', '80c95c9d-9d82-5d74-b5da-7fe8b3a85fad', 'demo/registro/carlos_r3.jpg', 'registro', true, now(), pg_temp.huella('[["carlos", 1.0], ["carlos_r3", 0.4]]'), 'simulado-v1'),
  ('00fe12cb-1d35-55df-8804-3cde00f6fa4f', '80c95c9d-9d82-5d74-b5da-7fe8b3a85fad', 'demo/prueba/carlos_p1.jpg', 'prueba', true, now(), null, null),
  ('571400b4-4626-5af5-9817-1776be6d0e56', '80c95c9d-9d82-5d74-b5da-7fe8b3a85fad', 'demo/prueba/carlos_p2.jpg', 'prueba', true, now(), null, null),
  ('96c885fe-053b-533e-979f-908a6bd2dab6', '945cb89f-78f7-5ef0-9138-7c67fc66c10a', 'demo/registro/diana_r1.jpg', 'registro', true, now(), pg_temp.huella('[["diana", 1.0], ["diana_r1", 0.4]]'), 'simulado-v1'),
  ('86ba34f1-0c66-5703-9f4b-c254b7ceb22a', '945cb89f-78f7-5ef0-9138-7c67fc66c10a', 'demo/registro/diana_r2.jpg', 'registro', true, now(), pg_temp.huella('[["diana", 1.0], ["diana_r2", 0.4]]'), 'simulado-v1'),
  ('1c96a5c5-2fad-54da-9026-eca35885b3e8', '945cb89f-78f7-5ef0-9138-7c67fc66c10a', 'demo/registro/diana_r3.jpg', 'registro', true, now(), pg_temp.huella('[["diana", 1.0], ["diana_r3", 0.4]]'), 'simulado-v1'),
  ('64751fea-08a5-53f8-b1c8-4ac30a284934', '945cb89f-78f7-5ef0-9138-7c67fc66c10a', 'demo/prueba/diana_p1.jpg', 'prueba', true, now(), null, null),
  ('f3c7f047-0348-5251-8a90-ccd6ac813e66', '945cb89f-78f7-5ef0-9138-7c67fc66c10a', 'demo/prueba/diana_p2.jpg', 'prueba', true, now(), null, null),
  ('584043bb-5abc-544e-970b-f173f06fbec1', '0412ee61-0040-52c9-8827-b7a4870924fd', 'demo/registro/tomas_r1.jpg', 'registro', true, now(), pg_temp.huella('[["tomas", 1.0], ["tomas_r1", 0.4]]'), 'simulado-v1'),
  ('747d3234-a510-5d50-a3a7-5b9f038e98a4', '0412ee61-0040-52c9-8827-b7a4870924fd', 'demo/registro/tomas_r2.jpg', 'registro', true, now(), pg_temp.huella('[["tomas", 1.0], ["tomas_r2", 0.4]]'), 'simulado-v1'),
  ('457e83b4-17f3-5d73-af92-a0bf48b31461', '0412ee61-0040-52c9-8827-b7a4870924fd', 'demo/registro/tomas_r3.jpg', 'registro', true, now(), pg_temp.huella('[["tomas", 1.0], ["tomas_r3", 0.4]]'), 'simulado-v1'),
  ('d5b7cf82-6633-50a5-87d3-f8797b2780bf', '0412ee61-0040-52c9-8827-b7a4870924fd', 'demo/prueba/tomas_p1.jpg', 'prueba', true, now(), null, null),
  ('48650ca5-2405-5492-848d-e804117370ab', '0412ee61-0040-52c9-8827-b7a4870924fd', 'demo/prueba/tomas_p2.jpg', 'prueba', true, now(), null, null),
  ('8631e10b-375d-5fac-9381-dee8941667cc', '34adc026-71ae-5b73-bb72-190b49b60df1', 'demo/registro/mateo_r1.jpg', 'registro', true, now(), pg_temp.huella('[["mateo", 1.0], ["mateo_r1", 0.4]]'), 'simulado-v1'),
  ('7fb12447-bfd6-5b36-b9e7-10c635b5f2c8', '34adc026-71ae-5b73-bb72-190b49b60df1', 'demo/registro/mateo_r2.jpg', 'registro', true, now(), pg_temp.huella('[["mateo", 1.0], ["mateo_r2", 0.4]]'), 'simulado-v1'),
  ('da00cf41-211f-5d2d-b66d-d3c118821067', '34adc026-71ae-5b73-bb72-190b49b60df1', 'demo/registro/mateo_r3.jpg', 'registro', true, now(), pg_temp.huella('[["mateo", 1.0], ["mateo_r3", 0.4]]'), 'simulado-v1'),
  ('31d49913-ddc5-5c6d-b246-d6261c0ef558', '34adc026-71ae-5b73-bb72-190b49b60df1', 'demo/prueba/mateo_p1.jpg', 'prueba', true, now(), null, null),
  ('b75889dc-2cd0-5255-ab2c-032a9da2530b', '34adc026-71ae-5b73-bb72-190b49b60df1', 'demo/prueba/mateo_p2.jpg', 'prueba', true, now(), null, null),
  ('6cc2bfcf-3284-5e01-8c62-0b5bad7a611e', 'ff5ff60c-79c3-56da-9c59-82d7e1f9c714', 'demo/registro/lucia_r1.jpg', 'registro', true, now(), pg_temp.huella('[["lucia", 1.0], ["lucia_r1", 0.4]]'), 'simulado-v1'),
  ('c860f4ab-14b2-54dd-8da4-0ad8cc7b67a0', 'ff5ff60c-79c3-56da-9c59-82d7e1f9c714', 'demo/registro/lucia_r2.jpg', 'registro', true, now(), pg_temp.huella('[["lucia", 1.0], ["lucia_r2", 0.4]]'), 'simulado-v1'),
  ('e5622a6a-4ffd-53bb-9848-6b2bdc5a1e9c', 'ff5ff60c-79c3-56da-9c59-82d7e1f9c714', 'demo/registro/lucia_r3.jpg', 'registro', true, now(), pg_temp.huella('[["lucia", 1.0], ["lucia_r3", 0.4]]'), 'simulado-v1'),
  ('0bb52f7d-f847-57d3-addf-0b5006c84dd7', 'ff5ff60c-79c3-56da-9c59-82d7e1f9c714', 'demo/prueba/lucia_p1.jpg', 'prueba', true, now(), null, null),
  ('38120e53-0efc-5902-ae88-c4ada99dc698', 'ff5ff60c-79c3-56da-9c59-82d7e1f9c714', 'demo/prueba/lucia_p2.jpg', 'prueba', true, now(), null, null),
  ('04fc8696-f440-50cc-aaee-00760fa054f8', 'fd30b56b-4bdc-5b45-b989-9db236845351', 'demo/registro/ricardo_r1.jpg', 'registro', true, now(), pg_temp.huella('[["ricardo", 1.0], ["ricardo_r1", 0.4]]'), 'simulado-v1'),
  ('712bd70f-09cd-5ff7-9148-f9f25c0503da', 'fd30b56b-4bdc-5b45-b989-9db236845351', 'demo/registro/ricardo_r2.jpg', 'registro', true, now(), pg_temp.huella('[["ricardo", 1.0], ["ricardo_r2", 0.4]]'), 'simulado-v1'),
  ('094eadb4-6365-5da4-ad61-fa85c07390f2', 'fd30b56b-4bdc-5b45-b989-9db236845351', 'demo/registro/ricardo_r3.jpg', 'registro', true, now(), pg_temp.huella('[["ricardo", 1.0], ["ricardo_r3", 0.4]]'), 'simulado-v1'),
  ('027ae36f-b55d-5221-84a3-de1c7252f7ad', 'fd30b56b-4bdc-5b45-b989-9db236845351', 'demo/prueba/ricardo_p1.jpg', 'prueba', true, now(), null, null),
  ('6b5b1c99-f0a1-580c-a4d6-bf17cbefb4f8', 'fd30b56b-4bdc-5b45-b989-9db236845351', 'demo/prueba/ricardo_p2.jpg', 'prueba', true, now(), null, null),
  ('61f54a2b-876f-5333-8b84-cc2eb8454b15', '33365230-63f3-53da-bee9-2a5fe95fbaa9', 'demo/registro/julian_r1.jpg', 'registro', true, now(), pg_temp.huella('[["julian", 1.0], ["julian_r1", 0.4]]'), 'simulado-v1'),
  ('1ef84841-cf68-5f13-872f-1e995044e182', '33365230-63f3-53da-bee9-2a5fe95fbaa9', 'demo/registro/julian_r2.jpg', 'registro', true, now(), pg_temp.huella('[["julian", 1.0], ["julian_r2", 0.4]]'), 'simulado-v1'),
  ('de226acd-dd9f-5e6b-8dca-1d12c13afefd', '33365230-63f3-53da-bee9-2a5fe95fbaa9', 'demo/registro/julian_r3.jpg', 'registro', true, now(), pg_temp.huella('[["julian", 1.0], ["julian_r3", 0.4]]'), 'simulado-v1'),
  ('f27a4dd4-7de6-5e1d-afcf-e0502a1e44cd', '33365230-63f3-53da-bee9-2a5fe95fbaa9', 'demo/prueba/julian_p1.jpg', 'prueba', true, now(), null, null),
  ('b25d678e-d032-58da-917d-35aaee8cb060', '33365230-63f3-53da-bee9-2a5fe95fbaa9', 'demo/prueba/julian_p2.jpg', 'prueba', true, now(), null, null),
  ('7d9dc0b1-677a-51fe-bdf4-56da10675e77', '547f5f08-cb57-5920-ae1c-f8fc21861a4a', 'demo/prueba/sofia_p1.jpg', 'prueba', true, now(), null, null),
  ('5fcd789f-09dc-5072-90db-052038256816', '03762c99-dca0-570c-80cf-a777673b7b8e', 'demo/prueba/jorge_p1.jpg', 'prueba', true, now(), null, null),
  ('df24ef0a-7d2f-5c96-8678-fdae8492c4d3', '59701761-53ff-56c3-8e03-61d545440ba6', 'demo/prueba/pedro_p1.jpg', 'prueba', true, now(), null, null),
  ('51fdcf61-91dd-5f36-9c25-803b488aeb6d', 'bc55e545-46e1-5873-8628-87c6082bad5c', 'demo/prueba/ana_p1.jpg', 'prueba', true, now(), null, null),
  ('30d71d4f-62c5-5d90-9bde-ba2be2227083', null, 'demo/prueba/desconocido_p1.jpg', 'prueba', true, now(), null, null),
  ('e823a343-9cb3-52c1-9db3-91b7a9cfd862', null, 'demo/prueba/visitante_p1.jpg', 'prueba', true, now(), null, null),
  ('fe6d346e-f391-5665-9943-ad5a41e069e1', 'e8ea80c8-b150-56df-877f-4e0591c89e01', 'demo/prueba/marta_p1.jpg', 'prueba', true, now(), null, null),
  ('c96ed96f-12ea-52e7-a64b-6b03a37dfd52', '34adc026-71ae-5b73-bb72-190b49b60df1', 'demo/prueba/mateo_p3.jpg', 'prueba', true, now(), null, null),
  ('26bcd1ec-3ac1-55ce-95e1-c44cbe0e896c', 'ff5ff60c-79c3-56da-9c59-82d7e1f9c714', 'demo/prueba/lucia_p3.jpg', 'prueba', true, now(), null, null),
  ('8444b7d3-20d3-5732-9c05-cf045409abf0', '33365230-63f3-53da-bee9-2a5fe95fbaa9', 'demo/prueba/julian_p3.jpg', 'prueba', true, now(), null, null);

commit;
