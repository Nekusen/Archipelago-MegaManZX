"""Parche de ROM de Mega Man ZX (v0.1: marca AP + slot name).

Enfoque ligero (docs/playbook_ds_ap.md): el cliente opera por RAM, así
que el parche solo marca la ROM como seed AP y embebe el slot name para
validate_rom/set_auth. Se escribe en 0x1000 (zona de padding tras la
cabecera NDS; verificado a ceros en la ROM base, mismo truco que usa
Pokémon Platinum para su versión).

Layout en 0x1000:
  +0x00  b"MZXAP\\x00"          magia (6)
  +0x08  u32 versión del mundo
  +0x10  slot name (64 B utf-8, cero-terminado)
  +0x50  seed name (32 B)
"""

from settings import get_settings
from worlds.Files import (APProcedurePatch, APTokenMixin, APTokenTypes,
                          APPatchExtension)

MMZX_US_MD5 = "88b684b1b3eea885a07625da89f1e5b3"
AP_MAGIC_OFFSET = 0x1000
AP_MAGIC = b"MZXAP\x00"
WORLD_VERSION_INT = 1  # v0.1

# --- Parche de tutorial-skip (v0.2; RE en docs/v02_notes.md §2c/§2e/§2h) ---
# El handler de estado FUN_02022544 (entry Thumb 0x02022544) es la ranura 0
# de la tabla de handlers 0x020D8E28 y lo COMPARTEN "New Game" (game_state
# 0x10000) y la demo de attract/intro (game_state 0xB00). Por eso un redirect
# incondicional pisaba también la cinemática de arranque (playtest del
# usuario). Solución: un CODE-CAVE (Thumb) que solo redirige cuando
# game_state (0x0215E6D8) == 0x10000 (New Game real): en ese caso salta al
# handler de LOAD FUN_0202252c (entra a la escena por la ruta de LOAD, limpia,
# usando el bloque de 0x021602A8 que siembra el cliente); en cualquier otro
# caso (attract 0xB00, etc.) replica el prologue original (push{r4,lr};
# mov r4,r0; bl FUN_0202298c) y continúa en 0x0202254C -> intro/attract
# INTACTA. "Continue" (Load real) usa otra ranura y no se toca.
# Entry (8 B) @0x02022544: LDR R3,[PC,#0]; BX R3; .word CAVE|1.
# Bytes ensamblados con keystone (exp206), validados E2E (exp207).
SKIP_ENTRY_RAM = 0x02022544
SKIP_ENTRY = bytes.fromhex("004b184761b40c02")        # -> BX 0x020CB460
SKIP_ENTRY_ORIG = bytes.fromhex("10b5041c00f020fa")   # push;mov r4,r0;bl
SKIP_CAVE_RAM = 0x020CB460                            # hueco de ceros arm9
# v2 (2026-09-02, agente exp269p + keystone): el modo de New Game codifica
# personaje/dificultad (FUN_02017e68: tbl[personaje]<<16 | tbl[dificultad]
# <<24; Vent/Easy = 0x10000, AILE/Easy = 0x00000000, Normal suma 0x1000000) —
# el cave v1 comparaba con 0x10000 exacto y con Aile NO redirigía (escena
# del título como gameplay). v2: redirige si los 16 bits bajos del modo son
# 0 (cualquier personaje/dificultad; el attract 0xB00/0xC00 no cumple) Y el
# carrusel del título está en "partida lanzada" (u8 0x0214CD70 == 6; en los
# logos gs=0 pero paso<3). Ensamblado con keystone (Thumb @0x020CB460):
#   ldr r1,[pc,#0x1C]; ldr r1,[r1]; lsls r1,r1,#16; bne orig
#   ldr r2,[pc,#0x18]; ldrb r2,[r2]; cmp r2,#6; beq skip
#   orig: push{r4,lr}; mov r4,r0; bl FUN_0202298c; ldr r3,=0x0202254D; bx r3
#   skip: ldr r3,=0x0202252D; bx r3
#   pool: 0x0215E6D8, 0x0214CD70, 0x0202254D, 0x0202252D
SKIP_CAVE = bytes.fromhex(
    "07490968090403d1064a1278062a05d010b5044657f78afa034b1847034b1847"
    "d8e6150270cd14024d2502022d250202")

# --- Hu-gate (v0.2 EXPERIMENTAL; RE en docs/v02_notes.md §2f) ---
# Hu está hardcoded: la categoría 0 del chequeo de posesión FUN_0203e414
# tiene lista NULL en 0x020DEB78 → devuelve el count (1) → siempre poseída.
# Para hacerla item: apuntar lists[0] a un array de 1 flag [136] (=bit
# 0x021045DD.0, libre) → Hu exige ese flag. counts[0] ya es 1.
HUGATE_LISTS0_RAM = 0x020DEB78            # lists[0] (u32, hoy 0)
HUGATE_ARRAY_RAM = 0x020CB434             # hueco de ceros en arm9 (0x5A0 B)
HUGATE_FLAG_INDEX = 136                   # 0x021045DD bit0 (VERIFICADO libre)
HUGATE_LISTS0_ORIG = b"\x00\x00\x00\x00"

CFG_HU_IN_POOL = 0x01                     # byte 0 del config: bit0 = hu_in_pool

# --- Guarda del dibujador de sprites OAM (exp214-225, 2026-09-02) ---
# FUN_02009b74 (Thumb, 208 B + pool de 24 B) construye las entradas OAM de un
# drawable: hace UN bounds-check antes del bucle y sale del bucle solo con
# `subs r5,#1; beq`. Si el count de sprites del frame es 0 (tabla OAM
# machacada: p.ej. el bloque de 139 KB de un jefe cargado en 0x0224C000
# encima del heap de graficos del nivel mientras hay entidades vivas, al
# aparecer por teleport en la zona del jefe), el bucle da la vuelta y
# escribe sprites por toda la RAM (cursor 0x020F728C) -> soft-lock. Parche
# MINIMO (1 byte): el bucle termina con `subs r5,#1 ; beq exit`
# (0x02009C2E/30); `beq` (D001) -> `bls` (D901): LS = borrow (r5 era 0) OR
# Z (llego a 0), asi que con count==0 sale tras UNA iteracion (acotada por
# el bounds-check previo) en vez de dar la vuelta a 0xFFFFFFFF. Con
# count>=1 el comportamiento es identico. (Una relocalizacion a cueva de
# 240 B tambien funcionaba, exp225, pero rompia el limite del slot BLZ.)
OAMLOOP_BR_RAM = 0x02009C30
OAMLOOP_BR_ORIG = bytes.fromhex("01d0")   # beq +2
OAMLOOP_BR_NEW = bytes.fromhex("01d9")    # bls +2
# GEMELA: FUN_02009c5c tiene el MISMO bucle sin guarda (0x02009D7A `subs r5,#1`
# / 0x02009D7C `beq`), con los mismos bytes. Sin parchear, al disparar el primer
# mini-jefe de D-2 (Troop) el bucle da la vuelta y rocía la RAM: se vieron
# corrompidos 0x021045E0 (se perdía el flag de inicio de la misión, que deja la
# escena de Giro sin dispararse), 0x021045FC (Card Keys) y 0x02104602. Con el
# parche, CERO escrituras y cero corrupción (agente exp521 vs exp523).
OAMLOOP2_BR_RAM = 0x02009D7C
OAMLOOP2_BR_ORIG = bytes.fromhex("01d0")
OAMLOOP2_BR_NEW = bytes.fromhex("01d9")

