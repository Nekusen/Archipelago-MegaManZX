#!/usr/bin/env python3
"""Assemble the cave and hook sources (src/asm/*.s) and compare them with the bytes rom/ ships.

Usage, from the package root (needs `pip install keystone-engine capstone`):

  python tools/check_caves.py               # table + exit code
  python tools/check_caves.py --dis         # also the capstone disassembly of every block
  python tools/check_caves.py --emit        # print the assembled constants in the rom/ module form
  python tools/check_caves.py --only notify # only the .s files whose name contains the text

Source convention (src/asm/README.md): a file has a preamble (`.thumb` plus
`.equ` names for the game addresses) followed by blocks that each start with
`.org ADDRESS`; every block carries a line `@ rom: <expression>` naming the
constant of the rom package that holds its expected bytes. The expression is
evaluated over the module-level constants of rom/*.py, read with `ast` without
importing the package, plus the helpers `thumb_bl(src, dst)` (same formula as
rom/arm9.py) and `pickup_ap_hook(i)` (same prefix + bl + suffix composition as
patch_arm9). A string result is taken as hex.

Each block is assembled on its own (keystone, Thumb, little endian) with the
preamble in front and the `.org` address as base. Labels are local to a block,
so a hook that targets the middle of a cave uses an `.equ` with the address.

keystone emits Thumb-2 (`ldr.w`, `ldrb.w`, `nop` = 0xBF00) when an immediate
does not fit Thumb-1 or when asked for `nop`; the ARM9 (ARMv5TE) cannot run it.
0xBF00 is accepted only as padding before a literal pool, where the shipped
bytes have it, and any other 4-byte instruction that is not `bl` is reported.
The byte-for-byte comparison with rom/ is the proof: rom/ carries the bytes
players get, these sources are the readable form.

Exit code: 0 when every block is IDENTICAL, 1 when a block differs, fails to
assemble or has no `@ rom:` mark.
"""

import argparse
import ast
import re
import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_THUMB, Cs
from keystone import KS_ARCH_ARM, KS_MODE_LITTLE_ENDIAN, KS_MODE_THUMB, Ks, KsError

PKG = Path(__file__).resolve().parents[1]
ROM_DIR = PKG / "rom"
ASM_DIR = PKG / "src" / "asm"

RE_ORG = re.compile(r"^\s*\.org\s+(0x[0-9A-Fa-f]+|\d+)\s*(?:@.*)?$")
RE_TAG = re.compile(r"^\s*@\s*rom:\s*(.+?)\s*$")
RE_NAME = re.compile(r"^[A-Za-z_]\w*$")


def thumb_bl(src, dst):
    """Thumb `bl dst` placed at src (4 bytes); a copy of thumb_bl in rom/arm9.py."""
    off = dst - (src + 4)
    return struct.pack("<HH", 0xF000 | ((off >> 12) & 0x7FF), 0xF800 | ((off >> 1) & 0x7FF))


