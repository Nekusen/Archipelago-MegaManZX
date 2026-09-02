"""REGLAS DE ACCESO CURADAS — Mega Man ZX (v0.2, set PRELIMINAR).

Fichero de DATOS editado a mano (usuario + Claude), sala por sala. Lo
consume regions.py; el DSL está en logic.py: `&` (AND), `|` (OR) y
paréntesis sobre los átomos HU X ZX HX FX LX PX OX, las llaves YELLOW
GREEN RED BLUE WHITE PURPLE y las macros MODEL (cualquier modelo no-Hu),
ALL6 (los seis biometales) y ANY. Validar con
`python tools/check_logic_rules.py`.

DOCTRINA DE MOVIMIENTO (usuario, 2026-09-02) — la referencia para decidir:
- Pasos de 1 tile de alto: SOLO Hu (el único que se agacha).
- Salto: alcanza EXACTAMENTE 3 tiles; una plataforma a 4 no se sube de un
  salto. Hu NO escala paredes -> 3 tiles es su limite. Todos los demas
  modelos escalan paredes verticales (-> MODEL).
- Gaps horizontales: todos cruzan ~5 tiles (aprox). Hx alcanza mas alto
  (5-6 tiles) y gaps mayores (doble salto + dash aereo + planeo): si un
  gap grande se puede saltar, normalmente es con Hx.
- Agua: Lx se mueve libre; el resto con movilidad reducida (Hx sin planeo,
  ni doble salto ni dash aereo). Pinchos/gaps bajo el agua -> LX.
- Bloques de hielo/rompibles -> FX (punos). Techos/plataformas colgantes ->
  PX. Objetos electricos (coche de C-1, generador...) -> HX (Electric
  Spark).
- Discord: Hx para el area O; Lx para el area F (sus partes profundas: la
  mision vanilla de F se hace SIN L); endgame (M, N, O, Slither Inc HQ =
  D-4/D-5) = 6 biometales + passwords (item o flags? A INVESTIGAR).
- Misiones = cruzar la zona (implicito por alcanzabilidad) SALVO las que
  exigen Hu para hablar con NPCs (Pass The Test en C, Fight The Mavericks
  en G) o gimmicks concretos.

FUENTES: mapas interordi (work/maps_interordi/: conexiones + notas),
renders del editor (work/room_renders/: pinchos, agua, escaleras,
bloques), docs/entity_catalog.md (objetos con nombre: Electric Truck, Ice
Cube, Box, Destructible Container, Punchable Tree, switches...), guia
Steam (work/refs/steam_zx_upgrade_locations.md) y data.DOORS (con dst_pos:
donde aterriza cada puerta -> identifica sub-salas).

CONVENCION: ante la duda, SOBRE-restringir (es seguro para la
completabilidad); marcar con `# ?` lo no confirmado in-game.
"""

# Requisito para ESTAR en la sala: se aplica (AND con la llave) a TODA
# arista entrante (puertas, warps, curadas).
ROOM_RULES = {
    "o01": "HX",   # ? Discord: "you need Hx for Area O"
    "o02": "HX",   # ?
}

