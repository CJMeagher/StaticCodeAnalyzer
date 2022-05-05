import ast

tree = ast.parse(code)
print(ast.dump(tree))