# --- Guarda del dibujador de sprites: SET SIN RANURA DE VRAM (exp585, 2026-09-06) ---
# El registrador de sets `FUN_02006b1c` RECHAZA un set cuando (paletas ya asignadas +
# las que pide el set) > 0x0F (0x02006B86 pantalla 0 / 0x02006B92 pantalla 1) o cuando
# el cursor de tiles no cabe (0x02006B66): deja 0x02105C94[set] = 0xFF. Los DIEZ
# dibujadores de sprites resuelven entonces el registro de la ranura como NULL y
# leen igualmente:
#     movs r0,#0 ; ldrh r0,[r0,#2] ; movs r3,#1
# es decir, LEEN LA DIRECCIÓN 0x00000002 -> data abort (pc = 0xFFFF0108) -> pantalla
# gris y juego muerto. Es un bug LATENTE del juego (varias salas ya llegan al tope de
# 15 paletas OBJ en vanilla) que el set AP de los iconos destapa: al ocupar una paleta
# de forma permanente, en F-5 el efecto de impacto (set 124) se queda sin registrar y
# el primer golpe al jefe mata el juego (playtest del usuario 2026-09-06; repro y
# diagnóstico con SU savestate en BizHawk: exp585, docs/v02_notes.md §2k).
# Parche: en cada sitio, `ldrh r0,[r0,#2] ; movs r3,#1` -> `bl cave`; el cave sólo lee
# si r0 != 0. Un sprite sin ranura no se dibuja en vez de colgar la consola.
SPRITEGUARD_CAVE_RAM = 0x020C827C          # tras ICON_CAVES (0x020C81C4 + 184)
SPRITEGUARD_CAVE = bytes.fromhex("002800d0408801237047")   # cmp r0,#0; beq +; ldrh r0,[r0,#2]; movs r3,#1; bx lr
SPRITEGUARD_ORIG = bytes.fromhex("40880123")
SPRITEGUARD_SITES = [0x0200F0D4, 0x0200F244, 0x0200F424, 0x0200F85A, 0x0200FA5A,
                     0x0200FC96, 0x0200FFA2, 0x02010236, 0x020104CA, 0x02010756]


# --- Posesión de biometales "solo item AP" (H/F/L/P) — exp240 (2026-09-02),
# agente exp380-389, PROGRESIVOS exp444-447c (2026-09-03) ---
# La posesión de un modelo la resuelve FUN_0203e414 sobre tablas de categoría
# (counts @0x020DE9AC, listas @0x020DEB78): devuelve CUÁNTOS flags de la lista
# están puestos. En vanilla HX/FX/LX/PX tienen count=2 y lista [D0.x, D1.x]:
# el bit que escribe la victoria del 1er Pseudoroid del par (D0, = detección
# de la location "Obtain Biometal X") y el del 2º (D1). Un flag = una MITAD
# del biometal: con 1 el modelo se usa; con 2 (model_owned_count >= 2) los
# overlays de modelo suben el tope del contador de carga de 0x28 a 0x78
# (ataque cargado de nivel 2: HX 0x0218A3F8, FX 0x02187854, LX 0x02187D60,
# PX 0x02188E48) y el tope de WE es 4 x (lv jefe1 + lv jefe2).
# Parche: la lista pasa a ser [mitad 1, mitad 2] con flags LIBRES que solo
# pone el item AP (progresivo, 2 copias): la victoria del jefe enciende D0/D1
# (dispara el check) pero NO concede nada; count se deja en 2 (vanilla).
#   mitad 1 = 728-731 = 0x02104627.0-3 (agente exp380-389: a 0 en 268
#            savestates, fuera de toda tabla, ignorados por el popcount de
#            Transport; persisten en el save)
#   mitad 2 = 720-723 = 0x02104626.0-3 (exp447: solo los toca la copia
#            canónica<->vivo; exp447c: sobreviven a save + reset + Continue)
# Verificado exp446: con [728,720] y solo 728 -> count=1 (tope 0x28); con los
# dos -> count=2 y la rama de carga completa (tope 0x78). ANTES (v0.2) la
# lista era [flag libre] con count=1: ningún modelo podía estar "completo".
# cat -> (count_addr, list0_addr, flag_mitad1, orig_list0 (D0), flag_mitad2, orig_list1 (D1))
BIOMETAL_CAT_PATCH = {
    3: (0x020DE9AF, 0x020DE9CC, 728, 33, 720, 41),   # H: Hivolt D0.1 / Hurricaune D1.1 -> 0x02104627.0 / 0x02104626.0
    4: (0x020DE9B0, 0x020DE9BC, 729, 37, 721, 45),   # F: Fistleo D0.5 / Flammole D1.5   -> .1 / .1
    5: (0x020DE9B1, 0x020DE9E4, 730, 35, 722, 43),   # L: Lurerre D0.3 / Leganchor D1.3  -> .2 / .2
    6: (0x020DE9B2, 0x020DE9F4, 731, 39, 723, 47),   # P: Purprill D0.7 / Protectos D1.7 -> .3 / .3
}
BIOMETAL_CAT_COUNT = 2   # vanilla; se comprueba, no se cambia


# --- Life Ups / Sub Tanks: "recogido" != "capacidad" (agente exp300-309,
# 2026-09-02; verificado en RAM: recogida, spawn, puerta, muerte, save+reset+
# Continue). En vanilla el byte de capacidad 0x0214FC77 (Life Ups) /
# 0x0214FC78 (Sub Tanks) usa los bits 0-3 como "slot recogido" (= capacidad
# y = gate del spawn del pickup, FUN_020a3dd4) y se persiste en el save. En
# el randomizer el nibble BAJO es el conteo de items AP (cliente, capacidad
# autoritativa) y el nibble ALTO (bit 4+idx) pasa a ser "recogido fisico":
# lo pone el pickup (grant_life_up FUN_02045008 / grant_sub_tank
# FUN_02044ca4 parcheados), gatea el spawn y es la DETECCION del check.
# El pickup ya no sube HP max ni toca los contenidos de tanque. La quest de
# los Energy Packs (report -> grant_sub_tank idx 3) pone FC78.7: sin tanque.
PICKUP_FLAG_PATCH = [
    # (RAM, bytes originales, bytes nuevos)
    (0x02045014, "0121", "1021"),          # grant_life_up: movs r1,#1 -> #0x10 (bit 4+idx)
    (0x0204501E, "00f005f8", "c046c046"),  # grant_life_up: bl FUN_0204502c(p,4) -> nop nop (sin +4 HP max)
    (0x02044CAA, "0124", "1024"),          # grant_sub_tank: movs r4,#1 -> #0x10
    (0x02044CD4, "0a54", "c046"),          # grant_sub_tank: strb (contenido del tanque) -> nop
    (0x020A3E30, "0121", "1021"),          # spawn Life Up (FUN_020a3dd4): gate por bit 4+idx
    (0x020A3E86, "0121", "1021"),          # spawn Sub Tank: gate por bit 4+idx
]


