def is_gkscopename(name):
    return name.startswith('gk_')


def filter_missing_mainscope(scopes):
    return [scope for scope in scopes if gk_mainscope(scope) in scopes]


def gk_mainscope(name):
    if not is_gkscopename(name):
        return name
    nameparts = name.split('_')
    if len(nameparts) == 2:
        return name
    return "_".join(nameparts[:2])


def has_gkscope_match(scope, gkscopes):
    return any(scope == gkscope or scope.startswith(gkscope + '_')
               for gkscope in gkscopes)
