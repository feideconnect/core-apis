def get_feideids(user):
    return set((id.split(':', 1)[1]
                for id in user['userid_sec']
                if id.startswith('feide:') and '@' in id))


def get_feideid(user):
    feideids = get_feideids(user)
    if not feideids:
        raise RuntimeError('could not find feide id')
    feideid = feideids.pop()
    return feideid
