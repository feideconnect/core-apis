# Organization API for Feide Connect

## List public information about all organizations

    $ curl 'https://api.feideconnect.no/orgs/'

    [{"type": ["home_organization", "service_provider", "upper_secondary"],
        "id": "fc:org:t-fk.no", "name": "Telemark County Council",
        "organization_number": "no940192226", "realm": "t-fk.no"},
     ...]

## Show public information about one organization

    $ curl 'https://api.feideconnect.no/orgs/<org-id>'

    {"type": ["home_organization","service_provider","upper_secondary"],
    "id": "fc:org:t-fk.no", "name": "Telemark County Council",
    "organization_number": "no940192226","realm": "t-fk.no"}

### Required parameters

- `<org-id>`: Must be the `id` of an organization in the format returned by the organization list.

## Get an organizations logo

    $ curl 'https://api.feideconnect.no/orgs/<org-id>/logo'|display