# --- BUZÓN de pickups respawneables (agente exp360-369, 2026-09-02) ---
# Los refills colocados en el mapa (salud/WE/E-Crystal/1-Up, kind 6 sub 0)
# son locations OPCIONALES: la primera recogida de cada uno envía el check y
# después siguen respawneando. No hay flag persistente: el juego los instancia
# desde la tabla de coords de la sala (0x020C9C7C+0x240) por el spawner
# FUN_0200ca8c, que asocia a cada entidad viva un REGISTRO de spawn (pool
# 0x02107FB4, 48 x 12 B: +0 next, +4 entidad, +8 u16 índice de coords, +0xA
# attr; lista activa en 0x021081F4). Los drops de enemigos (FUN_020a37d8) no
# tienen registro. Parche: el `bl FUN_0200fc0c` del prólogo del think
# item_entity_update (FUN_020a309c, 0x020A30A2) pasa a `bl cave`; el cave
# (Thumb, 88 B en el hueco de ceros del arm9) llama a FUN_0200fc0c y, si la
# entidad r5 está "recogida" (+0x94 & 4 && +0xC0 != 0: el mismo test del
# think), busca su registro y escribe en el buzón
#   MAILBOX+0  u32 contador (sube 1 por recogida con identidad)
#   MAILBOX+4  anillo de 8 x u32 [u8 subárea 0x02108228, u8 índice de coords,
#              u8 role (+0x14), 0]  (entrada = contador & 7)
# El cliente sondea el contador y mapea (sub, idx) -> location (data.py
# LOCATIONS detect ['mailbox', sub, idx]); las repeticiones (respawn) las
# filtra el cliente. Verificado en RAM (exp364/365: 9 pickups en a01/c01 con
# índice correcto, re-entrada vuelve a escribir, drop de enemigo no escribe)
# y horneado por rom.py (exp366, arranque en frío por el skip). Hueco
# 0x020CB490-0x020CB9D4 sin lecturas ni escrituras en sesión (exp363).
PICKUP_MAILBOX_HOOK_RAM = 0x020A30A2
PICKUP_MAILBOX_HOOK_ORIG = bytes.fromhex("6cf7b3fd")   # bl FUN_0200fc0c
PICKUP_MAILBOX_HOOK_NEW = bytes.fromhex("28f0fdf9")    # bl 0x020CB4A0 (cave del buzón). 2026-09-04..05 apuntó al cave de MARCADO gris 0x020CB800 (PICKUP_MARK, agente exp483-491), retirado al llegar los iconos de item (§2c)
PICKUP_MAILBOX_CAVE_RAM = 0x020CB4A0                   # tras SKIP_CAVE (0x020CB460+48)
# push{r4,lr}; bl FUN_0200fc0c; ldr r0,[r5,#0x94]; lsrs #3; bcc done;
# ldr r0,[r5,#0xC0]; beq done; r1=[0x021081F4]; loop: beq done; [r1+4]==r5?
# -> found; r1=[r1]; b loop; found: r2=u16[r1+8]<<8 | u8[0x02108228] |
# u8[r5+0x14]<<16; r3=MAILBOX; r0=[r3]; [r3+4+(r0&7)*4]=r2; [r3]=r0+1;
# done: pop{r4,pc}; pool: 0x021081F4, 0x02108228, MAILBOX
PICKUP_MAILBOX_CAVE = bytes.fromhex(
    "10b544f7b3fb94202858c0081dd3c0202858002819d00d490968002915d04a68"
    "aa4201d00968f8e70a891202084800780243287d00040243064b186807240440"
    "a400e41862600130186010bdf48110022882100200b50c02")
PICKUP_MAILBOX_RAM = 0x020CB500          # = data.PICKUP_MAILBOX_ADDR (gen_ap_data)
PICKUP_MAILBOX_SLOTS = 8

# --- Avisos en pantalla del cliente AP ("NOTIFY"; agente exp473-480,
# 2026-09-04; docs/v02_notes.md §2a) ---
# El handler de gameplay FUN_02021bb0 llama cada frame a msg_tick FUN_0201242c
# (0x02021DD4). El bl pasa a un cave que, si hay una petición en el buzón y el
# sistema de mensajes (0x027E02C4) está libre (sin cutscene 0x0214F502.0 ni
# consola 0x0214F506.1), abre el POPUP PEQUEÑO del juego (el de "Found a Life
# Up!": no bloquea el gameplay) con el texto del buzón (replica
# show_pickup_msg FUN_020122d4 con puntero directo: OBJ+0x1C = BUF, OBJ+0xC =
# DUR, FUN_020121dc, FUN_02012050, OBJ+0x10 = tipo) o el mensaje vanilla `id`
# (REQ=2), y por último llama a msg_tick. REQ se borra al ver la fase de
# cierre (OBJ+0x11 == 6); si el mensaje se resetea antes (cambio de sala), se
# relanza. Buzón: u8 REQ (0/1 texto/2 id), u8 STATE (cave), u16 DUR (frames
# con el texto entero), +4 BUF (<= 0xFC B, fuente = ASCII-0x20, fin 0xFE).
# Popup = 1 línea de 30 glifos (el 31º pisa el 1º). Verificado en RAM y en
# frío (exp475-480).
NOTIFY_HOOK_RAM = 0x02021DD4
NOTIFY_HOOK_ORIG = bytes.fromhex("f0f72afb")   # bl FUN_0201242c
NOTIFY_HOOK_NEW = bytes.fromhex("a9f014fc")    # bl 0x020CB600
NOTIFY_CAVE_RAM = 0x020CB600                   # zona 0x020CB600-0x020CB7FF
NOTIFY_CAVE = bytes.fromhex(
    "10b5204c2078002839d01f496078002806d0487e062803d10020207060702ee0"
    "488900282bd18869002828d117480078400824d216480078800820d201206070"
    "2078022804d1a088618846f743fe16e0201d486260884861c889002801d03bf7"
    "61ff0c4846f7bafd0a4846f7f1fc0649087b002801d0012000e00220886146f7"
    "d5fe10bd00b70c02c4027e0202f5140206f51402cc027e02")
NOTIFY_RAM = 0x020CB700        # = data.NOTIFY_ADDR
NOTIFY_BUF_MAX = 0xFC
NOTIFY_POPUP_GLYPHS = 30

# --- Cutscenes SIEMPRE saltables (agente exp453-462, 2026-09-04;
# docs/v02_notes.md §2a) ---
# Vanilla: START solo salta una cutscene si su evento único (bitfield de 96
# bits 0x021045C0) ya está puesto: el opcode 0x23 sub 0 de la VM
# (FUN_0201bfd0, "abrir bloque saltable") solo pone el flag 0x10 de
# 0x0214F502 ("saltable") si el bit ya estaba; el lector de START
# FUN_0201b1c8 exige ese flag y salta al estado post-cutscene del handler
# (mismo camino que "morir y repetir": los flags/warps los reproduce el
# handler, no los opcodes restantes). Parche: (1) el beq "evento no visto"
# pasa a `mov r8,r8` => saltable siempre; (2) al saltar, un cave hace lo que
# haría el cierre del bloque (FUN_02008624(evento) = "visto" + backup) para
# que el estado quede IDÉNTICO al de ver la cutscene (0 bits de diferencia
# en 8 cutscenes, exp456-462). Solo afecta a los guiones con bloque 23 (87
# de 292: las de historia); las intros de jefe (1-2 mensajes) no lo tienen.
CUTSCENE_SKIP_PATCH = [
    (0x0201C00C, "17d0", "c046"),           # FUN_0201bfd0 (op 23 sub 0): beq -> mov r8,r8
    (0x0201B1E4, "1348417f", "b0f0acf9"),   # FUN_0201b1c8: ldr r3,=...; ldrb r1,[r0,#0x1d] -> bl 0x020CB540
]
CUTSCENE_SKIP_CAVE_RAM = 0x020CB540         # zona 0x020CB540-0x020CB5FF
# push {r4,lr}; ldr r4,=0x0214F500; ldrb r0,[r4,#3]; bl FUN_02008624;
# ldr r0,=0x0214F6B0; ldrb r1,[r0,#0x1d]; pop {r4,pc}; pool
CUTSCENE_SKIP_CAVE = bytes.fromhex("10b5034ce0783df76df80248417f10bd00f51402b0f61402")

