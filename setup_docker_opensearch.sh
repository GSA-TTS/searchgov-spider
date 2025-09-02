#!/bin/bash -i
set -euo pipefail
IFS=$'\n\t'

# Set a maximum wait time (seconds) to avoid infinite loops
MAX_WAIT=300

set_defaults_env() {
    # Set default values only if they are not already defined
    export SEARCHOPENSEARCH_INDEX="${SEARCHOPENSEARCH_INDEX:-\"development-i14y-documents-opensearch\"}"
    export OPENSEARCH_HOSTS="${OPENSEARCH_HOSTS:-\"http://localhost:9300\"}"
}

wait_for_opensearch_healt_old() {
    local counter=0
    echo "Waiting for Opensearch to be healthy..."
    until curl -sS "${OPENSEARCH_HOSTS}/_cat/health?h=status" | grep -E -q "(green|yellow)"; do
        if (( counter >= MAX_WAIT )); then
            echo "Error: Opensearch did not become healthy within ${MAX_WAIT} seconds."
            return 1
        fi
        sleep 1
        ((counter++))
    done
    echo "Opensearch is healthy."
    return 0
}

wait_for_opensearch_healt() {
    local max_wait=MAX_WAIT
    local opensearch_url=OPENSEARCH_HOSTS
    local counter=0
    local consecutive_failures=0
    
    echo "Waiting for OpenSearch to be healthy (timeout: ${max_wait}s)..."
    
    while (( counter < max_wait )); do
        if status=$(curl -sS --max-time 5 "${opensearch_url}/_cat/health?h=status" 2>/dev/null); then
            consecutive_failures=0
            if echo "$status" | grep -E -q "^(green|yellow)$"; then
                echo "OpenSearch is healthy (status: $(echo "$status" | tr -d '\n'))."
                return 0
            else
                echo "OpenSearch responding but not healthy yet (status: $(echo "$status" | tr -d '\n'))"
            fi
        else
            ((consecutive_failures++))
            if (( consecutive_failures >= 5 )); then
                echo "Error: OpenSearch unreachable for 5 consecutive attempts"
                return 1
            fi
            echo "OpenSearch not responding (attempt $((counter + 1))/${max_wait})"
        fi
        
        sleep 1
        ((counter++))
    done
    
    echo "Error: OpenSearch did not become healthy within ${max_wait} seconds."
    return 1
}

install_opensearch_plugins() {
    local plugins=(analysis-kuromoji analysis-icu analysis-smartcn)
    for plugin in "${plugins[@]}"; do
        # Use the opensearch-plugin executable
        if /usr/share/opensearch/bin/opensearch-plugin list | grep -q "${plugin}"; then
            echo "Plugin ${plugin} is already installed, skipping."
        else
            echo "Installing plugin: ${plugin}"
            # Use the opensearch-plugin executable
            /usr/share/opensearch/bin/opensearch-plugin install "${plugin}"
        fi
    done
}

create_opensearch_index() {
    # Check if the index already exists
    if curl -sS --fail "${OPENSEARCH_HOSTS}/${OPENSEARCH_INDEX}" -o /dev/null 2>&1; then
        echo "Index ${OPENSEARCH_INDEX} already exists, skipping creation."
    else
        echo "Creating index '${OPENSEARCH_INDEX}'..."
        curl -X PUT "${OPENSEARCH_HOSTS}/${OPENSEARCH_INDEX}" \
             -H "Content-Type: application/json" \
             -d "@opensearch_index_settings.json"
        echo "Index '${OPENSEARCH_INDEX}' created successfully."
    fi
    return 0
}

restart_opensearch() {
    local pid
    # Find the Opensearch Java process instead of the Elasticsearch one
    pid=$(pgrep -f "org.opensearch.bootstrap.OpenSearch" || true)
    if [ -n "$pid" ]; then
        echo "Killing Opensearch with PID(s): ${pid} to trigger container restart."
        sleep 10
        kill "$pid"
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

    if ! wait_for_opensearch_health; then
        echo "Exiting due to Opensearch health check failure."
        exit 1
    fi

    install_opensearch_plugins

    # Wait again after installing plugins, as it can cause a brief restart
    if ! wait_for_opensearch_health; then
        echo "Exiting due to Opensearch health check failure after plugin installation."
        exit 1
    fi

    create_opensearch_index
    restart_opensearch
}

main "$@"
