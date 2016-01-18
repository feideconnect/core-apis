from coreapis.utils import EmailNotifier, json_load, LogWrapper, ValidationError
from .scope_request_notification import ScopeRequestNotification
from coreapis.scopes import filter_missing_mainscope, gk_mainscope, is_gkscopename

EMAIL_NOTIFICATIONS_CONFIG_KEY = 'notifications.email.'


def get_scopedefs(filename):
    return json_load(filename, fallback={})


class ScopesManager(object):
    def __init__(self, settings, session, get_public_info):
        self.log = LogWrapper('scopes.ScopesManager')
        scopedefs_file = settings.get('clientadm_scopedefs_file')
        system_moderator = settings.get('clientadm_system_moderator', '')
        self.scopedefs = get_scopedefs(scopedefs_file)
        self.session = session
        self.system_moderator = system_moderator
        self.get_public_info = get_public_info
        self.email_notification_settings = {'enabled': False}
        self.email_notification_settings.update({
            '.'.join(k.split('.')[2:]): v
            for k, v in settings.items()
            if k.startswith(EMAIL_NOTIFICATIONS_CONFIG_KEY)
        })

    def add_scope_if_approved(self, client, scopedef, scope):
        try:
            if scopedef['policy']['auto']:
                self.log.debug('Accept scope', scope=scope)
                client['scopes'].append(scope)
        except KeyError:
            pass

    def handle_gksubscope_request(self, client, scope, subname, subscopes):
        try:
            scopedef = subscopes[subname]
        except:
            raise ValidationError('invalid scope: {}'.format(scope))
        self.add_scope_if_approved(client, scopedef, scope)

    def handle_scope_request(self, client, scope):
        if is_gkscopename(scope):
            self.handle_gkscope_request(client, scope)
        elif not scope in self.scopedefs:
            raise ValidationError('invalid scope: {}'.format(scope))
        else:
            self.add_scope_if_approved(client, self.scopedefs[scope], scope)

    def get_gk_moderator(self, scope):
        apigk = self.scope_to_gk(scope)
        owner = self.session.get_user_by_id(apigk['owner'])
        try:
            return list(owner['email'].values())[0]
        except (AttributeError, IndexError):
            return None

    def get_moderator(self, scope):
        if is_gkscopename(scope):
            return self.get_gk_moderator(scope)
        else:
            return self.system_moderator

    # Group scopes by apigk, with a separate bucket for built-in scopes
    # Example:
    # {'system': {systemscopes},
    #  'gk_foo': {'gk_foo', gk_foo_bar'},
    #  'gk_baz': {'gk_baz1}}
    def get_scopes_by_base(self, modscopes):
        ret = {}
        for scope in modscopes:
            if is_gkscopename(scope):
                base = gk_mainscope(scope)
            else:
                base = 'system'
            ret[base] = ret.get(base, set())
            ret[base].add(scope)
        return ret

    def notify_moderator(self, moderator, client, scopes):
        apigk = None
        first_scope = list(scopes)[0]
        if is_gkscopename(first_scope):
            apigk = self.scope_to_gk(first_scope)
        notification = ScopeRequestNotification(self.get_public_info(client), scopes, apigk)
        subject = notification.get_subject()
        body = notification.get_body()
        self.log.debug('notify_moderator', moderator=moderator, subject=subject)
        EmailNotifier(self.email_notification_settings).notify(moderator, subject, body)

    def notify_moderators(self, client):
        modscopes = set(client['scopes_requested']).difference(set(client['scopes']))
        for base, scopes in self.get_scopes_by_base(modscopes).items():
            mod = self.get_moderator(base)
            if mod and len(mod) > 0:
                self.notify_moderator(mod, client, scopes)
            else:
                self.log.debug('No moderator address', base=base, mod=mod)

    def handle_gkscope_request(self, client, scope):
        nameparts = scope.split('_')
        gkname = nameparts[1]
        try:
            apigk = self.session.get_apigk(gkname)
            scopedef = apigk.get('scopedef', {})
            if not scopedef:
                scopedef = {}
        except:
            raise ValidationError('invalid scope: {}'.format(scope))
        if str(apigk['owner']) == str(client['owner']):
            client['scopes'].append(scope)
        elif len(nameparts) > 2:
            if 'subscopes' in scopedef:
                subname = nameparts[2]
                self.handle_gksubscope_request(client, scope, subname, scopedef['subscopes'])
            else:
                raise ValidationError('invalid scope: {}'.format(scope))
        else:
            self.add_scope_if_approved(client, scopedef, scope)

    def scope_to_gk(self, scopename):
        try:
            nameparts = scopename.split('_')
            gkname = nameparts[1]
            return self.session.get_apigk(gkname)
        except KeyError:
            return None

    def list_public_scopes(self):
        return {k: v for k, v in self.scopedefs.items() if v.get('public', False)}

    def handle_update(self, client):
        client['scopes_requested'] = filter_missing_mainscope(client['scopes_requested'])
        client['scopes'] = list(set(client['scopes']).intersection(set(client['scopes_requested'])))
        for scope in set(client['scopes_requested']).difference(set(client['scopes'])):
            self.handle_scope_request(client, scope)
