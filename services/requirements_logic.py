"""Bounded AND/OR expressions parsed with Python's AST, never eval or execution."""
import ast
import re


def compile_clause(text, normalize):
    if len(text) > 4096 or not re.search(r'\bor\b', text, re.IGNORECASE):
        return None
    names, source = {}, []
    nesting = 0
    for part in re.split(r'(\(|\)|\b(?:and/or|and|or|plus)\b|[,;&])', text, flags=re.IGNORECASE):
        part = part.strip()
        if not part:
            continue
        lower = part.lower()
        if lower in ('and', 'plus', ',', ';', '&'):
            source.append('and')
        elif lower in ('or', 'and/or'):
            source.append('or')
        elif part in ('(', ')'):
            nesting += 1 if part == '(' else -1
            if not 0 <= nesting <= 16:
                return None
            source.append(part)
        else:
            value = normalize(re.sub(r'^(?:either|both)\s+', '', part, flags=re.IGNORECASE))
            if not value or len(names) >= 64:
                return None
            name = 'term' + str(len(names))
            names[name] = value
            source.append(name)
    if nesting:
        return None
    try:
        tree = ast.parse(' '.join(source), mode='eval')
        if sum(1 for _ in ast.walk(tree)) > 192:
            return None

        def convert(node, depth=0):
            if depth > 16:
                raise ValueError('Expression is too deep')
            if isinstance(node, ast.Name) and node.id in names:
                return {'term': names[node.id]}
            if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
                return {'op': 'all' if isinstance(node.op, ast.And) else 'any',
                        'items': [convert(item, depth + 1) for item in node.values]}
            raise ValueError('Unsupported expression')
        return convert(tree.body)
    except (SyntaxError, ValueError, RecursionError):
        return None


def evaluate(expression, predicate, depth=0):
    if not isinstance(expression, dict) or depth > 16:
        return False
    if isinstance(expression.get('term'), str):
        return bool(predicate(expression['term']))
    items = expression.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 64:
        return False
    if expression.get('op') == 'all':
        return all(evaluate(item, predicate, depth + 1) for item in items)
    if expression.get('op') == 'any':
        return any(evaluate(item, predicate, depth + 1) for item in items)
    return False


def sql(expression, leaf, depth=0):
    if not isinstance(expression, dict) or depth > 16:
        return 'FALSE', []
    if isinstance(expression.get('term'), str):
        return leaf(expression['term'])
    items = expression.get('items')
    if expression.get('op') not in ('all', 'any') or not isinstance(items, list) or not 1 <= len(items) <= 64:
        return 'FALSE', []
    parts, params = [], []
    for item in items:
        part, values = sql(item, leaf, depth + 1)
        parts.append(part)
        params.extend(values)
    separator = ' AND ' if expression['op'] == 'all' else ' OR '
    return '(' + separator.join(parts) + ')', params


def label(expression, depth=0):
    if not isinstance(expression, dict) or depth > 16:
        return 'Unverified requirement'
    if isinstance(expression.get('term'), str):
        return expression['term']
    items = expression.get('items')
    if expression.get('op') not in ('all', 'any') or not isinstance(items, list) or not 1 <= len(items) <= 64:
        return 'Unverified requirement'
    separator = ' and ' if expression.get('op') == 'all' else ' or '
    return '(' + separator.join(label(item, depth + 1) for item in items) + ')'
