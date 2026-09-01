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
    "c01->c02": "HU|HX",   # bloque derecho de C-1: hueco de 1 tile (Hu) o
                           # saltarlo por encima + gap grande (Hx) [usuario]
    "d02->d04": "ALL6",    # ? puerta de Slither Inc. HQ (passwords / 6
                           # biometales en vanilla; RE pendiente del check)
}

# Sub-regiones dentro de una sala. {"parent": sala, "req": requisito para
# entrar desde la sala, "back": requisito para volver (default ANY),
# "locations": [locations fisicas que se mueven a la sub-region]}.
SUBREGIONS = {
    # A-1: las cuevas de arriba a la derecha se entran por las puertas
    # internas (864,1120)->(6688,352) y (2160,896)->(7200,352); la segunda
    # alberga Disk E-1 + refills. Requisito de acceso A CONFIRMAR.
    "a01/cuevas": {"parent": "a01", "req": "MODEL",   # ? (llega Hu?)
                   "locations": ["Disk E-1"]},
}

# Requisito adicional por location (AND con el de su sala/sub-region).
LOCATION_RULES = {
    # --- A-1 [usuario]: O-9 esta en el camino central de 1 tile ---
    "Disk O-9": "HU",
    # --- Guia Steam (Life Ups / Sub Tanks) ---
    "Life Up - Area D01": "MODEL",          # "any transformation"
    "Life Up - Area F02": "HX&FX",          # bloques de hielo + salto alto
    "Life Up - Area I05": "HX",             # tornados (ambas mitades)
    "Life Up - Area J01": "LX",             # nadar entre pinchos
    "Sub Tank - Area A02": "HX",            # dash aereo hasta la plataforma
    "Sub Tank - Area E04": "MODEL",         # "any transformation"
    "Sub Tank - Area K01": "HX&FX&LX&PX",   # el mas largo (techos, bloques,
                                            # boton oculto, nado)
    # --- Misiones que exigen forma Hu para hablar con NPCs [usuario] ---
    "Mission - Pass The Test": "HU",
    "Mission - Fight The Mavericks": "HU",
}
