# Logins statistics API for Dataporten

To test the API, obtain an authentication token and

    $ export TOKEN=...

## Get statistics records for a client

    curl -H "Authorization: Bearer $TOKEN" 'https://api.dataporten.no/clientadm/clients/<client-id>/logins_stats/'

    [{"login_count": 5,
      "date": "2016-03-02",
      "timeslot": "2016-03-02T14:06:00Z",
      "authsource": "feide:uninett.no"
    },
	...
	]

    curl -H "Authorization: Bearer $TOKEN" \
	'https://api.dataporten.no/clientadm/clients/<client-id>/logins_stats/?end_date=2016-03-15'

    curl -H "Authorization: Bearer $TOKEN" \
	'https://api.dataporten.no/clientadm/clients/<client-id>/logins_stats/?num_days=2'

    curl -H "Authorization: Bearer $TOKEN" \
	'https://api.dataporten.no/clientadm/clients/<client-id>/logins_stats/?authsource=feide:uninett.no'

### Description

Returns a list of statistics records

### Parameters

- `client-id`: The client id. Part of url.
- `end_date`: Final date to be included. Optional parameter. ISO 8601
  date string. Defaults to current date.
- `num_days`: Number of days to report. Optional parameter. Integer
  string. Defaults to 1. Must not be above upper limit. Limit is given in 400 body
  if it is exceeded.
- `authsource`: Authentication source to include in report. Optional
  parameter. String. Default is no filtering.

### Return values

- `200 OK`: When the request is successful this code is returned and
  the statistics are returned as json in the response body.
- `400 Bad Request`: Returned if some parameter has a  malformed or
  illegal value.
- `403 Forbidden`: User is not owner or administrator of the client.
