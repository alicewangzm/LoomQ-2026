"""L2 agent: turn natural language into quantum circuits and backend advice.

agent_chat(prompt) reads the LOOMQ_LLM_* environment (via the starter kit's
llm_client transport) and returns the model's response. One system prompt covers
the three L2 task types: intent -> OpenQASM 2.0, error repair, and backend
selection against the official capabilities table.
"""

import json
import os
import sys

# llm_client.py ships in the starter_kit dir (the parent of loomq/). Put that on
# the path so we reuse the official transport instead of duplicating it.
_LOOMQ_DIR = os.path.dirname(__file__)
_STARTER_KIT = os.path.dirname(_LOOMQ_DIR)
if _STARTER_KIT not in sys.path:
    sys.path.insert(0, _STARTER_KIT)

from llm_client import chat_completion  # noqa: E402

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


def agent_chat(prompt: str) -> str:
    """Return the agent's natural-language response to a user request.

    Reads LOOMQ_LLM_* via llm_client (raises if unset), makes one chat-completion
    call, and returns the assistant's message text.
    """
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": prompt},
    ]
    response = chat_completion(messages)
    return response["choices"][0]["message"]["content"]


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

