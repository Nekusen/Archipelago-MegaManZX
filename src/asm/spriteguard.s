@ Sprite guard: set without a VRAM slot.
@ When the registrar rejects a set, ten drawers resolve its slot record to a
@ null pointer and read a halfword from address 2. At each site
@ `ldrh r0, [r0, #2]; movs r3, #1` becomes a call into the cave, which skips
@ the read when the record pointer is null.
@ Cave at 0x020C827C (rom.py SPRITEGUARD_CAVE), sites in SPRITEGUARD_SITES.

        .thumb

.equ spriteguard_cave,  0x020C827C

        .org    0x020C827C
@ rom.py: SPRITEGUARD_CAVE
        cmp     r0, #0                  @ slot record pointer
        beq     skip                    @ null: leave r0 = 0
        ldrh    r0, [r0, #2]            @ the displaced read
skip:   movs    r3, #1                  @ the displaced constant
        bx      lr

@ The ten drawer sites.  was: ldrh r0, [r0, #2]; movs r3, #1   (SPRITEGUARD_ORIG)

        .org    0x0200F0D4
@ rom.py: thumb_bl(SPRITEGUARD_SITES[0], SPRITEGUARD_CAVE_RAM)
        bl      spriteguard_cave

        .org    0x0200F244
@ rom.py: thumb_bl(SPRITEGUARD_SITES[1], SPRITEGUARD_CAVE_RAM)
        bl      spriteguard_cave

        .org    0x0200F424
@ rom.py: thumb_bl(SPRITEGUARD_SITES[2], SPRITEGUARD_CAVE_RAM)
        bl      spriteguard_cave

        .org    0x0200F85A
@ rom.py: thumb_bl(SPRITEGUARD_SITES[3], SPRITEGUARD_CAVE_RAM)
        bl      spriteguard_cave

        .org    0x0200FA5A
@ rom.py: thumb_bl(SPRITEGUARD_SITES[4], SPRITEGUARD_CAVE_RAM)
        bl      spriteguard_cave

        .org    0x0200FC96
@ rom.py: thumb_bl(SPRITEGUARD_SITES[5], SPRITEGUARD_CAVE_RAM)
        bl      spriteguard_cave

        .org    0x0200FFA2
@ rom.py: thumb_bl(SPRITEGUARD_SITES[6], SPRITEGUARD_CAVE_RAM)
        bl      spriteguard_cave

        .org    0x02010236
@ rom.py: thumb_bl(SPRITEGUARD_SITES[7], SPRITEGUARD_CAVE_RAM)
        bl      spriteguard_cave

        .org    0x020104CA
@ rom.py: thumb_bl(SPRITEGUARD_SITES[8], SPRITEGUARD_CAVE_RAM)
        bl      spriteguard_cave

        .org    0x02010756
@ rom.py: thumb_bl(SPRITEGUARD_SITES[9], SPRITEGUARD_CAVE_RAM)
        bl      spriteguard_cave
