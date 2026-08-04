def _parse_reg(statement):
    statement_left_bracket_index = statement.index('[')
    statement_right_bracket_index = statement.index(']')
    statement_N_string = statement[statement_left_bracket_index+1:statement_right_bracket_index]

    return (statement[:statement_left_bracket_index].split()[-1], int(statement_N_string))

# returns a result dict
def parse_qasm(qasm_str: str):
    result = {
        "qreg": {},
        "creg": {},
        "ops": [],
    }
    # Remove first two lines
    statements = qasm_str.split(";")
    statements_without_header = statements[2:]
    
    # Configure qreg
    qname, qsize = _parse_reg(statements_without_header[0])
    result["qreg"][qname] = qsize

    # Configure creg
    cname, csize = _parse_reg(statements_without_header[1])
    result["creg"][cname] = csize
    return result
