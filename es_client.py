"""
es_client.py
------------
Builds the Elasticsearch client from environment variables, so the SAME code
works whether you are pointing at a local Elasticsearch (security on or off)
or at a hosted deployment such as Elastic Cloud.

Environment variables (all optional, with sensible defaults):

  ES_URL       Elasticsearch URL.
               Local, security ON  (8.x default):  https://localhost:9200
               Local, security OFF:                http://localhost:9200
               Elastic Cloud:                       the endpoint shown on
                                                     your deployment's page,
                                                     e.g.
                                                     https://my-deployment.es.us-east-1.aws.elastic.cloud:443

  ES_API_KEY   An Elastic Cloud "encoded" API key (the long base64-looking
               string Elastic Cloud's connection-details panel gives you).
               If this is set, it's used instead of ES_USERNAME/ES_PASSWORD.
               This is the easiest option when using Elastic Cloud.

  ES_USERNAME  Default: elastic. Only used if ES_API_KEY is NOT set.
  ES_PASSWORD  Password for the 'elastic' user. Only used if ES_API_KEY is
               NOT set. REQUIRED when security is ON and no API key is used.
  ES_CA_CERT   Path to Elasticsearch's http_ca.crt (recommended with HTTPS
               for a *local* install). Not needed for Elastic Cloud — its
               certificate is already publicly trusted.
               Usually at:  <es-install-dir>/config/certs/http_ca.crt

If you connect over HTTPS without ES_CA_CERT, TLS certificate verification is
turned OFF — convenient for local learning, but not for production. (Elastic
Cloud connections always use a trusted certificate, so this never applies to
Elastic Cloud.)
"""

import os
from elasticsearch import Elasticsearch


def get_client() -> Elasticsearch:
    url = os.environ.get("ES_URL", "https://localhost:9200")
    api_key = os.environ.get("ES_API_KEY")
    username = os.environ.get("ES_USERNAME", "elastic")
    password = os.environ.get("ES_PASSWORD")
    ca_cert = os.environ.get("ES_CA_CERT")

    kwargs = {}

    # Authentication — needed whenever security is enabled (always true for
    # Elastic Cloud, optional for a local install). Prefer an API key if one
    # is provided; otherwise fall back to username/password.
    if api_key:
        kwargs["api_key"] = api_key
    elif password:
        kwargs["basic_auth"] = (username, password)

    # TLS handling for HTTPS endpoints.
    if url.lower().startswith("https"):
        if ca_cert:
            kwargs["ca_certs"] = ca_cert          # verify against a known CA
        else:
            kwargs["verify_certs"] = False        # skip verification (fine
            kwargs["ssl_show_warn"] = False       # for Elastic Cloud's own
                                                   # publicly trusted cert,
                                                   # and for local learning)

    return Elasticsearch(url, **kwargs)
