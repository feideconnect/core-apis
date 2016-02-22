# Organization API for Dataporten

## List public information about all organizations

    $ curl 'https://api.dataporten.no/orgs/'

    [{"type": ["home_organization", "service_provider", "upper_secondary"],
        "id": "fc:org:t-fk.no", "name": "Telemark County Council",
        "organization_number": "no940192226", "realm": "t-fk.no"},
     ...]

### Query parameters

- `peoplesearch`: When set to `true`, returns only organizations with peoplesearch available. When set to `false` returns only organizations without peoplesearch. Otherwise returns all organizations

## Show public information about one organization

    $ curl 'https://api.dataporten.no/orgs/<org-id>'

    {"type": ["home_organization","service_provider","upper_secondary"],
    "id": "fc:org:t-fk.no", "name": "Telemark County Council",
    "organization_number": "no940192226","realm": "t-fk.no"}

### Required parameters

- `<org-id>`: Must be the `id` of an organization in the format returned by the organization list.

## Get an organization's logo

    $ curl 'https://api.dataporten.no/orgs/<org-id>/logo'|display
