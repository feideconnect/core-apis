from coreapis.utils import (translatable, pick_lang)

SIMPLESCOPE_TMPL = {
    "nb": "FC-klienten {} ønsker tilgang til API {}",
    "en": "FC client {} wants to access API(s) {}",
}

APIGK_TMPL = {
    "nb": "FC-klienten {} ønsker tilgang til API {}, subscope {}",
    "en": "FC client {} wants to access API {}, subscope {}",
}

CLIENT_TMPL_NB = '''
Informasjon om klienten:
eier:         {}
organisasjon: {}
URL:          {}
beskrivelse:  {}
'''

CLIENT_TMPL_EN = '''
Client information:
owner:        {}
organization: {}
URL:          {}
description:  {}
'''

CLIENT_TMPL = {"nb": CLIENT_TMPL_NB, "en": CLIENT_TMPL_EN}

DASHBOARDMSG = {
    "nb": "Du kan behandle forespørselen i FeideConnect dashbord på URLen nedenfor",
    "en": "You may handle the request in the FeideConnect dashboard at the URL below",
}

CONNECTMSG = {
    "nb": "Les mer om FeideConnect på",
    "en": "Read more about FeideConnect at",
}

DASHBOARD_URL_TMPL = "https://dashboard.feideconnect.no/#!/{}/apigk/{}/edit/tabRequests"

FC_URL = "http://feideconnect.no"


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
        return self.translate(translatable(SIMPLESCOPE_TMPL))

    def get_apigk_tmpl(self):
        return self.translate(translatable(APIGK_TMPL))

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
        client_tmpl = self.translate(translatable(CLIENT_TMPL))
        name = self.client['owner']['name']
        try:
            orgname = self.translate(self.client['organization']['name'])
        except:
            orgname = ''
        descr = self.translate(self.client['descr'])
        uris = ', '.join(self.client['redirect_uri'])
        return client_tmpl.format(name, orgname, uris, descr)

    def get_dashboard_url(self):
        orgid = self.apigk['organization']
        if not orgid:
            orgid = '_'
        base = self.scopes[0].split('_')[1]
        return DASHBOARD_URL_TMPL.format(orgid, base)

    def get_fc_help(self):
        dashboardmsg = self.translate(translatable(DASHBOARDMSG))
        connectmsg = self.translate(translatable(CONNECTMSG))
        if self.apigk:
            return "{}:\n{}\n{} {}".format(dashboardmsg, self.get_dashboard_url(),
                                           connectmsg, FC_URL)
        else:
            return "{} {}".format(connectmsg, FC_URL)

    def get_body(self):
        tmpl = '''
{}
{}
{}
'''
        return tmpl.format(self.get_subject(),
                           self.get_client_info(),
                           self.get_fc_help())