"""Opciones YAML del mundo Mega Man ZX. Decisiones en docs/DISENO_CHECKS.md."""

from dataclasses import dataclass

from Options import (Choice, DeathLink, DefaultOnToggle, PerGameCommonOptions,
                     StartInventoryPool, Toggle)


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


@dataclass
class MMZXOptions(PerGameCommonOptions):
    character: Character
    goal: Goal
    starting_model: StartingModel
    starting_transerver: StartingTranserver
    hu_in_pool: HuInPool
    level4_victories: Level4Victories
    submission_checks: SubmissionChecks
    mission_auto_accept: MissionAutoAccept
    death_link: DeathLink
    start_inventory_from_pool: StartInventoryPool