# --- Iconos de biometal de la pantalla DATA SELECT (Continue) — exp429/430,
# 2026-09-03 ---
# El dibujador de los iconos de cada slot (FUN_02036104, un sprite por icono;
# buffer de slots 0x0215D808 + 0x4F4*slot = copia del bloque 0x021045CC del
# save) NO usa model_owned_count: testea bits CRUDOS del byte D0 del slot
# (bit0 ZX, bit1 H, bit3 L, bit5 F, bit7 P) y D2.1 (OX), y el primer icono
# enseña X siempre que no haya ZX. Con la posesión del randomizer en los
# flags libres 0x02104627.0-3 el save solo mostraba [X]. Parche in-place
# (mismo tamaño) por icono H/F/L/P:
#   ldrb r1,[r5,#4]; movs r0,#m; ands r1,r0; cmp r1,#0        (8 B)
#   -> ldr r1,[r5,#0x58]; lsrs r1,r1,#24; movs r0,#m'; ands r1,r0
# (u32 +0x58 alineado; su byte alto = +0x5B = 0x02104627; el `bne` original
# sigue valiendo porque `ands` fija Z). Icono X/ZX: la rama "sin ZX" pasa a
# un cave que pone el frame de X y OCULTA el sprite (bit0 de +0xA, como
# hacen los demás casos) si el slot no tiene X (+0x03 bit7 = 0x021045CF.7).
DATASELECT_ICON_PATCH = [
    # (RAM, bytes originales, bytes nuevos)
    (0x020361FC, "2979022001400029", "a96d090e01200140"),   # H: D0.1 -> 0x02104627.0
    (0x02036218, "2979202001400029", "a96d090e02200140"),   # F: D0.5 -> .1
    (0x02036234, "2979082001400029", "a96d090e04200140"),   # L: D0.3 -> .2
    (0x02036250, "2979802001400029", "a96d090e08200140"),   # P: D0.7 -> .3
    # icono X/ZX (rama sin ZX): mov r0,r4; movs r1,#2; bl FUN_0200fe64
    #   -> bl DATASELECT_CAVE; b fin_switch; nop
    (0x020361E2, "201c0221d9f73dfe", "95f0cdfb64e0c046"),
]
DATASELECT_CAVE_RAM = 0x020CB980     # hueco de ceros del arm9 (0x020CB434-0x020CB9D4)
# push{r4,r5,lr}; mov r0,r4; movs r1,#2; bl FUN_0200fe64; ldrb r0,[r5,#3];
# lsls r0,r0,#24; bmi ret; ldrb r1,[r4,#0xA]; movs r0,#0xFE; ands r1,r0;
# strb r1,[r4,#0xA]; ret: pop{r4,r5,pc}   (r4 = sprite, r5 = bloque del slot)
DATASELECT_CAVE = bytes.fromhex(
    "30b5201c022144f76dfae878000603d4a17afe200140a17230bd")

# --- "Go to Transerver" desde el menú de pausa (pestaña MISSION/mapa) —
# exp434-436, 2026-09-03 ---
# Petición del usuario: una opción de UI para volver al Transerver. El menú
# de pausa (game_state 0x101; struct 0x0215D7F8, página u8 +0x1825 =
# 0x0215F01D: 0 STATUS, 1 ITEM, 2 OPTIONS, 3 MISSION/mapa) despacha por
# tablas de punteros. En la pestaña del mapa el handler de scroll
# FUN_020272ac lee los botones MANTENIDOS (u16 0x020F2768): D-pad = scroll,
# A = scroll rápido, X = salir del scan; Y no se usa. START/B cierran el
# menú vía FUN_02022b0c (llamada desde FUN_0202323c @0x02023240).
# Parche: (A) el `ldr r1,=pad; ldrh r1,[r1]` de FUN_020272ac pasa a
# `bl CAVE_A`, que devuelve r1 = pad mantenido y, si Y acaba de PULSARSE
# (mantenido & ~anterior 0x020F276A, bit 11), pone WARP_FLAGS+0 = 1
# (petición para el CLIENTE, que la consume y teletransporta al último
# Transerver visitado) y WARP_FLAGS+1 = 1 (cerrar menú). (B) la llamada a
# FUN_02022b0c pasa a `bl CAVE_B`: si WARP_FLAGS+1 está puesto lo borra y
# devuelve 1 (= "cerrar", como START); si no, salta a FUN_02022b0c. Los
# textos de ayuda de la pestaña (m_sub_en.bin, NitroFS en 0xDFB200, tres
# variantes) cambian "<pad>Control Pad:Scan Area Map" por
# "Y Button:Go to Transerver" (misma longitud, in-place).
MENU_WARP_FLAGS_RAM = 0x020CB9D0    # u8 petición (cliente) + u8 cerrar (cave B); hueco de ceros
MENU_WARP_CAVE_A_RAM = 0x020CB99C   # tras DATASELECT_CAVE (0x020CB980+26)
# ldr r2,=0x020F2768; ldrh r1,[r2]; ldrh r3,[r2,#2]; mvns r3,r3; ands r3,r1;
# lsls r3,r3,#20; bpl ret; ldr r2,=FLAGS; movs r3,#1; strb r3,[r2]; strb r3,[r2,#1]; ret: bx lr
MENU_WARP_CAVE_A = bytes.fromhex(
    "054a11885388db430b401b0503d5034a012313705370704768270f02d0b90c02")
MENU_WARP_CAVE_B_RAM = 0x020CB438   # hueco entre HUGATE_ARRAY (4 B) y SKIP_CAVE
# ldr r1,=FLAGS; ldrb r2,[r1,#1]; cmp r2,#0; beq orig; movs r2,#0; strb r2,[r1,#1];
# movs r0,#1; bx lr; orig: ldr r3,=FUN_02022b0c|1; bx r3
MENU_WARP_CAVE_B = bytes.fromhex(
    "04494a78002a03d000224a7001207047014b1847d0b90c020d2b0202")
MENU_WARP_HOOKS = [
    # (RAM, bytes originales, bytes nuevos)
    (0x020272B6, "1d490988", "a4f071fb"),   # FUN_020272ac: ldr r1,=pad; ldrh r1,[r1] -> bl CAVE_A
    (0x02023240, "fff764fc", "a8f0faf8"),   # FUN_0202323c: bl FUN_02022b0c -> bl CAVE_B
]
MENU_WARP_TEXT_ROM = 0xDFB200        # m_sub_en.bin (NitroFS, sin comprimir; verificado byte a byte)
MENU_WARP_TEXT_OLD = bytes.fromhex("e0e1234f4e54524f4c003041441a3343414e0021524541002d4150")  # <pad>Control Pad:Scan Area Map
MENU_WARP_TEXT_NEW = bytes.fromhex("3900225554544f4e1a274f00544f003452414e5345525645520000")  # Y Button:Go to Transerver
MENU_WARP_TEXT_OFFS = (0xB14, 0xB4B, 0xB85)   # 3 variantes (sin/1/varios servers en el área)

