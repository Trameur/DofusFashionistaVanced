#!/usr/bin/env python3
"""
retro_swf_parser.py: pure-Python parser for Dofus Retro "lang" SWF files.

Dofus Retro ships its game data as SWF files whose payload is an ActionScript 2
program that builds global objects (e.g. `I` for items). This module:
  1. zlib-decompresses the CWS SWF,
  2. walks the SWF tags to collect the DoAction bytecode blocks,
  3. runs a small AS2 stack machine over the subset of opcodes those blocks use
     (ConstantPool, Push, Get/SetVariable, Get/SetMember, InitObject/Array,
     NewObject, Pop), reconstructing the global variables.

No external tool (JPEXS/Flare/Java) required.

Verified: items_fr_1260.swf -> globals['I']['u'] = 11203 item records, each with
fields n (name), l (level), t (type id), e (effects), c (conditions), s (set)…

Usage:
    from retro_swf_parser import parse_lang_swf
    globals_ = parse_lang_swf(open('items_fr_xxx.swf','rb').read())
    items = globals_['I']['u']
"""

from __future__ import annotations

import struct
import zlib


def _decode_str(raw: bytes) -> str:
    """Dofus Retro lang strings are UTF-8; fall back to latin-1 for odd bytes."""
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('latin-1')


def _decompress(swf: bytes) -> bytes:
    if swf[:3] == b'CWS':
        return zlib.decompress(swf[8:])
    if swf[:3] == b'FWS':
        return swf[8:]
    raise ValueError('Not a SWF (expected CWS/FWS, got %r)' % swf[:8])


def _iter_doaction_blocks(body: bytes):
    """Yield the bytecode of every DoAction (tag 12) / DoInitAction (tag 59)."""
    nbits = body[0] >> 3
    pos = ((5 + 4 * nbits + 7) // 8) + 4  # skip RECT + frameRate(2) + frameCount(2)
    n = len(body)
    while pos < n - 1:
        tag_code_len = struct.unpack_from('<H', body, pos)[0]
        pos += 2
        code = tag_code_len >> 6
        length = tag_code_len & 0x3F
        if length == 0x3F:
            length = struct.unpack_from('<I', body, pos)[0]
            pos += 4
        if code == 0:  # End tag
            break
        if code in (12, 59):
            yield body[pos:pos + length]
        pos += length


class _AS2Machine:
    """Minimal AS2 interpreter for the opcodes Dofus lang files use."""

    def __init__(self):
        self.pool = []
        self.stack = []
        self.vars = {}

    def run(self, bytecode: bytes):
        i, n = 0, len(bytecode)
        while i < n:
            op = bytecode[i]
            i += 1
            if op >= 0x80:
                ln = struct.unpack_from('<H', bytecode, i)[0]
                i += 2
                payload = bytecode[i:i + ln]
                i += ln
            else:
                payload = b''
            try:
                self._exec(op, payload)
            except Exception:
                # Be permissive: an unhandled edge opcode shouldn't abort the
                # whole extraction. The data-building opcodes are simple/regular.
                pass

    def _exec(self, op, p):
        st = self.stack
        if op == 0x88:  # ConstantPool
            count = struct.unpack_from('<H', p, 0)[0]
            o, pool = 2, []
            for _ in range(count):
                e = p.index(0, o)
                pool.append(_decode_str(p[o:e]))
                o = e + 1
            self.pool = pool
        elif op == 0x96:  # Push
            o = 0
            while o < len(p):
                t = p[o]
                o += 1
                if t == 0:
                    e = p.index(0, o)
                    st.append(_decode_str(p[o:e]))
                    o = e + 1
                elif t == 1:
                    st.append(struct.unpack_from('<f', p, o)[0]); o += 4
                elif t in (2, 3):
                    st.append(None)
                elif t == 4:
                    st.append(('reg', p[o])); o += 1
                elif t == 5:
                    st.append(bool(p[o])); o += 1
                elif t == 6:
                    st.append(struct.unpack_from('<d', p, o)[0]); o += 8
                elif t == 7:
                    st.append(struct.unpack_from('<i', p, o)[0]); o += 4
                elif t == 8:
                    idx = p[o]; o += 1
                    st.append(self.pool[idx] if idx < len(self.pool) else None)
                elif t == 9:
                    idx = struct.unpack_from('<H', p, o)[0]; o += 2
                    st.append(self.pool[idx] if idx < len(self.pool) else None)
                else:
                    break
        elif op == 0x1C:  # GetVariable
            nm = st.pop(); st.append(self.vars.get(nm))
        elif op == 0x1D:  # SetVariable
            v = st.pop(); nm = st.pop(); self.vars[nm] = v
        elif op == 0x4E:  # GetMember
            nm = st.pop(); ob = st.pop()
            st.append(ob.get(str(nm)) if isinstance(ob, dict) else None)
        elif op == 0x4F:  # SetMember
            v = st.pop(); nm = st.pop(); ob = st.pop()
            if isinstance(ob, dict):
                ob[str(nm)] = v
        elif op == 0x43:  # InitObject
            c = st.pop(); ob = {}
            for _ in range(int(c) if c else 0):
                val = st.pop(); key = st.pop(); ob[str(key)] = val
            st.append(ob)
        elif op == 0x42:  # InitArray
            c = st.pop(); arr = []
            for _ in range(int(c) if c else 0):
                arr.append(st.pop())
            st.append(list(reversed(arr)))
        elif op == 0x40:  # NewObject
            st.pop()  # constructor name
            c = st.pop()
            for _ in range(int(c) if c else 0):
                if st:
                    st.pop()
            st.append({})
        elif op == 0x17:  # Pop
            if st:
                st.pop()
        elif op == 0x47:  # Add2 (typed add). Used to re-join string literals that
            # were split in the constant pool because they contain a '"' (e.g. the
            # Sram class description quotes a state name). Without this the fragments
            # stay as separate stack items and misalign the surrounding InitObject.
            if len(st) >= 2:
                b = st.pop()
                a = st.pop()
                if isinstance(a, str) or isinstance(b, str):
                    st.append(('' if a is None else str(a))
                              + ('' if b is None else str(b)))
                else:
                    try:
                        st.append(a + b)
                    except Exception:
                        st.append(a if a is not None else b)
        # other opcodes (jumps, function defs) are irrelevant to the static data
        # tables and safely ignored.


def parse_lang_swf(swf_bytes: bytes) -> dict:
    """Parse a Dofus Retro lang SWF; return the reconstructed global vars dict."""
    body = _decompress(swf_bytes)
    machine = _AS2Machine()
    for block in _iter_doaction_blocks(body):
        machine.run(block)
    return machine.vars


if __name__ == '__main__':
    import sys
    import json
    if len(sys.argv) < 2:
        print('usage: retro_swf_parser.py <file.swf> [global_var]', file=sys.stderr)
        raise SystemExit(2)
    g = parse_lang_swf(open(sys.argv[1], 'rb').read())
    if len(sys.argv) >= 3:
        print(json.dumps(g.get(sys.argv[2]), ensure_ascii=False)[:2000])
    else:
        print('globals:', list(g.keys()))
        for k, v in g.items():
            if isinstance(v, dict):
                print('  %s: dict(%d)' % (k, len(v)))
