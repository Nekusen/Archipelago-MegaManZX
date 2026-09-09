"""Skip del BOSS RUSH de la torre de Slither Inc. (D-4) — opción QoL
`skip_boss_rush`. Lógica PURA (sin dependencias de Archipelago) compartida por
el cliente (client.py::_boss_rush_skip_tick) y por los experimentos que la
validan en el emulador (work/experiments/618-619).

Cómo funciona el juego (RE 2026-09-09, exp614-618; docs/functions.md §D-4):

- "Pseudoroid X vencido en el boss rush" = 8 flags del bloque de partida:
  0x021045FF.4-7 (teletransportador IZQUIERDO de cada par: Hivolt, Lurerre,
  Fistleo, Purprill) y 0x02104600.0-3 (DERECHO: Hurricaune, Leganchor,
  Flammole, Protectos). Con el flag puesto el teletransportador queda INERTE
  (UP no hace nada), ovl061 pinta su cápsula como usada AL CARGAR la sala
  (0x02194A84 → FUN_02013328) y desbloquea las puertas de la sala del par
  (0x02194C84 pone/quita 0x0210462A.7 cada frame según los DOS flags).
- El ascensor es UNA sola entidad (0x02194DEC) que se coloca según la
  "etapa" u8 0x0212FBA1: 0 abajo del hueco 1, 1 parada 1 (y=2440), 2 subiendo
  a 2440, 3 arriba (520), 4 subiendo a 520, 5 abajo del hueco 2 (2688,4360),
  6 parada 1 (2824), 7 subiendo a 2824, 8 arriba (904), 9 subiendo a 904. Las
  etapas fijas SALTAN de golpe a su posición. La etapa la conduce el handler
  de historia de la misión 16 (FUN_0201fc90) por estado + flags + rectángulos:
  con un par puesto ANTES de tiempo, el ascensor salta a la parada y el
  jugador cae al pozo (exp614: con los 8 flags de golpe, etapa 8 = ascensor
  aparcado arriba del hueco 2 y el jugador muere en el hueco 1).
- Por eso el par k se pone SOLO cuando el ascensor ya está parado en la
  parada del par con el jugador encima (o el jugador dentro de la sala del
  par). Al ponerlo, el handler encadena solo la cinemática siguiente y el
  ascensor sigue subiendo (exp615/618).
- Checkpoint: las puertas de fundido actualizan la posición de reaparición
  (0x0216047C) pero NO la copia del handler (0x02160554): una muerte
  reaparecía con el handler desfasado y el ascensor muerto (exp617). Al poner
  un par se hace el COMMIT completo como FUN_0201b384 (posición → bloque
  persistente del jugador → descriptor; bloque vivo → canónica; historia →
  cola 1), con la posición SIN fracción y solo con el ascensor ya llegado (un
  spawn dentro de la plataforma expulsa al jugador fuera del mapa, exp618a).
- Estética: el juego solo repinta las cápsulas al cargar D-4, así que el
  cliente replica FUN_02013328: copia el parche 5×6 de metatiles (u16) de
  cada cápsula desde ovl061 al mapa de metatiles de la sala (0x02112B78,
  stride 192 en D-4) y marca el mapa sucio (u16 0x0212DB54+0x28 = 1).
"""

SUBAREA = 18                     # D-4 (torre)
HANDLER_ID = 16                  # misión "Destroy Model W"
FLAG_LEFT = 0x021045FF           # bit 4+k = par k, teletransportador izquierdo
FLAG_RIGHT = 0x02104600          # bit k   = par k, teletransportador derecho
STAGE = 0x0212FBA1               # etapa del ascensor (u8)