# --- Sprite del Secret Disk = LOGO DE ARCHIPELAGO (agente exp463-467,
# 2026-09-04; docs/v02_notes.md §2b) ---
# obj_fnt.bin (NitroFS id 235, ROM 0x00F09000) tiene 511 "sets" de gráficos
# de objetos; el cuerpo del disco es la unidad 0x11 (16x16, 4bpp OBJ 1D,
# 4 tiles TL/TR/BL/BR, nibble bajo = píxel izquierdo, 128 B) del set 58
# (atlas de items: refills, 1-Up, disco, destellos), paleta OBJ slot 1. Las
# 4 series (B/M/E/O) comparten el frame. El set 58 se carga a VRAM una vez
# al arrancar. Parche in-place, mismo tamaño, sin recomprimir (fuera de la
# CRC de cabecera). Logo v1 (círculo con "A", exp465) sustituido por el
# logo oficial adaptado (exp495; ver DISK_LOGO_NEW).
# Verificado en frío: VRAM = logo, el disco de A-2/E-1 se ve y se recoge.
DISK_LOGO_ROM = 0x00F5F20C   # obj_fnt.bin + 0x5620C
DISK_LOGO_OLD = bytes.fromhex(
    "000044f40040458f0054f48800ff8f88f088888884884844dc44848844887800"
    "ff0f000088f8000088880f008888f8008888880f44848848884844cd00878844"
    "dc88780084ff8f88dc88f8ff4088888800848888004088880000847700004047"
    "008788cd88f8ff48ff8f88cd8888880488884800888804007748000074040000")
DISK_LOGO_NEW = bytes.fromhex(   # logo OFICIAL de Archipelago (sprite 16x16 del apworld de
    # Metroid Zero Mission, mzm/patcher/data/item_sprites/ap_logo.gfx frame 0) con sus 6
    # "islas" remapeadas a la paleta 1 del disco: granate 9, naranja C, verdes 1-3, azul 5,
    # azul-violeta 4 (el morado no existe), rojo A (el rosa no existe), contorno blanco F;
    # centro transparente. Conversión reproducible: work/experiments/495_ap_logo_official.py
    "000000f00000009f00f0ff9900cfcc9ff0ccccfcf0ccccfcf0fcfffc005f550f"
    "ff000000990f000099f9ff00991f110ff91111f1f91111f1fff1fff1004f440f"
    "f05555f5f05555f5f05555af005ff5aa00f0ffaa0000f0aa000000af000000f0"
    "f04444f4ff4444f4aa4f44f4aafa440faafaff00aafa0000aa0f0000ff000000")


# --- ICONOS DE ITEM EN EL MUNDO (2026-09-05, exp560-569; docs/v02_notes.md §2c) ---
# Cada pickup físico (94 discos, 8 Life Up/Sub Tank, 133 refills) se dibuja con el
# icono del ITEM que el randomizer ha puesto ahí: un SET de gráficos propio ("AP",
# worlds/mmzx/gfx/ap_set_*.bin, generado por tools/gen_icon_set.py: 3 logos de
# Archipelago useful/progression/filler, Life Up, Sub Tank, 8 chips, 8 badges de
# modelo del menú STATUS, 6 Card Keys del menú ITEM C; 4bpp, 1 paleta de 16) se
# INSERTA como set ICON_SET (vacío en vanilla) en obj_fnt.bin/obj_dat.bin (los
# offsets de los sets siguientes se desplazan; ambos ficheros se reubican al padding
# final de la ROM reescribiendo la FAT, receta exp551d/552b) y se hace RESIDENTE
# como el set 58: la lista de sets globales [0,1,58] de FUN_0200bd04 (u16[3]
# @0x020C9C30, con hueco de alineación) pasa a [0,1,58,ICON_SET] y sus dos
# `movs r2,#3` a #4; el cave de arranque (en lugar del `bl FUN_02006164` del set 58)
# registra ranura VRAM estática + slot de paleta (FUN_02006a88(mgr, fnt[set], set,
# 3,1,1) + FUN_02006164(mgr, set, 0,0,0,0,1,0)). Verificado (exp567b/569b): ranura
# VRAM 3 y paleta OBJ 2 constantes en las 69 salas + jefe; VRAM máx 123/128 KB.
# El CLIENTE escribe por subárea la TABLA (ICON_TABLE_RAM, RAM libre entre el slot
# de overlays 0x02184000 y 0x02194000, nunca leída ni escrita por el juego: exp560):
#   +0 u8 sub, +1 u8 flags (bit0 = válida), +4 u8 code[128] (índice de coords de la
#   entidad -> anim+1 del set AP; 0 = sin cambio), +0x84 u8 checked[32] (bitmap por
#   idx: "ya enviado" -> aspecto vanilla; los refills respawnean como lo que son).
# Caves (Thumb, HOLE_C8150 = tramo a cero del arm9 sin accesos, exp560): LOOKUP(ent)
# busca la entidad en la lista de spawns 0x021081F4 ([+4] = ent, u16[+8] = idx;
# exp566: ya está registrada en los tres inits) y devuelve anim o -1; ATTACH
# sustituye los 3 `bl FUN_02010624` (disco 0x020A3BC4, Life Up/Sub Tank 0x020A3EEE,
# refill 0x020A36F4) -> con override llama FUN_02010624(ent, ICON_SET) limpiando
# +0xB.3 (dinámico) y +0xC.0 (paleta de otro set); ANIM sustituye los 3
# `bl FUN_0200fe64` siguientes (0x020A3BCC / 0x020A3EF6 / 0x020A3706) -> si
# u16[ent+0x22] == ICON_SET usa la anim del LOOKUP. La recogida no cambia (exp568c).
# Reemplaza al marcador gris PICKUP_MARK (el cave se retiró; su hueco queda libre).
ICON_SET = 261
ICON_FNT_FILE_ID, ICON_DAT_FILE_ID = 235, 234     # obj_fnt.bin / obj_dat.bin (NitroFS)
DISK_LOGO_FNT_OFF = 0x5620C                       # = DISK_LOGO_ROM - inicio vanilla de obj_fnt (0x00F09000)
ICON_TABLE_RAM = 0x02191460
ICON_TABLE_SIZE = 0xA4
ICON_RESIDENT_LIST_PATCH = [
    (0x020C9C36, "0000", "0501"),     # 4ª entrada u16 de la lista [0,1,58] (hueco de alineación)
    (0x0200BD16, "0322", "0422"),     # FUN_0200bd04: movs r2,#3 -> #4 (fnt)
    (0x0200BDB6, "0322", "0422"),     # FUN_0200bd04: movs r2,#3 -> #4 (dat)
]
ICON_BOOT_HOOK_RAM = 0x0200BDA8                   # bl FUN_02006164 (subida VRAM del set 58) -> cave
ICON_BOOT_HOOK_ORIG = "faf7dcf9"
ICON_BOOT_CAVE_RAM = 0x020C8150                   # HOLE_C8150 (0x020C8150-0x020C8394 a cero y sin accesos, exp560)
ICON_BOOT_CAVE = bytes.fromhex("10b584b000240094019401240294002403940f483a21002200230e4ca04701240094c0460c480d4909680d4a03230d4ca047002400940194012402940024039409480a4900220023094ca04700f074f840571002656100024057100234390f0205010000896a0002405710020501000065610002")
# El set AP NO pide paleta propia (`str r4,[sp,#4]` -> nop en el cave de arranque) y
# comparte la del set 58 (residente, siempre cargado): PALSHARE escribe
# 0x02105EE4[261] = 0x02105EE4[58] y devuelve por el epílogo del cave. Si pidiera una,
# el juego se quedaría con 15 de 15 paletas OBJ en las salas pesadas y el siguiente set
# dinámico (p.ej. el efecto de impacto de F-5) no se registraría -> puntero NULL en el
# dibujador -> data abort (crash del usuario; exp585-589, docs/v02_notes.md §2k).
PALSHARE_CAVE_RAM = 0x020C8288             # tras SPRITEGUARD_CAVE (0x020C827C + 10)
PALSHARE_CAVE = bytes.fromhex("03483a21415c0348017004b010bdc046e45e1002e95f1002")
ICON_CAVES_RAM = 0x020C81C4                       # lookup / attach / anim (tras el cave de arranque)
ICON_CAVES = bytes.fromhex("30b5264c2178264a127891421cd16178c90719d023490968002915d04a68824201d00968f8e70a89802a0dd2d3088433e35c07251540eb40db0705d1231d985c002801d0013830bd0020c04330bd30b504000d00fff7d4ff002808dbe17a08229143e172217b0122914321730e4d200029000e4a904730bd30b504000d00428c0b4b9a4204d1fff7bbff002800db050020002900074a904730bd00bf6014190228821002f481100205010000250601020501000065fe0002")
ICON_ATTACH_CAVE_RAM = 0x020C8212
ICON_ANIM_CAVE_RAM = 0x020C823C
ICON_ATTACH_HOOKS = [(0x020A3BC4, "6cf72efd"), (0x020A3EEE, "6cf799fb"), (0x020A36F4, "6cf796ff")]
ICON_ANIM_HOOKS = [(0x020A3BCC, "6cf74af9"), (0x020A3EF6, "6bf7b5ff"), (0x020A3706, "6cf7adfb")]


