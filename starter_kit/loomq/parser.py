"""OpenQASM 2.0 parser for the LoomQ universal transpiler (L1.1).

Turns raw QASM text into a neutral intermediate representation (IR) that every
backend emitter (SpinQ / OriginIR / Braket) can walk. Keeping the IR
vendor-agnostic is what makes the transpiler genuinely "universal" rather than
three hardcoded string translators.

IR shape returned by parse_qasm():

    {
        "qreg": {"q": 2},         # register name -> size
        "creg": {"c": 2},
        "ops":  [                 # operations, in program order
            {"gate": "h",  "qubits": [0],    "params": []},
            {"gate": "cx", "qubits": [0, 1], "params": []},
            # measure ops also carry their classical-bit targets:
            {"gate": "measure", "qubits": [0], "clbits": [0]},
        ],
    }
"""

import re

def _parse_reg(statement):
    """Parse one register declaration into a (name, size) pair.

    >>> _parse_reg("qreg q[2]")
    ('q', 2)
    >>> _parse_reg("creg c[12]")
    ('c', 12)

    Size is the integer between the brackets. Name is the last whitespace-
    separated word before '[', so any leading newline left by the ';' split
    is harmlessly dropped.
    """
    statement_left_bracket_index = statement.index("[")
    statement_right_bracket_index = statement.index("]")
    statement_N_string = statement[
        statement_left_bracket_index + 1 : statement_right_bracket_index
    ]

    return (
        statement[:statement_left_bracket_index].split()[-1],
        int(statement_N_string),
    )

def _bracket_ints(s):
    """'cx q[0], q[1]' -> [0, 1]"""
    return [int(n) for n in re.findall(r'\[(\d+)\]', s)]

def parse_qasm(qasm_str: str):
    """Parse an OpenQASM 2.0 program into the LoomQ IR (see module docstring).

    Assumes the fixed header shared by every evaluation circuit:

        OPENQASM 2.0;
        include "qelib1.inc";

    so the first two ';'-separated statements are dropped, leaving the qreg
    declaration, the creg declaration, then the gate / measure body.

    TODO (L1.1): parse the gate and measure statements into result["ops"].
    """
    result = {
        "qreg": {},
        "creg": {},
        "ops": [],
    }
    # Drop the two header statements (OPENQASM + include); statements are
    # ';'-terminated, so splitting on ';' gives one entry per statement.
    statements = qasm_str.split(";")
    statements_without_header = statements[2:]

    # First two remaining statements are the quantum and classical registers.
    qname, qsize = _parse_reg(statements_without_header[0])
    result["qreg"][qname] = qsize

    cname, csize = _parse_reg(statements_without_header[1])
    result["creg"][cname] = csize

    # configure ops

    for statement in statements[2:]:
        # Step 1: parse plain (no-parameter) gates: h, x, s, sdg,t, tdg, cx, swap, ccx
        ops_statements = statement.strip()
        #should i instead check the length of ops_statments, if it is smaller than 2, it means it is wrong. 
        if ops_statements == "":
            break
        gate_name = ops_statements[0]
        #should i check specifically h, x, s, sdg, t, tdg, cx, swap, ccx to be safe here? then else will run error
        if gate_name != "measure":
            gate_list = {"gate": gate_name, "qubits": _bracket_ints(statement), "params": [] }
            result["ops"].append(gate_list)
        else: 
            left, right = statement.split("->")
            left, right = left.strip(), right.strip()

            if "[" in left:
                # single-bit form: measure q[0] -> c[0]
                q_index = _bracket_ints(left)[0]
                c_index = _bracket_ints(right)[0]
                result["ops"].append({"gate": "measure", "qubits": [q_index], "clbits": [c_index]})
            else:
                # whole-register form: measure q -> c
                q_name = left.split()[-1]              # 'q'  (word after 'measure')
                n = result["qreg"][q_name]             # how many qubits -> how many ops
                for i in range(n):                     # <-- the expansion loop
                    result["ops"].append({"gate": "measure", "qubits": [i], "clbits": [i]})
    return result
