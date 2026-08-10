"""L2 agent: turn natural language into quantum circuits and backend advice.

agent_chat(prompt) reads the LOOMQ_LLM_* environment (via the starter kit's
llm_client transport) and returns the model's response. One system prompt covers
the three L2 task types: intent -> OpenQASM 2.0, error repair, and backend
selection against the official capabilities table.
"""

import json
import os
import re
import sys

# llm_client.py ships in the starter_kit dir (the parent of loomq/). Put that on
# the path so we reuse the official transport instead of duplicating it.
_LOOMQ_DIR = os.path.dirname(__file__)
_STARTER_KIT = os.path.dirname(_LOOMQ_DIR)
if _STARTER_KIT not in sys.path:
    sys.path.insert(0, _STARTER_KIT)

from llm_client import chat_completion  # noqa: E402
from parser import parse_qasm  # noqa: E402

# Matches a fenced code block, optionally tagged ```qasm. Group 1 = the body.
_QASM_BLOCK = re.compile(r"```(?:qasm)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

_CAPS_PATH = os.path.join(_STARTER_KIT, "backend_capabilities.json")

WHITELIST_GATES = "h, x, s, sdg, t, tdg, rz(theta), ry(theta), cx, cu1(theta), swap, ccx"


def _backend_table():
    """Compact 'id: constraints' lines from the official capabilities file.

    The agent needs the real data to pick a backend, but feeding it the whole
    JSON is noisy. One line per backend keeps the canonical id front and centre.
    """
    try:
        with open(_CAPS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except OSError:
        return "(backend table unavailable)"
    lines = []
    for b in data.get("backends", []):
        lines.append(
            f"- {b['id']}: {b['kind']}, max_qubits={b['max_qubits']}, "
            f"queue={b['queue']}, cost={b['cost']}, "
            f"requires_account={b['requires_account']}"
        )
    return "\n".join(lines)


def _system_prompt():
    return f"""You are LoomQ, a friendly assistant that lets people with no quantum
background drive real quantum computers. You handle three kinds of request.

1. GENERATE - the user describes what they want (a state, an experiment). Reply
   with one complete, valid OpenQASM 2.0 program in a single ```qasm code block.

2. FIX - the user shows broken circuit code and states a goal. Return the
   corrected OpenQASM 2.0 in a single ```qasm code block, preserving their goal.

3. RECOMMEND - the user gives constraints (qubit count, queue, cost). Reply in
   plain language AND include the exact canonical backend id (verbatim, e.g.
   braket_local_simulator) chosen from this table:
{_backend_table()}

Circuit rules (for GENERATE and FIX):
- Use ONLY these gates: {WHITELIST_GATES}.
- Always include `OPENQASM 2.0;`, `include "qelib1.inc";`, a qreg, a creg, the
  gates, and measurements. Measure the whole register with `measure q -> c;`.
- Put the circuit in the ```qasm block; keep any prose short and outside it.

If constraints cannot be satisfied (e.g. more qubits than any backend offers),
say so honestly rather than inventing an answer.
"""


def _extract_qasm(text):
    """Pull the OpenQASM program out of a reply, or None if there isn't one.

    Prefers a fenced ```qasm block; falls back to everything from the first
    `OPENQASM` keyword (some models skip the fences).
    """
    match = _QASM_BLOCK.search(text)
    if match:
        return match.group(1).strip()
    if "OPENQASM" in text:
        return text[text.index("OPENQASM"):].strip()
    return None


def _validate_qasm(qasm):
    """Return None if the circuit is structurally valid, else a short error.

    Uses L1's parser (which catches syntax errors and non-whitelist gates) plus
    a qubit/clbit index-range check. This is dependency-free, fast, and yields
    clear messages the model can act on -- far better feedback than a raw
    simulator stack trace. Any whitelist circuit that passes here also runs.
    """
    try:
        ir = parse_qasm(qasm)
    except Exception as exc:  # noqa: BLE001 - surface the parse failure verbatim
        return str(exc)[:200]

    n_qubits = sum(ir["qreg"].values())
    n_clbits = sum(ir["creg"].values())
    for op in ir["ops"]:
        for i in op.get("qubits", []):
            if i >= n_qubits:
                return f"qubit index q[{i}] is out of range ({n_qubits} qubits declared)"
        for j in op.get("clbits", []):
            if j >= n_clbits:
                return f"classical bit c[{j}] is out of range ({n_clbits} bits declared)"
    return None


def _chat(messages):
    return chat_completion(messages)["choices"][0]["message"]["content"]


def agent_chat(prompt: str, max_retries: int = 2) -> str:
    """Return the agent's response, self-verifying any circuit it produces.

    Reads LOOMQ_LLM_* via llm_client (raises if unset). For circuit tasks the
    reply's QASM is run through L1; if it fails, the error is fed back and the
    model retries (up to max_retries). Non-circuit replies (e.g. a backend
    recommendation) are returned as-is.
    """
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": prompt},
    ]
    reply = _chat(messages)
    for _attempt in range(max_retries):
        qasm = _extract_qasm(reply)
        if qasm is None:
            return reply  # no circuit to verify (e.g. backend recommendation)
        error = _validate_qasm(qasm)
        if error is None:
            return reply  # circuit runs -> accept it
        # Feed the failure back and let the model correct itself.
        messages.append({"role": "assistant", "content": reply})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"That circuit failed to run: {error}\n"
                    "Return a corrected OpenQASM 2.0 program in a ```qasm block, "
                    "using only the allowed gates."
                ),
            }
        )
        reply = _chat(messages)
    return reply  # out of retries -> best effort


if __name__ == "__main__":
    # Manual smoke test: set LOOMQ_LLM_* then `python agent.py`. Exercises one
    # prompt of each L2 task type (generate / fix / recommend).
    _DEMOS = [
        "Make a 3-qubit GHZ (maximally entangled) state and measure everything.",
        "I want a Bell state but this errors, please fix it: H q[0]; CX q[0] q[1]",
        "I need to run a 15-qubit circuit with zero queue wait. Which backend?",
    ]
    for _d in _DEMOS:
        print("=" * 64)
        print("USER:", _d)
        print("-" * 64)
        print(agent_chat(_d))
        print()