def _thumb_bl(src: int, dst: int) -> bytes:
    """Codifica un `bl dst` Thumb (4 B) situado en src."""
    import struct
    off = dst - (src + 4)
    return struct.pack("<HH", 0xF000 | ((off >> 12) & 0x7FF), 0xF800 | ((off >> 1) & 0x7FF))


def _gfx_data(name: str) -> bytes:
    """Bloque binario de worlds/mmzx/gfx/ (también dentro del .apworld)."""
    import os
    import pkgutil
    try:
        data = pkgutil.get_data(__name__.rsplit(".", 1)[0], "gfx/" + name)
    except Exception:
        data = None
    if data is None:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gfx", name), "rb") as f:
            data = f.read()
    return data


def _insert_set(blob: bytes, setno: int, block: bytes) -> bytes:
    """Inserta `block` como set `setno` (hoy vacío) en un fichero obj_fnt/obj_dat
    (u32 count + u32 offset[count+1]; tamaño del set i = off[i+1]-off[i])."""
    import struct
    n = struct.unpack_from("<I", blob, 0)[0]
    offs = [struct.unpack_from("<I", blob, 4 + i * 4)[0] for i in range(n + 1)]
    if offs[n] != len(blob):
        raise ValueError("MMZX: tabla de offsets del fichero de sets inesperada")
    if offs[setno] != offs[setno + 1]:
        raise ValueError("MMZX: el set %d no está vacío" % setno)
    block = block + bytes((-len(block)) % 4)
    new = bytearray(blob[:4])
    for i in range(n + 1):
        new += struct.pack("<I", offs[i] + (len(block) if i > setno else 0))
    new += blob[4 + (n + 1) * 4:offs[setno]] + block + blob[offs[setno]:]
    return bytes(new)


