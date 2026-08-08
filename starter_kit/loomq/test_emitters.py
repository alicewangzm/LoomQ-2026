#!/usr/bin/env python3
"""Self-tests for the backend emitters.

Run from the repo root:

    python starter_kit/loomq/test_emitters.py

Uses property-based (round-trip) tests: parse -> emit -> parse must land on the
same IR, since an emitter is the inverse of the parser. No third-party deps.
"""

from parser import parse_qasm
from emitters import emit_spinq
from testkit import check, summary


def roundtrips(qasm):
    """emit_spinq is faithful iff re-parsing its output reproduces the IR."""
    ir = parse_qasm(qasm)
    return parse_qasm(emit_spinq(ir)) == ir


BELL = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0], q[1];
measure q -> c;
"""

# A circuit exercising a param gate, a 3-qubit gate, and whole-register measure.
MIXED = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
rz(pi/2) q[0];
ccx q[0], q[1], q[2];
measure q -> c;
"""

check("bell round-trips through emit_spinq", roundtrips(BELL), True)
check("mixed (param + ccx) round-trips through emit_spinq", roundtrips(MIXED), True)

summary()
