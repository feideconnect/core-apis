from coreapis.utils import (translatable, pick_lang)


class ScopeRequestNotification(object):
    def __init__(self, client, scopes, apigk, lang='nb'):
        self.client = client
        self.scopes = list(scopes)
        self.apigk = apigk
        self.lang = lang

    def matcher(self, data):
        return lambda data: self.lang if self.lang in data else None

    def translate(self, data):
        return pick_lang(self.matcher(data), data)

    def get_simplescope_tmpl(self):
        return self.translate(translatable({
            "nb": "FC-klienten {} ønsker tilgang til API {}",
            "en": "FC client {} wants to access API(s) {}",
        }))

    def get_apigk_tmpl(self):
        return self.translate(translatable({
            "nb": "FC-klienten {} ønsker tilgang til API {}, subscope {}",
            "en": "FC client {} wants to access API {}, subscope {}",
        }))

    def get_subject(self):
        firstscope = self.scopes[0]
        name = self.client['name']
        if self.apigk:
            base = firstscope.split('_')[1]
            subscopes = [scope.split('_')[2]
                         for scope in self.scopes
                         if len(scope.split('_')) > 2]
            if len(subscopes) > 0:
                return self.get_apigk_tmpl().format(name, base, ', '.join(subscopes))
            else:
                return self.get_simplescope_tmpl().format(name, base)
        else:
            return self.get_simplescope_tmpl().format(name, firstscope)

    def get_client_info(self):
        tmpl_nb = '''
Informasjon om klienten:
eier:         {}
organisasjon: {}
URL:          {}
beskrivelse:  {}
'''
        tmpl_en = '''
Client information:
owner:        {}
organization: {}
URL:          {}
description:  {}
'''
        tmpl = self.translate(translatable({"nb": tmpl_nb, "en": tmpl_en}))
        name = self.client['owner']['name']
        try:
            orgname = self.translate(self.client['organization']['name'])
        except:
            orgname = ''
        descr = self.translate(self.client['descr'])
        uris = ', '.join(self.client['redirect_uri'])
        return tmpl.format(name, orgname, uris, descr)

    def get_dashboard_url(self):
        tmpl = 'https://dashboard.feideconnect.no/#!/{}/apigk/{}/edit/tabRequests'
        orgid = self.apigk['organization']
        if not orgid:
            orgid = '_'
        base = self.scopes[0].split('_')[1]
        return tmpl.format(orgid, base)

    def get_fc_help(self):
        dashboardmsg = self.translate(translatable({
            "nb": "Du kan behandle forespørselen i FeideConnect dashbord på URLen nedenfor",
            "en": "You may handle the request in the FeideConnect dashboard at the URL below",
        }))
        connectmsg = self.translate(translatable({
            "nb": "Les mer om FeideConnect på",
            "en": "Read more about FeideConnect at",
        }))
        fcurl = 'http://feideconnect.no'
        if self.apigk:
            return "{}:\n{}\n{} {}".format(dashboardmsg, self.get_dashboard_url(),
                                           connectmsg, fcurl)
        else:
            return "{} {}".format(connectmsg, fcurl)
            return ''

    def get_body(self):
        tmpl = '''
{}
{}
{}
'''
        return tmpl.format(self.get_subject(),
                           self.get_client_info(),
                           self.get_fc_help())
