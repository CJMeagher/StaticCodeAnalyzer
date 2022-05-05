import ast

expression = "(34 + 6) * (23**2 - 7 + 45**2)"

tree = ast.parse(expression)
nodes = list(ast.walk(tree))
print(len(nodes))