# Requisito extra de una transicion concreta. Clave "src->dst" (todas las
# aristas entre esas salas) o el nombre exacto de la arista en data.DOORS.
DOOR_RULES = {
    # --- Area E ---
    # E-7 -> E-8: la "Fade door" (1784,712) del corredor del Transerver de
    # E-7 solo abre con Search The Plant COMPLETADA (Hivolt vencido +
    # Report: bits 0x021045E1.4 && 0x021045FD.4). VALIDADO exp285-287
    # (agente seams, 2026-09-02). E-8 solo contiene Disk B-8.
    "e07->e08": "SEARCH_THE_PLANT",
    # --- Area A ---
    "a01->a03": "MODEL",   # ? puerta Amarilla en lo alto del muro derecho
                           # (tile y=47 vs suelo 69): hay que escalar
    "a03->h04": "FX",      # ? Fire thorns (118,55) en el pasillo a la
                           # puerta Purpura (131,55): quemarlas
    # a04->m01: + ALL6 por el SELLO de M-1 (ovl104 FUN_02194350: capas por
    # modelo, 6/6 -> capa extra; agente exp290-299; hipotesis conservadora)
    "a04->m01": "MODEL&RED&ALL6",   # ? puerta en la estructura alta (54,20): se
                               # sube por escalera y columna; y nada mas
                               # entrar en M-1 esta la puerta Roja interna
                               # (56,46) + el Orehawk (miniboss)
    # --- Area B ---
    "b03->f01": "MODEL",   # ? caverna ascendente con pinchos hasta F-1
    "b02->d01": "MODEL",   # ? el Rayfly (miniboss) esta en el tramo
                           # derecho de B-2, antes del corredor a D-1
    # --- Area H ---
    "h02->h03": "MODEL",   # ? Powmettaur (miniboss) en el foso central
    "h02->l01": "MODEL",   # ? de H-2; ambas salidas quedan detras
    # --- Area I ---
    "i02->i04": "MODEL",   # ? Diadrake (miniboss) nada mas entrar en I-4
    "i02->i05": "MODEL",   # ? Steephinx (miniboss) nada mas entrar en I-5
    # --- Area J (fondo del lago: todo bajo el agua) ---
    "j01->a04": "MODEL",   # ? subir 13 tiles bajo el agua hasta la puerta
                           # Azul (28,22): escalar paredes
    "j02->j03": "MODEL",   # ? Tentalamia (miniboss) nada mas entrar en J-3
    # --- Area K (volcan) ---
    "k02->k03": "MODEL",   # Lava Demon (miniboss) en K-2: hay que matarlo
                           # para caer al subterraneo
    "k03->k05": "MODEL",   # ? subir por el pozo de K-3 hasta la salida alta
    # --- Area D ---
    "d01->d02": "MODEL",   # ? el puente de la autopista se baja con un
                           # switch (Bridge switch (141,34)): hay que golpear
    # --- Area E ---
    "e02->e04": "MODEL",   # ? pozo de E-2: barras electricas giratorias y
    "e02->e01": "MODEL",   # ? sus botones (Electric Rod button): golpear
    "e05->e07": "MODEL",   # ? plataformas electrificadas (Electric
                           # Platform x10) antes de la salida a E-7
    # --- Area F (lago helado): Ice Cube / Box se rompen atacando ---
    # NOTA: en vanilla F se puede hacer ANTES de tener FX (misiones 5-12 a
    # eleccion), asi que el hielo de la ruta principal NO exige FX.
    "f01->f02": "MODEL",   # ? cubos/cajas de hielo tapando la puerta
    "f02->f03": "MODEL",   # ? cubos en el pasillo superior (109-111,32)
    "f03->f04": "MODEL",   # ? cubos junto a la puerta Azul (27-29,98-100)
    "f04->f05": "MODEL",   # ? filas de cubos/cajas a lo largo de F-4
    # --- Area C ---
    "c01->c02": "HU|HX",   # bloque derecho de C-1: hueco de 1 tile (Hu) o
                           # saltarlo por encima + gap grande (Hx) [usuario]
    # --- Area D ---
    # d02->d04: solo la Green Key de la tabla. D-4/D-5 NO consultan misiones
    # ni biometales (agente exp290-299): el requisito "6 biometales" del final
    # va en la VICTORIA (regions.py) y en la entrada de M (sello de M-1).
}

