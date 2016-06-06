from coreapis.utils import (
    EmailNotifier, json_load, LogWrapper, ValidationError, PRIV_PLATFORM_ADMIN)
from .scope_request_notification import ScopeRequestNotification
from coreapis.scopes import filter_missing_mainscope, gk_mainscope, is_gkscopename

EMAIL_NOTIFICATIONS_CONFIG_KEY = 'notifications.email.'


def get_scopedefs(filename):
    return json_load(filename, fallback={})


class ScopesManager(object):
    def __init__(self, settings, session, get_public_info, for_apigk):
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
        self.for_apigk = for_apigk

    def _add_scope_if_approved(self, target, scopedef, scope, privileges):
        try:
            if PRIV_PLATFORM_ADMIN in privileges or scopedef['policy']['auto']:
                self.log.debug('Accept scope', scope=scope)
                target['scopes'].append(scope)
        except KeyError:
            pass

    def _handle_gksubscope_request(self, target, scope, subname, subscopes, privileges):
        try:
            scopedef = subscopes[subname]
        except:
            raise ValidationError('invalid scope: {}'.format(scope))
        self._add_scope_if_approved(target, scopedef, scope, privileges)

    def _handle_scope_request(self, target, scope, privileges):
        if is_gkscopename(scope):
            self._handle_gkscope_request(target, scope, privileges)
        elif scope not in self.scopedefs:
            raise ValidationError('invalid scope: {}'.format(scope))
        else:
            self._add_scope_if_approved(target, self.scopedefs[scope], scope, privileges)

    def _get_gk_moderator(self, scope):
        apigk = self.scope_to_gk(scope)
        owner = self.session.get_user_by_id(apigk['owner'])
        try:
            return list(owner['email'].values())[0]
        except (AttributeError, IndexError):
            return None

    def _get_moderator(self, scope):
        if is_gkscopename(scope):
            return self._get_gk_moderator(scope)
        else:
            return self.system_moderator

    # Group scopes by apigk, with a separate bucket for built-in scopes
    # Example:
    # {'system': {systemscopes},
    #  'gk_foo': {'gk_foo', gk_foo_bar'},
    #  'gk_baz': {'gk_baz1}}
    def _get_scopes_by_base(self, modscopes):
        ret = {}
        for scope in modscopes:
            if is_gkscopename(scope):
                base = gk_mainscope(scope)
            else:
                base = 'system'
            ret[base] = ret.get(base, set())
            ret[base].add(scope)
        return ret

    def _notify_moderator(self, moderator, target, scopes):
        apigk = None
        first_scope = list(scopes)[0]
        if is_gkscopename(first_scope):
            apigk = self.scope_to_gk(first_scope)
        notification = ScopeRequestNotification(self.get_public_info(target), scopes, apigk)
        subject = notification.get_subject()
        body = notification.get_body()
        self.log.debug('notify_moderator', moderator=moderator, subject=subject)
        EmailNotifier(self.email_notification_settings).notify(moderator, subject, body)

    def _handle_gkscope_request(self, target, scope, privileges):
        nameparts = scope.split('_')
        gkname = nameparts[1]
        try:
            apigk = self.session.get_apigk(gkname)
            scopedef = apigk.get('scopedef', {})
            if not scopedef:
                scopedef = {}
        except:
            raise ValidationError('invalid scope: {}'.format(scope))
        if str(apigk['owner']) == str(target['owner']):
            target['scopes'].append(scope)
        elif len(nameparts) > 2:
            if 'subscopes' in scopedef:
                subname = nameparts[2]
                self._handle_gksubscope_request(target, scope, subname,
                                                scopedef['subscopes'], privileges)
            else:
                raise ValidationError('invalid scope: {}'.format(scope))
        else:
            self._add_scope_if_approved(target, scopedef, scope, privileges)

    def _scope_allowed_for_apigk(self, scope):
        if is_gkscopename(scope):
            return False
        return not self.scopedefs.get(scope, {}).get('client_only', False)

    def notify_moderators(self, target):
        modscopes = set(target['scopes_requested']).difference(set(target['scopes']))
        for base, scopes in self._get_scopes_by_base(modscopes).items():
            mod = self._get_moderator(base)
            if mod and len(mod) > 0:
                self._notify_moderator(mod, target, scopes)
            else:
                self.log.debug('No moderator address', base=base, mod=mod)

    def scope_to_gk(self, scopename):
        try:
            nameparts = scopename.split('_')
            gkname = nameparts[1]
            return self.session.get_apigk(gkname)
        except KeyError:
            return None

    def list_public_scopes(self):
        return {k: v for k, v in self.scopedefs.items() if v.get('public', False)}

    def list_scopes(self):
        return {k: v for k, v in self.scopedefs.items()}

    def handle_update(self, target, privileges):
        if self.for_apigk:
            target['scopes_requested'] = [scope for scope in target['scopes_requested']
                                          if self._scope_allowed_for_apigk(scope)]
        else:
            target['scopes_requested'] = filter_missing_mainscope(target['scopes_requested'])
        target['scopes'] = list(set(target['scopes']).intersection(set(target['scopes_requested'])))
        for scope in set(target['scopes_requested']).difference(set(target['scopes'])):
            self._handle_scope_request(target, scope, privileges)
