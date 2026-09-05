"""Opciones YAML del mundo Mega Man ZX. Decisiones en docs/DISENO_CHECKS.md."""

from dataclasses import dataclass

from Options import (Choice, DeathLink, DefaultOnToggle, OptionDict,
                     PerGameCommonOptions, StartInventoryPool, Toggle)


class Character(Choice):
    """Personaje jugable: Vent o Aile (misma ROM, cambia sprites/diálogo)."""
    display_name = "Character"
    option_vent = 0
    option_aile = 1
    default = 0


class Goal(Choice):
    """Objetivo de la seed. v0.1: derrotar a Serpent."""
    display_name = "Goal"
    option_defeat_serpent = 0
    default = 0


class Level4Victories(Toggle):
    """Añade como checks las 'Level 4 Victory' de cada Pseudoroid
    (derrotarlos con rango máximo). ⚠️ v0.1: aún SIN EFECTO — la
    detección de Level 4 no está implementada todavía (llega en una
    actualización)."""
    display_name = "Level 4 Victory Checks"


class SubmissionChecks(Toggle):
    """Incluye las submisiones de NPCs (quests) como checks. ⚠️ v0.1: aún
    SIN EFECTO — la detección de 'quest completada' no está validada, así
    que las quests se excluyen del seed por ahora (se añadirán cuando su
    detección esté lista, sin romper seeds antiguas)."""
    display_name = "Submission Checks"
    default = 0


class StartingModel(Choice):
    """Modelo con el que empiezas (v0.2, tutorial-skip). El arranque salta el
    tutorial y te deja en el Transerver con este modelo (o ninguno = forma
    humana, sin biometal, hasta que encuentres uno). El modelo elegido se
    pre-concede (start inventory) y no ocupa sitio en el pool; Model X se
    convierte en item encontrable salvo que empieces con él. Puedes poner
    'random' en el YAML para uno aleatorio.
    ⚠️ Hasta que el parche de ROM del arranque esté listo, el cliente aplica
    el modelo al llegar al hub post-tutorial."""
    display_name = "Starting Model"
    option_model_x = 0
    option_none = 1
    option_model_zx = 2
    option_model_hx = 3
    option_model_fx = 4
    option_model_lx = 5
    option_model_px = 6
    option_model_ox = 7
    option_model_hu = 8   # solo con hu_in_pool ON (si no, = none)
    default = 0


class LogicDifficulty(Choice):
    """Nivel de la lógica de acceso (worlds/mmzx/logic/logic.json).
    normal: solo rutas seguras. expert: además las alternativas marcadas
    como expert en el editor (trucos, damage boost, saltos justos); es
    ACUMULATIVO, todo lo válido en normal sigue valiendo en expert."""
    display_name = "Logic Difficulty"
    option_normal = 0
    option_expert = 1
    default = 0


class BossLogic(OptionDict):
    """(v0.3) Dificultad de los jefes A TU GUSTO: qué tienes que llevar para
    que la LÓGICA te considere capaz de vencer a cada jefe de la historia.

    Es una restricción solo de lógica — en el juego puedes pelear con lo que
    quieras. Lo que garantiza es que la seed nunca te OBLIGUE a pasar por un
    jefe para el que no tienes lo que tú mismo has pedido: ni a cruzar su
    arena hacia el otro lado, ni a coger lo que hay dentro, ni a completar su
    misión, ni a obtener su biometal (los biometales salen de dos jefes: si
    solo puedes con uno, la lógica cuenta ese camino y no el otro). Los ocho
    Pseudoroids se pelean DOS veces (su área y el boss rush de la torre de
    D-4, que el juego OBLIGA a superar para pasar a D-5): el requisito se
    aplica a los dos encuentros, así que llegar a Serpent exige poder con los
    ocho.

    Jefes: Rayfly (B-2), Model Z (D-2), Hivolt (E-7), Lurerre (F-5),
    Fistleo (G-5), Purprill (H-4), Hurricaune (I-3), Leganchor (J-5),
    Flammole (K-4), Protectos (L-4), Prometheus (X-3), Pandora (M-3),
    Prometheus & Pandora (O-2), Serpent (D-5), Omega Zero (N-1). También vale
    el código de la sala como clave ("E-7"). Los que no pongas no piden nada.
    (Giga Aspis, el jefe del tutorial, no está: el randomizer salta el
    tutorial entero y no se pelea nunca.)

    Requisitos: modelos (X ZX HX FX LX PX OX; "HX2" o "Model HX (full)" = las
    dos mitades del progresivo, o sea carga de nivel 2), MODEL (cualquiera),
    ALL6 (los seis biometales), "Life Up x2" (o LIFEUP>=2), "Sub Tank x1" (o
    SUBTANK>=1), chips de ITEM B por su nombre ("Absorber Chip") y Card Keys.
    Se combinan con & (Y) y | (O) y paréntesis. Un chip exigido pasa de
    `useful` a progresión automáticamente.

    Ejemplo:
      boss_logic:
        Hivolt: "HX & Life Up x2"
        Flammole: "Model FX (full) & Absorber Chip"
        Serpent: "ALL6 & Sub Tank x2 & Life Up x4"
        Omega Zero: "OX | (ALL6 & SUBTANK>=2)"
    """
    display_name = "Boss Logic"
    default = {}