# Sub-regiones dentro de una sala. {"parent": sala, "req": requisito para
# entrar desde la sala, "back": requisito para volver (default ANY),
# "locations": [locations fisicas que se mueven a la sub-region]}.
SUBREGIONS = {
    # A-1: dos cuevas (sub-salas) por puertas internas: (54,70)->(418,22) y
    # (135,56)->(450,22). Disk E-1 (477,21) esta en la segunda, cuya puerta
    # tiene "Fire thorns" (135,55) delante -> quemarlas con FX.
    "a01/cueva-e1": {"parent": "a01", "req": "FX",   # ?
                     "locations": ["A-1: Disk E-1"]},
    # A-2: el tramo inferior (llegada desde A-1) queda separado del resto
    # por el miniboss Giga Aspis: hay que matarlo para pasar (Hu no ataca).
    "a02/sur": {"parent": "a02", "req": "MODEL", "back": "MODEL",   # ?
                "doors_in": ["a01->a02"], "doors_out": ["a02->a01"]},
    # E-7: sala del jefe Hivolt. Desde E-5 se llega al lado oeste; el pad
    # de Transerver y la salida a E-8/I-1 estan al otro lado del jefe.
    "e07/oeste": {"parent": "e07", "req": "MODEL", "back": "MODEL",
                  "doors_in": ["e05->e07"], "doors_out": ["e07->e05"]},
    # F-5: sala del jefe Lurerre; el pad de Transerver esta al otro lado.
    "f05/oeste": {"parent": "f05", "req": "MODEL", "back": "MODEL",
                  "doors_in": ["f04->f05"], "doors_out": ["f05->f04"]},
    # G-5: Fistleo al fondo; el pad de Transerver queda detras del jefe
    # (la parte principal, con E-32 y la sub-sala de B-11, es la entrada).
    "g05/pad": {"parent": "g05", "req": "MODEL", "back": "MODEL",
                "doors_in": ["z01->g05"], "doors_out": ["g05->z01"]},
    # H-4: Purprill en el pasillo de entrada desde H-3; la torre (B-7, sala
    # DATA, llegada desde A-3 por la puerta Purpura) queda al otro lado.
    "h04/oeste": {"parent": "h04", "req": "MODEL", "back": "MODEL",
                  "doors_in": ["h03->h04"], "doors_out": ["h04->h03"]},
    # I-3: Hurricaune en el pasillo inferior; el pad esta al fondo derecho.
    "i03/pad": {"parent": "i03", "req": "MODEL", "back": "MODEL",
                "doors_in": ["z01->i03"], "doors_out": ["i03->z01"]},
    # J-5: Leganchor nada mas entrar desde J-3; B-16 y la salida a J-4
    # quedan detras del jefe.
    "j05/entrada": {"parent": "j05", "req": "MODEL", "back": "MODEL",
                    "doors_in": ["j03->j05"], "doors_out": ["j05->j03"]},
    # K-1: el SUBTERRANEO (Sub Tank, control de lava, puerta a K-5) solo se
    # alcanza cayendo a K-2 -> K-3 -> subiendo K-5; desde la superficie no
    # hay paso directo (FALSE). De vuelta a la superficie hay un ascensor.
    "k01/subterraneo": {"parent": "k01", "req": "FALSE", "back": "ANY",
                        "doors_in": ["k05->k01"], "doors_out": ["k01->k05"],
                        "locations": ["K-1: Sub Tank"]},
    # K-3: se llega ARRIBA (caida desde K-2; salida a K-5 por el pasillo
    # superior); el fondo (M-9, E-43, llegada desde K-4) se alcanza cayendo
    # por el pozo y se vuelve a subir escalando.
    "k03/fondo": {"parent": "k03", "req": "ANY", "back": "MODEL",   # ?
                  "doors_in": ["k04->k03"],
                  "locations": ["K-3: Disk M-9", "K-3: Disk E-43"]},
    # K-4: Flammole al fondo derecho; el pad de Transerver queda detras.
    "k04/pad": {"parent": "k04", "req": "MODEL", "back": "MODEL",
                "doors_in": ["z01->k04"], "doors_out": ["k04->z01"]},
    # L-4: Protectos al fondo; el pad queda detras del jefe.
    "l04/pad": {"parent": "l04", "req": "MODEL", "back": "MODEL",
                "doors_in": ["z01->l04"], "doors_out": ["l04->z01"]},
    # M-3: Pandora en el pasillo inferior; el pad (y el corredor a N-1)
    # quedan detras.
    "m03/pad": {"parent": "m03", "req": "MODEL", "back": "MODEL",
                "doors_in": ["z01->m03"], "doors_out": ["m03->z01"]},
    # O-2: el pad esta a mitad de sala; Tentalamia (miniboss) y luego
    # Pandora & Prometheus bloquean el tramo este con B-14.
    "o02/este": {"parent": "o02", "req": "MODEL", "back": "MODEL",
                 "locations": ["O-2: Disk B-14"]},
}

# Locations FISICAS de salas con puerta interna con llave a las que esa
# llave NO afecta (analizadas): quedan fuera de la regla coarse.
INTERNAL_GATE_EXEMPT = {
    "K-4: Disk E-26",   # K-4: extremo oeste del pasillo central, sin puerta Blanca
}

