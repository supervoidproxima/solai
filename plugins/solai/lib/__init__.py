# -*- coding: utf-8 -*-
"""`solai` engine library.

Primitives (fm, stamp, regions, fsplan) know nothing about vaults. Declarations (decl)
know nothing about output. Emitters (emit/) know nothing about the filesystem. The
engine wires the four together and is the only thing that writes.
"""
VERSION = '0.35.0'
