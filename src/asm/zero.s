@ Mega Man Zero 3/4 boss sets read from the ROM.
@ The game draws the eight optional bosses of N-1 with sprites it reads from a
@ Game Pak in the second slot and converts on the spot. The patch converts them
@ at patch time from the player's own Zero 3 and Zero 4 ROMs and stores the
@ result in a file of the ROM, so this loader only reads a slice of that file
@ into the buffer the engine hands it and fills in the three pointers.
@ Replaces FUN_02010a28 and the converters behind it (rom/zero.py ZERO_LOADER);
@ the table of slices follows the code and is written at patch time.

        .thumb

.equ FS_InitFile,           0x020AF090
.equ FS_OpenFile,           0x020AED40
.equ FS_SeekFile,           0x020AEB9C
.equ FS_ReadFile,           0x020AEC08
.equ FS_CloseFile,          0x020AECF8
.equ FILE_LEN,              0x58            @ room for an FSFile on the stack
.equ ENTRY_LEN,             20              @ u16 key, u16 0, u32 offset, u32 size, u32 frames, u32 graphics

        .org    0x02010A28
@ rom: ZERO_LOADER
@ r0 = game (0 Zero 3, 1 Zero 4), r1 = table (0 or 1), r2 = set, r3 = destination,
@ [sp] = the engine's three pointers (animations, frames, graphics). Returns the bytes read.
loader:
        push    {r4, r5, r6, lr}
        sub     sp, #FILE_LEN
        adds    r4, r3, #0              @ destination
        lsls    r0, r0, #9
        lsls    r1, r1, #8
        orrs    r0, r1
        lsls    r2, r2, #24
        lsrs    r2, r2, #24
        orrs    r0, r2                  @ key: game << 9 | table << 8 | set
        ldr     r5, lit_table
        ldr     r6, lit_end
search:
        ldrh    r1, [r5]
        cmp     r1, r0
        beq     found
        cmp     r1, r6
        beq     missing
        adds    r5, #ENTRY_LEN
        b       search
missing:
        movs    r6, #0                  @ nothing read: the pointers stay on the destination
        b       pointers
found:
        mov     r0, sp
        ldr     r1, lit_init
        blx     r1                      @ FS_InitFile(&file)
        mov     r0, sp
        ldr     r1, lit_path
        ldr     r2, lit_open
        blx     r2                      @ FS_OpenFile(&file, path)
        mov     r0, sp
        ldr     r1, [r5, #4]            @ offset of the slice inside the file
        movs    r2, #0                  @ from the start of the file
        ldr     r3, lit_seek
        blx     r3                      @ FS_SeekFile(&file, offset, 0)
        mov     r0, sp
        adds    r1, r4, #0
        ldr     r2, [r5, #8]            @ size of the slice
        ldr     r3, lit_read
        blx     r3                      @ FS_ReadFile(&file, destination, size)
        mov     r0, sp
        ldr     r1, lit_close
        blx     r1                      @ FS_CloseFile(&file)
        ldr     r6, [r5, #8]
pointers:
        ldr     r0, [sp, #FILE_LEN + 16]    @ the caller's [sp]: past the file and the pushed registers
        str     r4, [r0]                @ animations
        ldr     r1, [r5, #12]
        adds    r1, r1, r4
        str     r1, [r0, #4]            @ frames
        ldr     r1, [r5, #16]
        adds    r1, r1, r4
        str     r1, [r0, #8]            @ graphics
        adds    r0, r6, #0
        add     sp, #FILE_LEN
        pop     {r4, r5, r6, pc}
lit_table:      .word   table
lit_end:        .word   0xFFFF
lit_init:       .word   FS_InitFile
lit_path:       .word   path
lit_open:       .word   FS_OpenFile
lit_seek:       .word   FS_SeekFile
lit_read:       .word   FS_ReadFile
lit_close:      .word   FS_CloseFile
path:           .byte   0x2F, 0x6D, 0x5F, 0x6C, 0x69, 0x76, 0x5F, 0x6A, 0x70, 0x2E, 0x62, 0x69, 0x6E, 0x00, 0x00, 0x00
table:                                  @ written at patch time (rom/zero.py ZERO_TABLE_RAM)
