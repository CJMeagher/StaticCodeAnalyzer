import pathlib
from collections import namedtuple
import re
import sys
import ast

camel_matcher = re.compile("[A-Z][A-Za-z]*$")
snake_matcher = re.compile("[a-z0-9_]*$")

error_code_to_text = {
    "S001": "Too Long",
    "S002": "Indentation is not a multiple of four",
    "S003": "Unnecessary semicolon after a statement",
    "S004": "Less than two spaces before inline comments",
    "S005": "TODO found",
    "S006": "More than two blank lines preceding a code line",
    "S007": "Too many spaces after '{}'",
    "S008": "Class name '{}' should be written in CamelCase",
    "S009": "Function name '{}' should be snake_case",
    "S010": "Argument name '{}' should be snake_case",
    "S011": "Variable '{}' in function should be snake_case",
    "S012": "The default argument value is mutable",
}

Error = namedtuple("Error", "path_to_file line code variables", defaults=[[]])


class CodeLine:
    blank_line_counter = 0

    def __init__(self, line):
        self.line = line
        self.line_length_stripped = len(self.line.rstrip())

        self.blank_lines_b4 = CodeLine.blank_line_counter
        if self.line_length_stripped == 0:
            CodeLine.blank_line_counter += 1
        else:
            CodeLine.blank_line_counter = 0

        self.start_of_comment_index = self.line.find("#")

        self.leading_whitespace_length = self.line_length_stripped - len(
            self.line.strip()
        )

        if self.start_of_comment_index == -1:
            self.code_only = self.line.rstrip()
        else:
            self.code_only = self.line[: self.start_of_comment_index].rstrip()

        self.code_only_stripped = self.code_only.lstrip()

        if self.start_of_comment_index == -1:
            self.comment_only = ""
        else:
            self.comment_only = self.line[self.start_of_comment_index :].rstrip()


def get_python_code(file):
    with open(file, "r") as code_file:
        lines_of_code = code_file.readlines()
    return lines_of_code


def get_file_list(directory_or_path):
    a_path = pathlib.Path(directory_or_path)
    if a_path.is_file() and a_path.suffix == ".py":
        return [directory_or_path]
    paths = a_path.glob("**/*.py")
    return paths


def analyze_code(file):
    lines_of_code = get_python_code(file)
    errors = []
    for line_number, a_line in enumerate(lines_of_code, 1):
        line = CodeLine(a_line)
        if line_too_long(line):
            errors.append(Error(file, line_number, "S001"))
        if bad_indent(line):
            errors.append(Error(file, line_number, "S002"))
        if trailing_semicolon(line):
            errors.append(Error(file, line_number, "S003"))
        if lt_2_spaces_b4_comment(line):
            errors.append(Error(file, line_number, "S004"))
        if todo_in_comments(line):
            errors.append(Error(file, line_number, "S005"))
        if gt_2_lines_b4_code(line):
            errors.append(Error(file, line_number, "S006"))
        if gt_1_space_after_construct(line):
            def_or_class = line.code_only_stripped.split()[0]
            errors.append(Error(file, line_number, "S007", [def_or_class]))

    tree = ast.parse("".join(lines_of_code))
    ast_analyzer = AstDefAnalyzer(file)
    ast_analyzer.visit(tree)
    errors.extend(ast_analyzer.errors)
    errors.sort()

    return errors


class AstDefAnalyzer(ast.NodeVisitor):
    def __init__(self, file):
        self.file = file
        self.errors = []

    def visit_ClassDef(self, node):
        if not re.match(camel_matcher, node.name):
            self.errors.append(Error(self.file, node.lineno, "S008", [node.name]))

        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if not re.match(snake_matcher, node.name):
            self.errors.append(Error(self.file, node.lineno, "S009", [node.name]))

        all_args = node.args.args + node.args.kwonlyargs + node.args.posonlyargs
        if node.args.kwarg:
            all_args.append(node.args.kwarg)
        if node.args.vararg:
            all_args.append(node.args.vararg)
        for arg in all_args:
            if not re.match(snake_matcher, arg.arg):
                self.errors.append(Error(self.file, node.lineno, "S010", [arg.arg]))

        all_defaults = node.args.defaults + node.args.kw_defaults
        for default in all_defaults:
            if type(default) in [ast.List, ast.Set, ast.Dict]:
                self.errors.append(Error(self.file, node.lineno, "S012"))

        self.generic_visit(node)

        ast_name_analyzer = AstNameAnalyzer(self.file)
        ast_name_analyzer.visit(node)
        self.errors.extend(ast_name_analyzer.errors)


class AstNameAnalyzer(ast.NodeVisitor):
    def __init__(self, file):
        self.file = file
        self.errors = []

    def visit_Name(self, node):
        if not isinstance(node.ctx, ast.Store):
            return
        if not re.match(snake_matcher, node.id):
            self.errors.append(Error(self.file, node.lineno, "S011", [node.id]))


def line_too_long(line):
    return line.line_length_stripped > 79


def bad_indent(line):
    return line.leading_whitespace_length % 4 != 0


def trailing_semicolon(line):
    return len(line.code_only) > 0 and line.code_only[-1] == ";"


def lt_2_spaces_b4_comment(line):
    if line.start_of_comment_index == -1:
        return False
    if len(line.code_only) == 0:
        return False
    if (line.start_of_comment_index - len(line.code_only)) < 2:
        return True


def todo_in_comments(line):
    return re.search(r"\b(\s*TODO\s*)\b", line.comment_only, flags=re.IGNORECASE)


def gt_2_lines_b4_code(line):
    return (line.line_length_stripped > 0) and (line.blank_lines_b4 > 2)


def gt_1_space_after_construct(line):
    if line.code_only_stripped.startswith(
        "def  "
    ) or line.code_only_stripped.startswith("class  "):
        return True


def class_name_not_camel(line):
    if not line.code_only_stripped.startswith("class "):
        return
    camel_matcher = re.compile("[A-Z][A-Za-z]*$")
    open_paren_index = line.code_only_stripped.find("(")
    class_name = line.code_only_stripped[5:open_paren_index].lstrip()
    if re.match(camel_matcher, class_name):
        return
    return True


def function_name_not_snake(line):
    if not line.code_only_stripped.startswith("def "):
        return
    function_matcher = re.compile("[a-z0-9_]*$")
    open_paren_index = line.code_only_stripped.find("(")
    function_name = line.code_only_stripped[4:open_paren_index].lstrip()
    if re.match(function_matcher, function_name):
        return
    return True


def print_report(error_analysis):
    for error in error_analysis:
        error_message = error_code_to_text[error.code].format(*error.variables)
        print(f"{error.path_to_file}: Line {error.line}: {error.code} {error_message}")


def main():
    directory_or_path = sys.argv[1]
    files = get_file_list(directory_or_path)
    error_analysis = []
    for file in files:
        error_analysis.extend(analyze_code(file))
    print_report(error_analysis)


if __name__ == "__main__":
    main()
