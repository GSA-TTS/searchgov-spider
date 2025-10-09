#!/bin/bash

set_defaults_env() {
    # Set default values only if they are not already defined
    export SEARCHELASTIC_INDEX="${SEARCHELASTIC_INDEX:-development-i14y-documents-searchgov}"
    export ES_HOSTS="${ES_HOSTS:-http://localhost:9200}"
    export OPENSEARCH_SEARCH_INDEX="${OPENSEARCH_SEARCH_INDEX:-development-i14y-documents-searchgov}"
    export OPENSEARCH_SEARCH_HOST="${OPENSEARCH_SEARCH_HOST:-http://localhost:9300}"
}


create_es_index() {
    # Check if the index already exists
    if curl -sS --fail "${ES_HOSTS}/${SEARCHELASTIC_INDEX}" > /dev/null 2>&1; then
        echo "Elasticsearch Index ${SEARCHELASTIC_INDEX} already exists, skipping creation."
    else
        echo "Creating index '${SEARCHELASTIC_INDEX}'..."
        curl -X PUT "${ES_HOSTS}/${SEARCHELASTIC_INDEX}" \
             -H "Content-Type: application/json" \
             -d "@es_index_settings.json"
        echo -e "\nElasticsearch Index '${SEARCHELASTIC_INDEX}' created successfully."
    fi
    return 0
}

create_opensearch_index() {
    # Check if the index already exists
    if curl -sS --fail "${OPENSEARCH_SEARCH_HOST}/${OPENSEARCH_SEARCH_INDEX}" > /dev/null 2>&1; then
        echo "Opensearch Index ${OPENSEARCH_SEARCH_INDEX} already exists, skipping creation."
    else
        echo "Creating index '${OPENSEARCH_SEARCH_INDEX}' on host ${OPENSEARCH_SEARCH_HOST}"
        curl -XPUT "${OPENSEARCH_SEARCH_HOST}/${OPENSEARCH_SEARCH_INDEX}" \
             -H "Content-Type: application/json" \
             -d "@opensearch_index_settings.json"
        echo -e "\nOpensearch Index '${OPENSEARCH_SEARCH_INDEX}' created successfully."
    fi
    return 0
}


main() {
    # Load environment variables from .env
    if [ -f .env ]; then
        set -o allexport
        source .env
        set +o allexport
    fi

    set_defaults_env
    create_es_index
    create_opensearch_index
}

main "$@"