def _install_icon_set(d: bytearray) -> int:
    """Inserta el set AP en obj_dat/obj_fnt y reubica ambos ficheros al padding final
    de la ROM (FAT + tamaño usado 0x80). Devuelve el nuevo inicio de obj_fnt.bin."""
    import struct
    fat = struct.unpack_from("<I", d, 0x48)[0]
    fatsize = struct.unpack_from("<I", d, 0x4C)[0]
    used = max(struct.unpack_from("<II", d, fat + k * 8)[1] for k in range(fatsize // 8))
    cur = (used + 0x1FF) & ~0x1FF
    fnt_start = None
    for fid, name in ((ICON_DAT_FILE_ID, "ap_set_dat.bin"), (ICON_FNT_FILE_ID, "ap_set_fnt.bin")):
        s0, e0 = struct.unpack_from("<II", d, fat + fid * 8)
        newfile = _insert_set(bytes(d[s0:e0]), ICON_SET, _gfx_data(name))
        if cur + len(newfile) > len(d) or any(d[cur:cur + len(newfile)]):
            raise ValueError("MMZX: no hay padding libre para reubicar el fichero %d" % fid)
        d[cur:cur + len(newfile)] = newfile
        struct.pack_into("<II", d, fat + fid * 8, cur, cur + len(newfile))
        if fid == ICON_FNT_FILE_ID:
            fnt_start = cur
        cur = (cur + len(newfile) + 0x1FF) & ~0x1FF
    struct.pack_into("<I", d, 0x80, cur)          # "used ROM size"
    return fnt_start

# --- Compresor BLZ con parse ÓPTIMO (agente exp360-369, exp367) ---
# El arm9 recomprimido debe caber en su slot de la ROM (0x8F400 B). El greedy
# de ndspy dejaba 76 B de margen y el cave del buzón ya no cabía. Mismo
# formato (LZ hacia atrás: literal 9 bits, match 17 bits con len 3..18 y
# disp 0..0xFFF, sin solapamiento, igual que ndspy) pero eligiendo los tokens
# por programación dinámica: 0x8DB04 B frente a 0x8F3A8 B del greedy (6.3 KB
# de margen; 5.6 s frente a 3.2 s). Round-trip verificado con
# ndspy.codeCompression.decompress y arranque real (exp366). Se inyecta en
# ndspy por monkeypatch de _lzCommon.compress SOLO durante arm9.save().
def _lz_compress_optimal(data, posSubtract, maxMatchDiff, maxMatchLen, zerosAtEnd,
                         searchReverse):
    """Misma firma/retorno que ndspy._lzCommon.compress:
    (stream, ignorableDataAmount, ignorableCompressedAmount)."""
    n = len(data)
    data = bytes(data)
    maxlen = [0] * (n + 1)
    mpos = [0] * (n + 1)
    find = data.rfind if searchReverse else data.find
    for pos in range(n):
        start = pos - maxMatchDiff
        if start < 0:
            start = 0
        if find(data[pos:pos + 3], start, pos) == -1:
            continue
        lower, upper = 3, min(maxMatchLen, n - pos)
        rec_p = rec_l = 0
        while lower <= upper:
            length = (lower + upper) >> 1
            p = find(data[pos:pos + length], start, pos)
            if p == -1:
                upper = length - 1
            else:
                if length > rec_l:
                    rec_p, rec_l = p, length
                lower = length + 1
        maxlen[pos] = rec_l
        mpos[pos] = rec_p
    best = [0] * (n + 2)
    choice = [0] * (n + 1)      # 0 = literal, L>=3 = match de longitud L
    for i in range(n - 1, -1, -1):
        b = 9 + best[i + 1]
        c = 0
        for length in range(3, maxlen[i] + 1):
            v = 17 + best[i + length]
            if v < b:
                b, c = v, length
        best[i] = b
        choice[i] = c
    result = bytearray()
    current = 0
    ignorable_d = ignorable_c = 0
    best_savings = 0
    while current < n:
        flags = 0
        flags_off = len(result)
        result.append(0)
        ignorable_c += 1
        for i in range(8):
            if current >= n:
                if zerosAtEnd:
                    result.append(0)
                continue
            length = choice[current]
            if length >= 3:
                disp = current - mpos[current] - posSubtract
                flags |= 1 << (7 - i)
                result.append((((length - 3) & 0xF) << 4) | ((disp >> 8) & 0xF))
                result.append(disp & 0xFF)
                current += length
                ignorable_d += length
                ignorable_c += 2
            else:
                result.append(data[current])
                current += 1
                ignorable_d += 1
                ignorable_c += 1
            savings = current - len(result)
            if savings > best_savings:
                ignorable_d = ignorable_c = 0
                best_savings = savings
        result[flags_off] = flags
    return bytes(result), ignorable_d, ignorable_c


def _save_arm9_compressed(arm9) -> bytes:
    """arm9.save(compress=True) usando el compresor óptimo."""
    from .ndspy import codeCompression
    orig = codeCompression._lzCommon.compress
    codeCompression._lzCommon.compress = _lz_compress_optimal
    try:
        return arm9.save(compress=True)
    finally:
        codeCompression._lzCommon.compress = orig


class MMZXPatchExtension(APPatchExtension):
    game = "Mega Man ZX"

    @staticmethod
    def patch_arm9(caller: APProcedurePatch, rom: bytes, cfg_file: str) -> bytes:
        """Descomprime el ARM9 (BLZ), aplica el redirect del tutorial-skip
        (siempre) y el Hu-gate (si hu_in_pool), recomprime y recoloca el
        arm9 IN-PLACE en su slot original: el resto de la imagen de 64 MiB
        queda byte-idéntico (solo cambian arm9, su tamaño en cabecera 0x2C y
        el CRC16 0x15E). ⚠️ NO usar el reempaquetado completo de ndspy
        (nds.save()): compacta la ROM a ~44 MB y desplaza el layout, y
        melonDS/BizHawk revienta con std::bad_alloc al cargarla (verificado
        en BizHawk real, exp205). ndspy vendorizado (MIT) solo para el BLZ."""
        import struct

        from . import ndspy  # noqa: F401  (paquete vendorizado)
        from .ndspy import rom as ndsrom

        cfg = caller.get_file(cfg_file)
        hu_in_pool = bool(cfg[0] & CFG_HU_IN_POOL) if cfg else False

        d = bytearray(rom)
        nds = ndsrom.NintendoDSRom(bytes(rom))
        arm9 = nds.loadArm9()

        def poke(ram, data, orig=None):
            for sec in arm9.sections:
                if sec.ramAddress <= ram < sec.ramAddress + len(sec.data):
                    off = ram - sec.ramAddress
                    cur = bytes(sec.data[off:off + len(data)])
                    if cur == data:
                        return  # idempotente
                    if orig is not None and cur != orig:
                        raise ValueError(
                            "MMZX: bytes inesperados en 0x%08X (%s, esperado "
                            "%s). ¿ROM incorrecta?" % (ram, cur.hex(), orig.hex()))
                    buf = bytearray(sec.data)
                    buf[off:off + len(data)] = data
                    sec.data = bytes(buf)
                    return
            raise ValueError("MMZX: 0x%08X fuera de las secciones ARM9" % ram)

        # 1) tutorial-skip (siempre): entry (con guarda de bytes originales)
        #    + code-cave condicional por game_state
        poke(SKIP_ENTRY_RAM, SKIP_ENTRY, SKIP_ENTRY_ORIG)
        poke(SKIP_CAVE_RAM, SKIP_CAVE)
        # 1b) guarda del dibujador OAM (siempre; robustez anti soft-lock):
        #     `beq` -> `bls` al final del bucle de sprites de FUN_02009b74
        poke(OAMLOOP_BR_RAM, OAMLOOP_BR_NEW, OAMLOOP_BR_ORIG)
        poke(OAMLOOP2_BR_RAM, OAMLOOP2_BR_NEW, OAMLOOP2_BR_ORIG)
        # 1c) posesión de biometales "solo item AP" (siempre): la victoria del
        #     jefe deja de conceder el modelo; cada copia del item progresivo
        #     pone una mitad (lista [mitad 1, mitad 2]; count vanilla = 2)
        for cnt_a, lst_a, flag1, orig1, flag2, orig2 in BIOMETAL_CAT_PATCH.values():
            poke(lst_a, flag1.to_bytes(4, "little"), orig1.to_bytes(4, "little"))
            poke(lst_a + 4, flag2.to_bytes(4, "little"), orig2.to_bytes(4, "little"))
            poke(cnt_a, bytes([BIOMETAL_CAT_COUNT]), bytes([BIOMETAL_CAT_COUNT]))
        # 1d) Life Ups / Sub Tanks: "recogido" = nibble alto (siempre)
        for ram, orig, new in PICKUP_FLAG_PATCH:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        # 1e) buzón de pickups respawneables (siempre; el cliente solo lo usa
        #     con las opciones pickup_checks_*): hook + cave + buzón a ceros
        assert len(PICKUP_MAILBOX_CAVE) <= PICKUP_MAILBOX_RAM - PICKUP_MAILBOX_CAVE_RAM
        poke(PICKUP_MAILBOX_CAVE_RAM, PICKUP_MAILBOX_CAVE,
             bytes(len(PICKUP_MAILBOX_CAVE)))
        poke(PICKUP_MAILBOX_HOOK_RAM, PICKUP_MAILBOX_HOOK_NEW, PICKUP_MAILBOX_HOOK_ORIG)
        # 1f) iconos de biometal del DATA SELECT = posesión del randomizer
        #     (siempre): H/F/L/P por 0x02104627.0-3 y X oculto si no se posee
        for ram, orig, new in DATASELECT_ICON_PATCH:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        poke(DATASELECT_CAVE_RAM, DATASELECT_CAVE, bytes(len(DATASELECT_CAVE)))
        # 1g) "Go to Transerver" en la pestaña MISSION del menú de pausa (siempre)
        assert len(MENU_WARP_CAVE_A) <= MENU_WARP_FLAGS_RAM - MENU_WARP_CAVE_A_RAM
        assert len(MENU_WARP_CAVE_B) <= SKIP_CAVE_RAM - MENU_WARP_CAVE_B_RAM
        poke(MENU_WARP_CAVE_A_RAM, MENU_WARP_CAVE_A, bytes(len(MENU_WARP_CAVE_A)))
        poke(MENU_WARP_CAVE_B_RAM, MENU_WARP_CAVE_B, bytes(len(MENU_WARP_CAVE_B)))
        for ram, orig, new in MENU_WARP_HOOKS:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        # 1h) avisos en pantalla del cliente (popup pequeño; siempre)
        assert len(NOTIFY_CAVE) <= NOTIFY_RAM - NOTIFY_CAVE_RAM
        poke(NOTIFY_CAVE_RAM, NOTIFY_CAVE, bytes(len(NOTIFY_CAVE)))
        poke(NOTIFY_HOOK_RAM, NOTIFY_HOOK_NEW, NOTIFY_HOOK_ORIG)
        # 1i) cutscenes siempre saltables con START (siempre)
        assert CUTSCENE_SKIP_CAVE_RAM + len(CUTSCENE_SKIP_CAVE) <= NOTIFY_CAVE_RAM
        poke(CUTSCENE_SKIP_CAVE_RAM, CUTSCENE_SKIP_CAVE, bytes(len(CUTSCENE_SKIP_CAVE)))
        for ram, orig, new in CUTSCENE_SKIP_PATCH:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        # 1j) iconos de item en el mundo (siempre): set AP residente + caves
        for ram, orig, new in ICON_RESIDENT_LIST_PATCH:
            poke(ram, bytes.fromhex(new), bytes.fromhex(orig))
        assert ICON_BOOT_CAVE_RAM + len(ICON_BOOT_CAVE) <= ICON_CAVES_RAM
        assert ICON_CAVES_RAM + len(ICON_CAVES) <= 0x020C8394
        poke(ICON_BOOT_CAVE_RAM, ICON_BOOT_CAVE, bytes(len(ICON_BOOT_CAVE)))
        poke(ICON_BOOT_HOOK_RAM, _thumb_bl(ICON_BOOT_HOOK_RAM, ICON_BOOT_CAVE_RAM),
             bytes.fromhex(ICON_BOOT_HOOK_ORIG))
        poke(ICON_CAVES_RAM, ICON_CAVES, bytes(len(ICON_CAVES)))
        assert PALSHARE_CAVE_RAM + len(PALSHARE_CAVE) <= 0x020C8394
        poke(PALSHARE_CAVE_RAM, PALSHARE_CAVE, bytes(len(PALSHARE_CAVE)))
        for ram, orig in ICON_ATTACH_HOOKS:
            poke(ram, _thumb_bl(ram, ICON_ATTACH_CAVE_RAM), bytes.fromhex(orig))
        for ram, orig in ICON_ANIM_HOOKS:
            poke(ram, _thumb_bl(ram, ICON_ANIM_CAVE_RAM), bytes.fromhex(orig))

        # 1j) guarda del dibujador: un set sin ranura de VRAM ya no lee la dirección 2
        #     (data abort). Bug latente del juego que el set AP destapa (exp585).
        assert SPRITEGUARD_CAVE_RAM + len(SPRITEGUARD_CAVE) <= 0x020C8394
        assert SPRITEGUARD_CAVE_RAM >= ICON_CAVES_RAM + len(ICON_CAVES)
        poke(SPRITEGUARD_CAVE_RAM, SPRITEGUARD_CAVE, bytes(len(SPRITEGUARD_CAVE)))
        for ram in SPRITEGUARD_SITES:
            poke(ram, _thumb_bl(ram, SPRITEGUARD_CAVE_RAM), SPRITEGUARD_ORIG)
        # 2) Hu-gate (opcional)
        if hu_in_pool:
            poke(HUGATE_ARRAY_RAM, HUGATE_FLAG_INDEX.to_bytes(4, "little"))
            poke(HUGATE_LISTS0_RAM, HUGATE_ARRAY_RAM.to_bytes(4, "little"),
                 HUGATE_LISTS0_ORIG)

        # recomprimir (parse óptimo: el greedy de ndspy ya no cabía en el
        # slot con el cave del buzón) y recolocar in-place en el slot original
        blob = _save_arm9_compressed(arm9)
        post = bytes(nds.arm9PostData)         # footer nitrocode (12 B)
        arm9_off = struct.unpack_from("<I", d, 0x20)[0]
        others = [struct.unpack_from("<I", d, o)[0]
                  for o in (0x30, 0x40, 0x48, 0x50, 0x68)]
        slot_end = min(x for x in others if x > arm9_off)
        if len(blob) + len(post) > slot_end - arm9_off:
            raise ValueError(
                "MMZX: el arm9 recomprimido (0x%X+%d) no cabe en su slot "
                "(0x%X)" % (len(blob), len(post), slot_end - arm9_off))
        d[arm9_off:arm9_off + len(blob)] = blob
        end = arm9_off + len(blob)
        d[end:end + len(post)] = post
        d[end + len(post):slot_end] = b"\x00" * (slot_end - end - len(post))
        struct.pack_into("<I", d, 0x2C, len(blob))

        # set AP insertado en obj_dat/obj_fnt y ambos ficheros reubicados al padding
        fnt_start = _install_icon_set(d)

        # textos de ayuda de la pestaña MISSION (NitroFS in-place, misma longitud)
        for off in MENU_WARP_TEXT_OFFS:
            o = MENU_WARP_TEXT_ROM + off
            cur = bytes(d[o:o + len(MENU_WARP_TEXT_NEW)])
            if cur == MENU_WARP_TEXT_NEW:
                continue
            if cur != MENU_WARP_TEXT_OLD:
                raise ValueError("MMZX: texto inesperado en m_sub_en.bin+0x%X (%s)" % (off, cur.hex()))
            d[o:o + len(MENU_WARP_TEXT_NEW)] = MENU_WARP_TEXT_NEW

        # sprite del Secret Disk = logo de Archipelago (128 B in-place dentro del
        # obj_fnt.bin ya reubicado: el set 58 está antes del set AP, mismo offset)
        logo_off = fnt_start + DISK_LOGO_FNT_OFF
        cur = bytes(d[logo_off:logo_off + len(DISK_LOGO_NEW)])
        if cur != DISK_LOGO_NEW:
            if cur != DISK_LOGO_OLD:
                raise ValueError("MMZX: tile del disco inesperado en ROM 0x%X (%s)" % (logo_off, cur[:8].hex()))
            d[logo_off:logo_off + len(DISK_LOGO_NEW)] = DISK_LOGO_NEW

        # CRC16 de cabecera (CRC-16/MODBUS sobre [0:0x15E])
        crc = 0xFFFF
        for b in bytes(d[:0x15E]):
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        struct.pack_into("<H", d, 0x15E, crc)
        return bytes(d)


class MMZXPatch(APProcedurePatch, APTokenMixin):
    game = "Mega Man ZX"
    hash = MMZX_US_MD5
    patch_file_ending = ".apmmzx"
    result_file_ending = ".nds"

    # 1) parche del ARM9 (BLZ): skip + Hu-gate opcional; 2) marca AP + slot.
    procedure = [
        ("patch_arm9", ["mmzx_cfg.bin"]),
        ("apply_tokens", ["token_data.bin"]),
    ]

    @classmethod
    def get_source_data(cls) -> bytes:
        with open(get_settings().mmzx_settings.rom_file, "rb") as f:
            return f.read()


def write_patch_tokens(patch: MMZXPatch, slot_name: str, seed_name: str,
                       hu_in_pool: bool = False) -> None:
    blob = bytearray(0x80)
    blob[0:len(AP_MAGIC)] = AP_MAGIC
    blob[0x08:0x0C] = WORLD_VERSION_INT.to_bytes(4, "little")
    name = slot_name.encode("utf-8")[:63]
    blob[0x10:0x10 + len(name)] = name
    seed = seed_name.encode("utf-8")[:31]
    blob[0x50:0x50 + len(seed)] = seed
    patch.write_token(APTokenTypes.WRITE, AP_MAGIC_OFFSET, bytes(blob))
    patch.write_file("token_data.bin", patch.get_token_binary())
    # config leído por patch_arm9 (antes de apply_tokens): flags de opciones.
    cfg = bytearray(4)
    cfg[0] = CFG_HU_IN_POOL if hu_in_pool else 0
    patch.write_file("mmzx_cfg.bin", bytes(cfg))