class HuInPool(Toggle):
    """(v0.2 EXPERIMENTAL) Convierte la forma humana (Hu) en un item de la
    pool en vez de estar siempre disponible. Aplica un parche de ROM que
    'gatea' Hu tras un flag (como los biometales). ⚠️ RIESGO DE SOFTLOCK:
    algunas misiones EXIGEN forma humana (p.ej. Pass The Test) — sin la
    lógica de regiones cableada, puedes quedar atascado si te toca ese
    contenido antes de recibir Model Hu. Úsalo solo para pruebas."""
    display_name = "Human Form (Hu) In Pool"
    default = 0


class StartingTranserver(Choice):
    """Transerver donde empiezas (v0.2). Por ahora solo el hub de la base
    Guardian (el punto post-tutorial natural); se añadirán Transervers de
    área cuando la lógica de regiones esté cableada."""
    display_name = "Starting Transerver"
    option_guardian_hub = 0
    default = 0


class MissionAutoAccept(DefaultOnToggle):
    """Modo 'open world' de misiones (v0.2). Con ON, el cliente ACEPTA
    automáticamente la misión de la zona en la que entras (sin pasar por el
    Transerver), para poder hacerlas en cualquier orden. Las misiones que el
    juego lanza solas por historia (Model ZX en la base Guardian, y Protect
    HQ) se disparan igual, no se auto-aceptan. Con OFF, aceptación manual en
    el Transerver (vanilla) — ⚠️ la lógica de regiones ASUME auto-accept: en
    manual, la disponibilidad de misiones sigue la secuencia de historia del
    juego (N→N+4), que la lógica no modela."""
    display_name = "Mission Auto-Accept (Open World)"


class PickupChecks1Up(Toggle):
    """(v0.2) Los 1-Up colocados en el mapa (7) cuentan como checks: la
    PRIMERA vez que recoges cada uno envía su location; después siguen
    reapareciendo y dando vida como siempre. Añade 7 locations (y otros
    tantos items de relleno al pool)."""
    display_name = "Pickup Checks: 1-Ups"
    default = 0


class PickupChecksEnergy(Toggle):
    """(v0.2) Las cápsulas de energía (Energy Capsule L/XL) colocadas en el
    mapa (45) cuentan como checks: la PRIMERA recogida de cada una envía su
    location; después siguen reapareciendo y curando. Añade 45 locations."""
    display_name = "Pickup Checks: Energy Capsules"
    default = 0


class PickupChecksWeapon(Toggle):
    """(v0.2) Las recargas de arma (Weapon Energy L) colocadas en el mapa
    (25) cuentan como checks: la PRIMERA recogida de cada una envía su
    location; después siguen reapareciendo. Añade 25 locations."""
    display_name = "Pickup Checks: Weapon Energy"
    default = 0


class PickupChecksCrystals(Toggle):
    """(v0.2) Los E-Crystal L colocados en el mapa (56) cuentan como checks:
    la PRIMERA recogida de cada uno envía su location; después siguen
    reapareciendo y dando cristales. Añade 56 locations."""
    display_name = "Pickup Checks: E-Crystals"
    default = 0


class NotifyReceived(Choice):
    """Avisos en pantalla (popup pequeño del juego) al RECIBIR un item:
    qué clases se muestran. `off` ninguno; `progression` solo progresión;
    `useful` progresión + útiles; `all` también el relleno (E-Crystals,
    1-Up). Se puede cambiar en la partida con `/mmzx_notify`."""
    display_name = "On-screen Notifications: Received Items"
    option_off = 0
    option_progression = 1
    option_useful = 2
    option_all = 3
    default = 2


class NotifySent(Choice):
    """Avisos en pantalla al ENVIAR un item a otro jugador (check tuyo con
    un item ajeno): qué clases se muestran (`off`, `progression`, `useful`,
    `all`). Se puede cambiar en la partida con `/mmzx_notify`."""
    display_name = "On-screen Notifications: Sent Items"
    option_off = 0
    option_progression = 1
    option_useful = 2
    option_all = 3
    default = 2


@dataclass
class MMZXOptions(PerGameCommonOptions):
    character: Character
    goal: Goal
    starting_model: StartingModel
    starting_transerver: StartingTranserver
    hu_in_pool: HuInPool
    logic_difficulty: LogicDifficulty
    boss_logic: BossLogic
    level4_victories: Level4Victories
    submission_checks: SubmissionChecks
    mission_auto_accept: MissionAutoAccept
    pickup_checks_1up: PickupChecks1Up
    pickup_checks_energy: PickupChecksEnergy
    pickup_checks_weapon: PickupChecksWeapon
    pickup_checks_crystals: PickupChecksCrystals
    notify_received: NotifyReceived
    notify_sent: NotifySent
    death_link: DeathLink
    start_inventory_from_pool: StartInventoryPool
