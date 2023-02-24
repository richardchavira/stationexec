# Copyright 2004-present Facebook. All Rights Reserved.

# @lint-ignore-every PYTHON3COMPATIMPORTS1

from collections import defaultdict
from operator import methodcaller


class UnsupportedConditionalType(Exception):
    pass


def flatten_2d_list(incoming):
    return [item for _list in incoming for item in _list]


def unique_list(incoming):
    return list(set(incoming))


def named_method_on_list(obj_list, method, *args):
    """
    Perform a named method on all items in a list with list of args and return result list
    """
    return list(map(methodcaller(method, *args), obj_list))


def evaluate_conditional(operator, operand1, operand2, operand3=None):
    if operand1 is None or operand2 is None:
        # At least one operand unavailable to evaluate against -
        # return False to terminate the conditional. Do not run
        return False

    def compare(a, b):
        """
        Compare operand a and b, which are assumed to be of the same type. If either is None,
        return None, indicating comparison could not be performed.

        :param Union[int, str, float] a: 1st operand to compare
        :param Union[int, str, float] b: 2nd operand to compare

        :return: -1,0,1
        :rtype: int

        :raises ValueError: if types are not compatible
        """
        if a is None or b is None:
            return None
        return (a > b) - (a < b)

    if operator == "==":
        return compare(operand1, operand2) == 0
    elif operator == "<":
        return compare(operand1, operand2) < 0
    elif operator == "<=":
        return compare(operand1, operand2) <= 0
    elif operator == ">":
        return compare(operand1, operand2) > 0
    elif operator == ">=":
        return compare(operand1, operand2) >= 0
    elif operator == "!=":
        return compare(operand1, operand2) != 0
    elif operator == "inrange":
        if operand3 is None:
            return False
        # True if operand1 between operand2 and 3
        return (operand1 >= operand2) and (operand1 <= operand3)
    elif operator == "!inrange":
        if operand3 is None:
            return False
        # True if operand1 not between operand2 and 3
        return (operand1 < operand2) or (operand1 > operand3)


def parse_result_condition(ref_string, system_configs):
    if ref_string is None:
        raise Exception("Conditional definition does not exist")
    ref_string = ref_string.lstrip()
    operator, operand2 = ref_string.split(" ", 1)
    operand3 = "_none"
    if operator in ["inrange", "!inrange"]:
        operand2, operand3 = operand2.lstrip().split(",")
    # So that the data is interpreted for the operation data class itself (not to be applied to
    # the running operation - for behind-the-scenes use), prepend data 'value' tag with '_data::'
    op2 = parse_data_reference("_data::operand2", operand2.lstrip(), system_configs)
    op3 = parse_data_reference("_data::operand3", operand3.lstrip(), system_configs)
    return operator, op2, op3


def parse_conditional_reference(ref_string, system_configs):
    if ref_string is None:
        raise Exception("Conditional definition does not exist")
    ref_string = ref_string.lstrip()
    operand1, operator, operand2 = ref_string.split(" ", 2)
    operand3 = "_none"
    if operator in ["inrange", "!inrange"]:
        operand2, operand3 = operand2.lstrip().split(",")
    # So that the data is interpreted for the operation data class itself (not to be applied to
    # the running operation - for behind-the-scenes use), prepend data 'value' tag with '_data::'
    op1 = parse_data_reference("_data::operand1", operand1.lstrip(), system_configs)
    op2 = parse_data_reference("_data::operand2", operand2.lstrip(), system_configs)
    op3 = parse_data_reference("_data::operand3", operand3.lstrip(), system_configs)
    return operator, op1, op2, op3

def string_to_bool(data):
    booleans = {'FALSE': False, 'TRUE': True}
    key = str(data).upper()
    return booleans.get(key, None)
    
def string_to_int(data):
    try:
        integer_value = int(str(data)) # this prevents it from converting floats with a decimal component to ints
        return integer_value
    except (ValueError, TypeError):
        return None

def string_to_float(data):
    try:
        float_value = float(data)
        return float_value
    except (ValueError, TypeError):
        return None

def string_to_datatype(data):
    data_as_bool = string_to_bool(data)
    if data_as_bool is not None:
        return data_as_bool
    data_as_int = string_to_int(data)
    if data_as_int is not None:
        return data_as_int
    data_as_float = string_to_float(data)
    if data_as_float is not None:
        return data_as_float
    return data

