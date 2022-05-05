import ast

tree = ast.parse(code)


class ImportLister(ast.NodeVisitor):
    def visit_Import(self, node):
        for name in node.names:
            print(name.name)


ImportLister().visit(tree)
