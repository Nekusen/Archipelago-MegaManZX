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
    (derrotarlos con rango máximo)."""
    display_name = "Level 4 Victory Checks"


class SubmissionChecks(Toggle):
    """Incluye las submisiones de NPCs (quests) como checks. En v0.1 su
    detección es PROVISIONAL (pendiente de validar la bandera de
    completada)."""
    display_name = "Submission Checks"
    default = 1


@dataclass
class MMZXOptions(PerGameCommonOptions):
    character: Character
    goal: Goal
    level4_victories: Level4Victories
    submission_checks: SubmissionChecks
    death_link: DeathLink
    start_inventory_from_pool: StartInventoryPool
