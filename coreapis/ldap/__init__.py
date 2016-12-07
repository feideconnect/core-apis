ORG_ATTRIBUTE_NAMES = {
    'eduOrgLegalName',
    'norEduOrgNIN',
    'mail',
    'telephoneNumber',
    'postalAddress',
    'eduOrgHomePageURI',
    'eduOrgIdentityAuthNPolicyURI',
    'eduOrgWhitePagesURI',
    'facsimileTelephoneNumber',
    'l',
    'labeledURI',
    'norEduOrgAcronym',
    'norEduOrgUniqueIdentifier',
    'postalCode',
    'postOfficeBox',
    'street',
}

ORG_UNIT_ATTRIBUTE_NAMES = {
    'norEduOrgUnitUniqueIdentifier',
    'ou',
}

GROUP_PERSON_ATTRIBUTES = (
    'eduPersonOrgDN',
    'eduPersonOrgUnitDN',
    'eduPersonPrimaryOrgUnitDN',
    'eduPersonEntitlement',
    'eduPersonAffiliation',
    'eduPersonPrimaryAffiliation',
    'title',
)

PEOPLE_SEARCH_ATTRIBUTES = ['displayName', 'eduPersonPrincipalName']


PERSON_ATTRIBUTES = set(GROUP_PERSON_ATTRIBUTES) | set(PEOPLE_SEARCH_ATTRIBUTES)

REQUIRED_PERSON_ATTRIBUTES = [
    'eduPersonOrgDN',
    'eduPersonAffiliation',
    'displayName',
    'eduPersonPrincipalName',
]

REQUIRED_ORG_ATTRIBUTES = [
    'eduOrgLegalName',
]

REQUIRED_ORG_UNIT_ATTRIBUTES = [
    'norEduOrgUnitUniqueIdentifier',
    'ou',
]