# Requisito adicional por location (AND con el de su sala/sub-region).
LOCATION_RULES = {
    # --- A-1 [usuario]: O-9 esta en el camino central de 1 tile ---
    "A-1: Disk O-9": "HU",
    # --- Area A (interordi) ---
    "A-4: Disk E-20": "MODEL",     # ? A-4: arriba a la derecha de la estructura
                              # alta (escalera + columna vertical)
    # --- Area B (interordi) ---
    "B-1: Disk E-24": "MODEL",     # ? B-1: repisa elevada al fondo derecho
    "B-2: Disk E-17": "MODEL",     # ? B-2: en lo alto de un pilar (tile y=29)
    "B-2: Disk B-1": "MODEL",      # ? B-2: cima de la estructura derecha (y=28)
    "B-4: Disk E-11": "MODEL",     # ? B-4: estructura alta arriba a la derecha
    "Quest - Purify The Lakes": "LX&MODEL",  # ? B-4: 5 Pure Water Tanks en
                                             # el lago (bajo el agua; romperlos)
    # --- Area C (interordi) ---
    "C-3: Disk E-49": "MODEL",     # ? C-3: repisa alta a la izquierda (y=34)
    # --- Area E (interordi) ---
    "E-4: Disk E-8": "MODEL",      # ? E-4: arriba a la derecha, por la ruta de
                              # los engranajes hacia E-3 (nota interordi)
    "E-5: Disk E-37": "MODEL",     # ? E-5: pasadas las plataformas electricas
    # E-4 (Sub Tank) ya cubierto por Steam; E-21 abajo por escalera; M-5
    # arriba de la escalera larga de E-5; B-8 en el suelo de E-8.
    # --- Area F (interordi + catalogo) ---
    "F-1: Disk E-39": "MODEL",     # ? F-1: repisa en la cueva izquierda (y=34)
    "F-2: Disk E-15": "MODEL",     # ? F-2: laberinto inferior (cubos (75,54-62))
    "F-2: Disk E-44": "LX",        # ? F-2: zona baja entre filas de pinchos
                              # bajo el agua (Steam: pinchos "barely
                              # underwater" en F-2)
    "F-3: Disk E-48": "MODEL",     # ? F-3: arriba del todo tras una fila de
                              # cubos (37-45,30) y cajas (46-48,33-35)
    "F-3: Disk E-2": "MODEL",      # ? F-3: el disco esta ENTRE cubos (122-124,39)
    "F-4: Disk B-15": "LX",        # F-4: "Use Model Lx's charged attack to make
                              # a platform and get this disk" (interordi)
    "F-4: Disk E-45": "MODEL",     # ? F-4: cubos pegados (92-94,32)
    # --- Area G (interordi): los fuegos se pueden atravesar (G puede ser
    #     la primera mision vanilla); Hx los apaga (nota interordi) ---
    "G-5: Disk B-11": "HX",        # ? G-5: sub-sala (puerta (112,43)) tapada
                              # por fuego; interordi apunta con flecha
    "Quest - Find The Boy": "HU",   # escondite con los ninos (hablar)
    # E-38 en la calle de G-1; E-16 arriba del edificio (rampas); E-9 en
    # G-3; E-32 al pie de la cuesta de G-5 -> sin requisito.
    # --- Area H (interordi): E-10/M-8 en H-3 y B-7 en la torre de H-4
    #     se alcanzan por escaleras -> sin requisito propio ---
    # --- Area I (interordi) ---
    "I-2: Disk E-33": "HX",        # I-2: "Use Model Hx hover ability to get
                              # across the spikes and get the disk"
    "I-4: Disk M-1": "HX",         # I-4: "Use Model Hx's electric spark to
    "I-4: Disk E-14": "HX",        # I-4:  power the platforms and get the disks"
    "I-5: Disk M-6": "MODEL",      # ? I-5: en lo alto del tronco de un arbol
    "I-5: Disk E-13": "MODEL",     # ? I-5: estructura derecha (y=32), escalera
    # E-3 (I-1) en sub-sala por puerta del pasillo inferior; E-34 (I-2),
    # B-9 (I-3), E-23 (I-5) a pie de suelo -> sin requisito.
    # --- Area J (interordi): fondo del lago ---
    "J-2: Disk E-7": "LX",         # ? J-2: hueco alto con fila de pinchos bajo
                              # el agua (1360-1450,85)
    "J-3: Disk E-36": "MODEL",     # ? J-3: en lo alto de la estructura derecha
    # Life Up J-1 (Steam, LX) ya cubierto; M-7 (J-3) en un hueco al que se
    # cae; B-16 (J-5) tras Leganchor por escalera -> sin requisito propio.
    # --- Area K (interordi + Steam) ---
    "K-1: Disk E-22": "MODEL",     # ? K-1: estructura alta a la derecha (y=38)
    "K-3: Disk E-35": "MODEL",     # ? K-3: repisa a media altura del pozo
    "K-4: Disk B-12": "WHITE",     # K-4: tras la puerta interna Blanca (169,71)
                              # -> aterriza en (78,117), junto a B-12
    # E-26 (K-4, pasillo central) y E-25 (K-5, escalera) sin requisito.
    # --- Area L (interordi): almacenes con contenedores (Rayfly) ---
    "L-1: Disk E-18": "HX",        # ? L-1: plataforma flotante muy alta (y=33
                              # con suelo en 47); nada que escalar
    "L-2: Disk E-41": "HX",        # ? L-2: idem (y=29)
    # E-5 (L-3) y B-13 (L-4) a pie de suelo -> sin requisito propio.
    "Quest - Deliver The Aid Kit": "MODEL",   # destruir contenedores en L
    # --- Area M (interordi) ---
    "M-1: Disk M-2": "MODEL",      # ? M-1: sub-sala por la puerta (282,46);
                              # el disco 5 tiles por encima del aterrizaje
    "M-1: Disk E-50": "FX",        # M-1: "Use Model Fx Buster Edit to hit this
                              # switch" (sub-sala por la puerta (316,30))
    # B-10 (M-3) a pie de suelo antes de Pandora -> sin requisito.
    # --- Area N (interordi) ---
    "N-1: Disk B-2": "MODEL",      # ? N-1: zona superior con plataformas que
                              # desaparecen y pinchos (gate Blanco coarse
                              # de la sala tambien aplica: sobre-estricto)
    # --- Area O (interordi): HX por ROOM_RULES ---
    # E-42 en la calzada y M-3 debajo (se cae) -> sin requisito propio.
    # --- Area X (Guardian base): todo conectado por ascensor/puertas;
    #     los discos O-* de X-1/X-2/X-3 sin requisito ---
    # --- Quests con objeto en zonas dificiles ---
    "Quest - Find The Pearl": "LX",       # ? F-2: la Cold Pearl esta bajo
                                          # el agua del lago
    # --- Area D (interordi) ---
    # D-1: E-12 y el Life Up estan bajo la carretera (se cae por los
    # huecos); E-19/E-40/O-12/B-4 en la calzada; M-4 bajo la autopista de
    # D-2 (se cae); B-5/B-6 en los pasillos de la torre -> sin requisito.
    # --- Combate: Hu NO ataca. Jefes, minibosses, botones y switches
    #     exigen un modelo. Toda mision/biometal implica pelear. ---
    "Obtain Biometal H": "MODEL",
    "Obtain Biometal L": "MODEL",
    "Obtain Biometal F": "MODEL",
    "Obtain Biometal P": "MODEL",
    "Mission - Locate Giro": "MODEL",
    "Mission - Troop Reinforcement": "MODEL",
    "Mission - Search The Plant": "MODEL",
    "Mission - Find The Survivors": "MODEL",
    "Mission - Secure The Biometal": "MODEL",
    "Mission - Save The People": "MODEL",
    "Mission - Recover The Disk": "MODEL",
    "Mission - Attack The Excavators": "MODEL",
    "Mission - Protect The Lab": "MODEL",
    "Mission - Stop The Dig": "MODEL",
    "Mission - Repel The Army": "MODEL",
    "Mission - Protect Hq": "MODEL",
    "Mission - Destroy Model W": "MODEL",
    # --- Guia Steam (Life Ups / Sub Tanks) ---
    "D-1: Life Up": "MODEL",          # "any transformation"
    "F-2: Life Up": "HX&FX",          # bloques de hielo + salto alto
    "I-5: Life Up": "HX",             # tornados (ambas mitades)
    "J-1: Life Up": "LX",             # nadar entre pinchos
    "A-2: Sub Tank": "HX",            # dash aereo hasta la plataforma
    "E-4: Sub Tank": "MODEL",         # "any transformation"
    "K-1: Sub Tank": "HX&FX&LX&PX",   # el mas largo (techos, bloques,
                                            # boton oculto, nado)
    # --- Misiones que exigen forma Hu para hablar con NPCs [usuario] ---
    "Mission - Pass The Test": "HU&MODEL",        # ? (hablar + superar)
    "Mission - Fight The Mavericks": "HU&MODEL",  # hablar con NPCs + pelear
}
