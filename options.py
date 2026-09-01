"""Opciones YAML del mundo Mega Man ZX. Decisiones en docs/DISENO_CHECKS.md."""

from dataclasses import dataclass

from Options import Choice, Toggle, DeathLink, PerGameCommonOptions, StartInventoryPool


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


class MissionAutoAccept(Toggle):
    """Modo 'open world' de misiones (v0.2, EXPERIMENTAL). Con ON, el cliente
    ACEPTA automáticamente la misión de la zona en la que entras (sin pasar
    por el Transerver), para poder hacerlas en cualquier orden. Las misiones
    que el juego lanza solas por historia (Model ZX en la base Guardian, y
    Protect HQ) se disparan igual, no se auto-aceptan. Con OFF, aceptación
    manual en el Transerver (vanilla)."""
    display_name = "Mission Auto-Accept (Open World)"
    default = 0


@dataclass
class MMZXOptions(PerGameCommonOptions):
    character: Character
    goal: Goal
    level4_victories: Level4Victories
    submission_checks: SubmissionChecks
    mission_auto_accept: MissionAutoAccept
    death_link: DeathLink
    start_inventory_from_pool: StartInventoryPool
