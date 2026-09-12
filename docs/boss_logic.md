# The boss_logic option

`boss_logic` lets you tell the logic what you want to be carrying before it considers a story boss beatable. It only
restricts the logic: in the game you can fight with whatever you have. What it guarantees is that the seed never forces
you through a boss you are not equipped for by your own standard: not crossing its arena, not collecting what lies
inside, not completing its mission, not obtaining its biometal.

The eight Pseudoroids are fought twice, in their own area and in the boss rush of the D-4 tower, and the requirement
applies to both encounters. Reaching Serpent therefore means being able to handle all eight, unless `skip_boss_rush`
is on. Bosses you leave out ask for nothing.

## Bosses

Use the boss name or its room code as the key.

| Boss | Room | Notes |
|---|---|---|
| Rayfly | B-2 | |
| Model Z | D-2 | |
| Hivolt | E-7 | Pseudoroid, Model HX |
| Lurerre | F-5 | Pseudoroid, Model LX |
| Fistleo | G-5 | Pseudoroid, Model FX |
| Purprill | H-4 | Pseudoroid, Model PX |
| Hurricaune | I-3 | Pseudoroid, Model HX |
| Leganchor | J-5 | Pseudoroid, Model LX |
| Flammole | K-4 | Pseudoroid, Model FX |
| Protectos | L-4 | Pseudoroid, Model PX |
| Prometheus | X-3 | |
| Pandora | M-3 | |
| Prometheus & Pandora | O-2 | |
| Serpent | D-5 | |
| Omega Zero | N-1 | |

Giga Aspis, the tutorial boss, is not listed: the randomizer skips the tutorial.

## Writing a requirement

A requirement is a text with these building blocks, combined with `&` (and), `|` (or) and parentheses.

| Write | Meaning |
|---|---|
| `X`, `ZX`, `HX`, `FX`, `LX`, `PX`, `OX` | you can use that model (for HX, FX, LX and PX: at least the first half) |
| `HX2`, or `Model HX (full)` | both halves of the progressive biometal, that is, its level 2 charge (same for `FX2`, `LX2`, `PX2`) |
| `MODEL` | any model other than the human form |
| `ALL6` | the six biometals (X, ZX, HX, FX, LX and PX, both halves) |
| `Life Up x2`, or `LIFEUP>=2` | at least that many Life Ups (1 to 4) |
| `Sub Tank x1`, or `SUBTANK>=1` | at least that many Sub Tanks (1 to 4) |
| `Absorber Chip`, and the other ITEM B chips by name | you have that chip |
| `Yellow Card Key`, or `YELLOW` | you have that Card Key (Yellow, Green, Red, Blue, Purple) |

A chip named in a requirement is promoted from useful to progression automatically, so the logic can place it where
you can reach it. A requirement the pool cannot meet, or a boss name the world does not know, stops generation with a
message that says which entry is wrong.

## Example

```yaml
boss_logic:
  Hivolt: "HX & Life Up x2"
  Flammole: "Model FX (full) & Absorber Chip"
  Serpent: "ALL6 & Sub Tank x2 & Life Up x4"
  Omega Zero: "OX | (ALL6 & SUBTANK>=2)"
```