def parse_data_reference(local_key, value, system_configs):
    def _parse_ref(data_ref):
        try:
            data = data_ref.split("::", 1)
        except AttributeError:
            # Value type cannot be split - must be a constant. Return value
            return "_constant", data_ref
        if len(data) == 0:
            return None
        elif len(data) == 1:
            data = string_to_datatype(data[0])
            if data == "_none":
                data = None
            # Data is a constant value
            return "_constant", data
        else:
            # Data is formatted in "source::result" format; return the tuple
            return data

    # Attempt to parse a data reference either into a constant or a reference to external data
    source, ref_value = _parse_ref(value)
    # Local Key is name in operation object to set with the value
    # External Key is name of result in referenced operation the value will come from (if
    #   applicable)
    # Value is either the constant or the name of the reference
    # Source is _constant, _config, or the name of the operation that the data will come from
    ex_data = {
        "local_key": local_key,
        "external_key": None if source in ["_constant", "_config"] else ref_value,
        "value": _get_external_value(source, ref_value, system_configs),
        "source": source,
    }
    return ex_data


def _get_external_value(source, value, system_configs):
    """
    Helper function to determine the value of the external data now.

    If the source is _constant, value is constant and the value is known and returned.
    If the source is _config, the value is the key to the config data, which is returned.
    If the source is anything else, it is a reference and the value is not known now.

    :param source:
    :param value:
    :param system_configs:
    :return:
    """
    if source == "_constant":
        return value
    elif source == "_config":
        return system_configs[value]
    else:
        return None


def graph_to_path_matrix(input_graph):
    # Create a path matrix from the graph - shows the possibility of reaching a node from
    # any other node

    def dfs_tree(graph_node, graph):
        visited = set()

        def visit(node):
            visited.add(node)
            for dependency in graph[node]:
                if dependency not in visited:
                    visit(dependency)

        visit(graph_node)
        return list(visited)

    # Derived from https://github.com/mnylen/pygraph/blob/master/pygraph/algorithms/transitivity.py
    matrix = defaultdict(dict)
    for i in input_graph:
        for j in input_graph:
            is_reachable = False if (i == j) else j in dfs_tree(i, input_graph)
            matrix[i][j] = is_reachable

    return matrix


def find_graph_entry_exit(matrix):
    entry_nodes = []
    exit_nodes = []

    # Node is an Entry Node (nothing comes before it) if the row for that node is all 0
    for row in matrix:
        row_truth_values = [path for path in matrix[row] if matrix[row][path] is True]
        col_truth_values = [path for path in matrix[row] if matrix[path][row] is True]
        row_has_zero_true_values = len(row_truth_values) == 0
        col_has_zero_true_values = len(col_truth_values) == 0
        if row_has_zero_true_values:
            # Row is an entry node - no true values in the path matrix
            entry_nodes.append(row)
        if col_has_zero_true_values:
            # Col is an exit node - no true values in the path matrix
            exit_nodes.append(row)

    return entry_nodes, exit_nodes


class SequenceLoop(Exception):
    pass


def reduce_graph(graph, matrix):
    # Derived from Harry Hsu. "An algorithm for finding a minimal equivalent graph of a digraph."
    # via https://stackoverflow.com/questions/1690953/transitive-reduction-algorithm-pseudocode

    # Transitive Reduction of graph performed on a path
    for j in graph:
        for i in graph:
            # Cycle detection
            if matrix[i][j] and matrix[j][i]:
                # If a path exists both directions between nodes, there is a loop
                raise SequenceLoop("Loop found between {0} and {1}".format(i, j))

            if matrix[i][j]:
                # If a path exists between I and J
                for k in graph:
                    if matrix[j][k]:
                        # And a path also exists between J and K
                        # A path between I and K would be redundant - remove the path
                        matrix[i][k] = False

    new_graph = {key: [] for key in matrix}
    for i in matrix:
        for j in matrix:
            if matrix[i][j]:
                new_graph[i].append(j)

    return new_graph


def _print_matrix(matrix):
    print(" ")
    print("   [{0}]".format(", ".join(matrix.keys())))
    for key, value in matrix.items():
        print("[{0: <10}]{1}".format(key, [int(x) for x in value.values()]))

    print(" ")


if __name__ == "__main__":
    config = {"M2000": 4}
    print(parse_conditional_reference("8 < 6", config))
    print(parse_conditional_reference("_config::M2000 < 6", config))
    print(parse_conditional_reference("Cleaning::particles < 6", config))
    print(
        parse_conditional_reference(
            "Cleaning::particles inrange 6, _config::M2000", config
        )
    )
    # print(parse_conditional_reference(None, config))

    print(evaluate_conditional("<", 8, 6))
    print(evaluate_conditional("!=", 8, 6))
    print(evaluate_conditional("inrange", 8, 6, 15))
    print(evaluate_conditional("!inrange", 8, 6, 15))
    print(evaluate_conditional("inrange", 8, 6))
