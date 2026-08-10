"""Emit backend-native circuit text from the LoomQ IR (the inverse of parse_qasm)."""

# IR gate name -> OriginIR mnemonic (per target_ir_contract.md). The whitelist
# names that differ from OriginIR live here; the rest map to their upper-case form.
_ORIGINIR_GATES = {
    "h": "H",
    "x": "X",
    "s": "S",
    "sdg": "SDAG",
    "t": "T",
    "tdg": "TDAG",
    "ry": "RY",
    "rz": "RZ",
    "cx": "CNOT",
    "cu1": "CU1",
    "swap": "SWAP",
    "ccx": "TOFFOLI",
}


def emit_spinq(ir):
    """Emit OpenQASM 2.0 for the SpinQ target from the IR."""
    lines = []

    # 1. Header (always the same two lines)
    lines.append("OPENQASM 2.0;")
    lines.append('include "qelib1.inc";')

    # 2. Register declarations   <-- YOUR SLICE 1
    for name, size in ir["qreg"].items():
        lines.append(f"qreg {name}[{size}];")
    for name, size in ir["creg"].items():
        lines.append(f"creg {name}[{size}];")

    # 3. Ops -> one line each     (slice 2, next)
    for op in ir["ops"]:
        if op["gate"] == "measure":
            qname = list(ir["qreg"])[0]
            cname = list(ir["creg"])[0]
            line = f"measure {qname}[{op['qubits'][0]}] -> {cname}[{op['clbits'][0]}];"
        else: 
            qname = list(ir["qreg"])[0]                                  # "q"
            qubits_str = ", ".join(f"{qname}[{i}]" for i in op['qubits'])  # <-- handles 1, 2, OR 3 qubits
            param_str  = f"({op['params'][0]})" if op["params"] else ""    # <-- handles param OR no param
            line = f"{op['gate']}{param_str} {qubits_str};"
        
        lines.append(line)

    # 4. Join into one string
    return "\n".join(lines) + "\n"


def emit_originir(ir):
    """Emit OriginIR text for the OriginQ target from the IR.

    OriginIR differs from QASM: registers are `QINIT N` / `CREG N`, gates use
    upper-case mnemonics (cx -> CNOT, ccx -> TOFFOLI, ...), a parameter follows
    the gate name as `RZ(theta) q[0]`, and measurement is `MEASURE q[i], c[j]`.
    """
    lines = []

    # Registers: QINIT <n qubits>, CREG <n classical bits>.
    for _name, size in ir["qreg"].items():
        lines.append(f"QINIT {size}")
    for _name, size in ir["creg"].items():
        lines.append(f"CREG {size}")

    qname = list(ir["qreg"])[0]
    cname = list(ir["creg"])[0]
    for op in ir["ops"]:
        if op["gate"] == "measure":
            lines.append(f"MEASURE {qname}[{op['qubits'][0]}], {cname}[{op['clbits'][0]}]")
        else:
            gate = _ORIGINIR_GATES[op["gate"]]
            qubits_str = ", ".join(f"{qname}[{i}]" for i in op["qubits"])
            param_str = f"({op['params'][0]})" if op["params"] else ""
            lines.append(f"{gate}{param_str} {qubits_str}")

    return "\n".join(lines) + "\n"