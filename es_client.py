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
                                                     your deployment's
                                                     "Manage" page, e.g.
                                                     https://my-deployment.es.us-east-1.aws.elastic.cloud:443

  ES_USERNAME  Default: elastic
  ES_PASSWORD  Password for the 'elastic' user. REQUIRED when security is ON
               (this includes every Elastic Cloud deployment).
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
    username = os.environ.get("ES_USERNAME", "elastic")
    password = os.environ.get("ES_PASSWORD")
    ca_cert = os.environ.get("ES_CA_CERT")

    kwargs = {}

    # Authentication — needed whenever security is enabled (always true for
    # Elastic Cloud, optional for a local install).
    if password:
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