TILEMAP = 0x02112B78             # mapa de metatiles de la sala cargada (u16 por metatile)
TILEMAP_STRIDE = 192             # D-4: 12 pantallas × 16 metatiles
TILEMAP_DIRTY = 0x0212DB54 + 0x28   # u16 = 1 → el motor vuelve a subir el mapa visible
# (tx, ty, parche en ovl061) de cada cápsula: [par] = (izquierda, derecha).
# Parche = u16 ancho (5), s16 alto (6), 5×6 u16 (64 B).
PATCHES = {
    0: ((0x10, 0x0E, 0x02195A58), (0x1B, 0x0E, 0x02195B98)),
    1: ((0x30, 0x0E, 0x02195B18), (0x3B, 0x0E, 0x02195B58)),
    2: ((0x10, 0x26, 0x02195A18), (0x1B, 0x26, 0x021959D8)),
    3: ((0x30, 0x26, 0x02195AD8), (0x3B, 0x26, 0x02195A98)),
}
PATCH_W, PATCH_H = 5, 6

SHAFT1 = (1536, 1792)            # hueco del ascensor 1 (x)
SHAFT2 = (2560, 2816)            # hueco del ascensor 2 (x)
# par -> (hueco, y máxima del jugador DE PIE en la parada (+1), estado del
# handler, etapa del ascensor). El jugador de pie sobre el ascensor queda a
# y = parada + 23 (2463, 543, 2847, 927).
STOPS = {
    0: (SHAFT1, 2464, 2, 2),
    1: (SHAFT1, 544, 4, 4),
    2: (SHAFT2, 2848, 5, 7),
    3: (SHAFT2, 928, 7, 9),
}
# salas de cada par (x0, x1, y0, y1): A Hivolt/Hurricaune, B Lurerre/Leganchor,
# C Fistleo/Flammole, D Purprill/Protectos.
ROOMS = {
    0: (248, 760, 200, 420),
    1: (760, 1040, 200, 420),
    2: (248, 760, 600, 800),
    3: (760, 1040, 600, 800),
}
PAIR_NAMES = {0: "Hivolt/Hurricaune", 1: "Lurerre/Leganchor",
              2: "Fistleo/Flammole", 3: "Purprill/Protectos"}


def pair_set(flag_left: int, flag_right: int, k: int) -> bool:
    return bool((flag_left >> (4 + k)) & 1 and (flag_right >> k) & 1)


def pairs_to_set(x: int, y: int, hstate: int, stage: int,
                 flag_left: int, flag_right: int) -> list:
    """Pares que hay que marcar como vencidos AHORA (jugador en D-4, en juego,
    handler de la misión 16 instalado y sin cutscene en curso). Ordenados."""
    out = []
    for k in range(4):
        if pair_set(flag_left, flag_right, k):
            continue
        x0, x1, y0, y1 = ROOMS[k]
        if x0 <= x < x1 and y0 <= y < y1:
            out.append(k)
            continue
        (sx0, sx1), ymax, state, stg = STOPS[k]
        if sx0 <= x < sx1 and y <= ymax and hstate == state and stage == stg:
            out.append(k)
    return out


def apply_pairs(flag_left: int, flag_right: int, pairs) -> tuple:
    for k in pairs:
        flag_left |= 1 << (4 + k)
        flag_right |= 1 << k
    return flag_left & 0xFF, flag_right & 0xFF


def paint_writes(k: int, patch_bytes) -> list:
    """Escrituras [(dirección, bytes)] que pintan las dos cápsulas del par k
    como usadas. `patch_bytes(addr)` devuelve los 64 B del parche en `addr`
    (están en RAM mientras D-4 está cargada). Replica FUN_02013328."""
    out = []
    for tx, ty, src in PATCHES[k]:
        data = patch_bytes(src)
        w = int.from_bytes(data[0:2], "little")
        h = int.from_bytes(data[2:4], "little", signed=True)
        if w != PATCH_W or h != PATCH_H:      # overlay ajeno cargado: no tocar
            return []
        for row in range(h):
            out.append((TILEMAP + (tx + (ty + row) * TILEMAP_STRIDE) * 2,
                        data[4 + row * w * 2: 4 + (row + 1) * w * 2]))
    out.append((TILEMAP_DIRTY, (1).to_bytes(2, "little")))
    return out