def _eval_node(node):
    """Value of a rom module assignment: literals, lists/tuples/dicts, `bytes.fromhex(...)`, `"c046" * 4`."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return _eval_node(node.left) * _eval_node(node.right)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _eval_node(node.left) + _eval_node(node.right)
    if isinstance(node, ast.List):
        return [_eval_node(e) for e in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return {_eval_node(k): _eval_node(v) for k, v in zip(node.keys, node.values)}
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "fromhex" and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "bytes"):
        return bytes.fromhex(_eval_node(node.args[0]))
    return ast.literal_eval(node)


def load_rom_constants(path):
    """Module-level constants of the rom package (name -> value), without running anything.

    `path` is the rom/ folder (every .py is read) or a single file.
    """
    files = sorted(path.glob("*.py")) if path.is_dir() else [path]
    consts = {}
    for f in files:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in tree.body:
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)):
                continue
            try:
                consts[node.targets[0].id] = _eval_node(node.value)
            except (ValueError, TypeError, SyntaxError):
                pass  # functions, classes and expressions that are not data
    return consts


def make_namespace(consts):
    """Namespace of the `@ rom:` expressions."""
    def pickup_ap_hook(i):
        ram, orig, entry, pre, post = consts["PICKUP_AP_HOOKS"][i]
        target = consts["PICKUP_AP_CAVE_RAM"] + consts["PICKUP_AP_ENTRIES"][entry]
        return pre + thumb_bl(ram + len(pre), target) + post

    ns = dict(consts)
    ns.update(thumb_bl=thumb_bl, pickup_ap_hook=pickup_ap_hook, bytes=bytes)
    return ns


def expected_bytes(expr, ns):
    value = eval(expr, {"__builtins__": {}}, ns)  # expressions of our own sources
    if isinstance(value, str):
        value = bytes.fromhex(value)
    if not isinstance(value, (bytes, bytearray)):
        raise ValueError("the expression does not give bytes: %r" % (value,))
    return bytes(value)


def split_blocks(text):
    """(preamble, [(address, lines, line number)]): split a file at its `.org` lines."""
    preamble, blocks = [], []
    for lineno, line in enumerate(text.splitlines(), 1):
        m = RE_ORG.match(line)
        if m:
            blocks.append((int(m.group(1), 0), [], lineno))
        elif blocks:
            blocks[-1][1].append(line)
        else:
            preamble.append(line)
    return preamble, blocks


def block_tag(lines):
    for line in lines:
        m = RE_TAG.match(line)
        if m:
            return m.group(1)
    return None


def disasm(code, base):
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    return list(md.disasm(code, base))


def thumb2_warnings(code, base):
    """4-byte instructions that are not `bl` (Thumb-2, undefined on the ARM9). Pool words can decode this way too."""
    out = []
    for ins in disasm(code, base):
        if ins.size == 4 and ins.mnemonic != "bl":
            out.append("%08X %s %s" % (ins.address, ins.mnemonic, ins.op_str))
    return out


def hexdump(data, width=32):
    return " ".join(data[i:i + width].hex() for i in range(0, len(data), width))


def fmt_const(name, data):
    """`NAME = bytes.fromhex("...")` in the style of the rom modules (64 hex digits per line)."""
    h = data.hex()
    if len(h) <= 64:
        return '%s = bytes.fromhex("%s")' % (name, h)
    lines = ['    "%s"' % h[i:i + 64] for i in range(0, len(h), 64)]
    return "%s = bytes.fromhex(\n%s)" % (name, "\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--asm-dir", type=Path, default=ASM_DIR)
    ap.add_argument("--rom-dir", type=Path, default=ROM_DIR, help="the rom/ folder (or a single .py)")
    ap.add_argument("--only", help="only the .s files whose name contains this text")
    ap.add_argument("--dis", action="store_true", help="print the disassembly of every block")
    ap.add_argument("--emit", action="store_true", help="print the assembled constants in the rom/ module form")
    args = ap.parse_args()

    consts = load_rom_constants(args.rom_dir)
    ns = make_namespace(consts)
    ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB | KS_MODE_LITTLE_ENDIAN)

    files = sorted(args.asm_dir.glob("*.s"))
    if args.only:
        files = [f for f in files if args.only in f.name]
    if not files:
        print("no .s sources in %s" % args.asm_dir)
        return 1

    rows, emitted, bad = [], [], 0
    for path in files:
        preamble, blocks = split_blocks(path.read_text(encoding="utf-8"))
        if not blocks:
            rows.append((path.name, "-", "-", 0, "NO .org"))
            bad += 1
            continue
        for addr, lines, lineno in blocks:
            source = "%s @0x%08X" % (path.name, addr)
            tag = block_tag(lines)
            try:
                # the trailing newline matters: keystone rejects a trailing `@` comment without one
                code = bytes(ks.asm("\n".join(preamble + lines) + "\n", addr)[0] or [])
            except KsError as e:
                rows.append((source, tag or "-", "-", 0, "ERROR keystone: %s" % e))
                bad += 1
                continue
            if tag is None:
                rows.append((source, "-", hexdump(code), len(code), "NO @ rom: MARK"))
                bad += 1
                continue
            try:
                want = expected_bytes(tag, ns)
            except Exception as e:  # the expression is ours: any failure is a source error
                rows.append((source, tag, hexdump(code), len(code), "ERROR expression: %s" % e))
                bad += 1
                continue
            if code == want:
                status = "IDENTICAL"
            else:
                status = "DIFF"
                bad += 1
            rows.append((source, tag, hexdump(code), len(code), status))
            if status == "DIFF":
                first = next((i for i, (a, b) in enumerate(zip(code, want)) if a != b), min(len(code), len(want)))
                print("--- DIFF %s (line %d): first difference at +0x%X; assembled %d B, rom/ %d B"
                      % (source, lineno, first, len(code), len(want)))
                print("    assembled: %s" % code.hex())
                print("    rom/     : %s" % want.hex())
                for ins in disasm(code, addr):
                    print("    asm  %08X  %-8s %-6s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
                for ins in disasm(want, addr):
                    print("    rom  %08X  %-8s %-6s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
            warns = thumb2_warnings(code, addr)
            if warns and status == "DIFF":
                print("    possible Thumb-2 in the assembly: %s" % "; ".join(warns))
            if args.dis:
                print("--- %s  (%s)" % (source, tag))
                for ins in disasm(code, addr):
                    print("    %08X  %-8s %-6s %s" % (ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str))
            if args.emit:
                if RE_NAME.match(tag):
                    emitted.append(fmt_const(tag, code))
                else:
                    emitted.append('# %s: %s -> "%s"' % (source, tag, code.hex()))

    w_src = max(len(r[0]) for r in rows)
    w_tag = max(len(r[1]) for r in rows)
    print("%-*s | %-*s | %5s | %s" % (w_src, "source", w_tag, "constant", "bytes", "status"))
    print("%s-+-%s-+-%s-+-%s" % ("-" * w_src, "-" * w_tag, "-" * 5, "-" * 9))
    for src, tag, _hex, n, status in rows:
        print("%-*s | %-*s | %5d | %s" % (w_src, src, w_tag, tag, n, status))
    ok = sum(1 for r in rows if r[4] == "IDENTICAL")
    print("\n%d blocks, %d IDENTICAL, %d with problems" % (len(rows), ok, bad))

    if args.emit:
        print("\n# --- assembled constants (rom/ module form) ---")
        print("\n".join(emitted))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
