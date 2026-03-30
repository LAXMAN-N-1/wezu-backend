import ast, os, glob

def analyze_file(filepath):
    with open(filepath, 'r') as f:
        src = f.read()
    try:
        tree = ast.parse(src)
    except Exception:
        return []
        
    issues = []
    
    class ForLoopVisitor(ast.NodeVisitor):
        def __init__(self):
            self.in_for = False
            self.for_node = None
            
        def visit_For(self, node):
            old_in_for = self.in_for
            old_for_node = self.for_node
            self.in_for = True
            self.for_node = node
            self.generic_visit(node)
            self.in_for = old_in_for
            self.for_node = old_for_node

        def visit_Call(self, node):
            if self.in_for:
                if isinstance(node.func, ast.Attribute) and getattr(node.func.value, 'id', '') == 'db':
                    if node.func.attr in ('get', 'exec'):
                        issues.append({
                            'line': node.lineno,
                            'func': f'db.{node.func.attr}'
                        })
            self.generic_visit(node)
            
    ForLoopVisitor().visit(tree)
    return issues

files = glob.glob('/Users/murari/Desktop/wezu_battery_app/backend/app/api/admin/*.py')
total_issues = 0
for f in files:
    res = analyze_file(f)
    if res:
        name = os.path.basename(f)
        print(f"File: {name} ({len(res)} N+1 queries found)")
        for r in res:
            print(f"  Line {r['line']}: {r['func']} inside loop")
        total_issues += len(res)
print(f"\nTotal N+1 instances: {total_issues}")
