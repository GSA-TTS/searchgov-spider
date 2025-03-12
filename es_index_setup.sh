#!/bin/bash

# Set a maximum wait time (seconds) to avoid infinite loops
MAX_WAIT=120

wait_for_elasticsearch_health() {
    local counter=0
    echo "Waiting for Elasticsearch to be healthy..."

    until curl -sS "${ES_HOSTS}/_cat/health?h=status" | grep -E -q "(green|yellow)"; do
        if (( counter >= MAX_WAIT )); then
            echo "Error: Elasticsearch did not become healthy within ${MAX_WAIT} seconds."
            exit 1
        fi
        sleep 1
        ((counter++))
    done
    echo "Elasticsearch is healthy."
    return 0
}

create_es_index() {
    # Check if the index already exists
    if curl -sS --fail "${ES_HOSTS}/${SEARCHELASTIC_INDEX}" -o /dev/null 2>&1; then
        echo "Index ${SEARCHELASTIC_INDEX} already exists, skipping creation."
    else
        echo "Creating index '${SEARCHELASTIC_INDEX}'..."
        curl -X PUT "${ES_HOSTS}/${SEARCHELASTIC_INDEX}" \
             -H "Content-Type: application/json" \
             -d "@/es_index_settings.json"
        echo "Index '${SEARCHELASTIC_INDEX}' created successfully."
    fi
    return 0
}

main() {
    echo ES_HOSTS = $ES_HOSTS
    echo SEARCHELASTIC_INDEX = $SEARCHELASTIC_INDEX
    wait_for_elasticsearch_health
    create_es_index
}

main "$@"
