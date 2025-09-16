#!/usr/bin/env bash

set -o pipefail

# Load environment variables from .env
env_file=".env"
if [ -f "$env_file" ]; then
    set -o allexport
    source "$env_file"
    set +o allexport
else
    warn "No $env_file found. Creating an empty one and using defaults."
    # Create an empty .env file, so docker-compose doesn't fail
    touch "$env_file"
    chmod +x "$env_file"
fi

# ---- both compose YML files ----
ES_COMPOSE="docker-compose.yml"
OPENSEARCH_COMPOSE="docker-compose.opensearch.yml"

ES_HOST_PORTS=(9200 5601)
OPENSEARCH_HOST_PORTS=(9300 5602)

ES_HEALTH_URL="${ES_HOST:-http://localhost:9200}"
OPENSEARCH_HEALTH_URL="${OPENSEARCH_HOST:-http://localhost:9300}"

# how long to wait (seconds) for each service to become healthy
WAIT_TIMEOUT=180
WAIT_INTERVAL=5

# ---- helpers ----
log()  { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; }
err()  { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*"; }
die()  { err "$*"; exit 1; }

# Use docker compose if available, otherwise docker-compose
detect_compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
  else
    die "Neither 'docker compose' nor 'docker-compose' was found in PATH. Please install Docker Compose."
  fi
}

check_files() {
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  ES_COMPOSE_PATH="$script_dir/$ES_COMPOSE"
  OPENSEARCH_COMPOSE_PATH="$script_dir/$OPENSEARCH_COMPOSE"

  [[ -f "$ES_COMPOSE_PATH" ]] || die "Missing $ES_COMPOSE_PATH"
  [[ -f "$OPENSEARCH_COMPOSE_PATH" ]] || die "Missing $OPENSEARCH_COMPOSE_PATH"
}

# test if a host port is open (returns 0 if open)
host_port_open() {
  local port=$1
  # using bash /dev/tcp (works in bash)
  (echo >/dev/tcp/127.0.0.1/"$port") &>/dev/null
}

# Find docker container (name) that publishes a given host port (if any)
container_publishing_port() {
  local port=$1
  # list docker ps with Ports and Names, look for host port mapping like 0.0.0.0:9200->9200/tcp or :::9200->9200/tcp
  docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null | awk -v p=":$port" '
  {
    name=$1;
    $1="";
    ports=$0;
    if (index(ports, p) > 0) {
      print name;
      exit;
    }
  }'
}

# run compose action with proper command array
run_compose() {
  "${COMPOSE_CMD[@]}" -f "$1" "${@:2}"
}

# stop & remove compose stack
compose_down() {
  local file="$1"
  log "Tearing down compose stack: $file"
  if ! run_compose "$file" down --remove-orphans; then
    warn "compose down reported an error for $file (continuing). Showing last 100 lines of logs:"
    run_compose "$file" logs --tail 100 || true
  fi
}

# bring up compose stack
compose_up() {
  local file="$1"
  log "Starting compose stack: $file"
  if ! run_compose "$file" up -d --force-recreate --remove-orphans; then
    err "Failed to start compose stack: $file"
    run_compose "$file" logs --tail 200 || true
    return 1
  fi
  return 0
}

# wait until HTTP health endpoint returns a 2xx response or timeout
wait_for_health() {
  local url=$1
  local timeout=$2
  local interval=$3
  log "Waiting up to ${timeout}s for $url to respond..."
  local start_ts now code
  start_ts=$(date +%s)
  while true; do
    # use curl to check status code
    if command -v curl >/dev/null 2>&1; then
      code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 "$url" 2>/dev/null || echo "000")
    else
      # fallback to /dev/tcp probe (only checks TCP) — treat as success if TCP accepted
      local port="${url##*:}"
      port="${port%%/*}"  # strip any path if present
      if (echo >/dev/tcp/127.0.0.1/"$port") &>/dev/null; then
        code=200
      else
        code=000
      fi
    fi

    if [[ "$code" =~ ^2[0-9][0-9]$ ]]; then
      log "$url is responding (HTTP $code)."
      return 0
    fi

    now=$(date +%s)
    if (( now - start_ts >= timeout )); then
      err "Timed out waiting for $url (last HTTP status: $code)."
      return 2
    fi
    sleep "$interval"
  done
}

# ---- main ----
detect_compose_cmd
check_files

log "Using compose command: ${COMPOSE_CMD[*]}"
log "Compose files: $ES_COMPOSE_PATH , $OPENSEARCH_COMPOSE_PATH"

# 1) Check host ports for conflicts
log "Checking required host ports for conflicts..."
for p in "${ES_HOST_PORTS[@]}"; do
  if host_port_open "$p"; then
    container_name="$(container_publishing_port "$p")"
    if [[ -n "$container_name" ]]; then
      # port used by a docker container. If it's one of our expected names, we'll stop it below
      log "Host port $p is in use by container: $container_name"
    else
      die "Host port $p is in use by a non-docker process. Please free port $p."
    fi
  else
    log "Host port $p is free."
  fi
done

for p in "${OPENSEARCH_HOST_PORTS[@]}"; do
  if host_port_open "$p"; then
    container_name="$(container_publishing_port "$p")"
    if [[ -n "$container_name" ]]; then
      log "Host port $p is in use by container: $container_name"
    else
      die "Host port $p is in use by a non-docker process. Please free port $p or change your compose files before continuing."
    fi
  else
    log "Host port $p is free."
  fi
done

# 2) Stop (down) each compose stack if present
log "Stopping any existing stacks for Elasticsearch and OpenSearch (if present)..."
compose_down "$ES_COMPOSE_PATH"
compose_down "$OPENSEARCH_COMPOSE_PATH"

# 2.1) Verify ports are free after down
log "Verifying required ports are free after stopping stacks..."
for p in "${ES_HOST_PORTS[@]}" "${OPENSEARCH_HOST_PORTS[@]}"; do
  if host_port_open "$p"; then
    container_name="$(container_publishing_port "$p")"
    if [[ -n "$container_name" ]]; then
      die "Host port $p still in use by container $container_name after stopping stacks. Please stop it manually."
    else
      die "Host port $p still in use by a non-docker process after stopping stacks. Please free it manually."
    fi
  fi
done

# 3) Start Elasticsearch compose and wait for health
if ! compose_up "$ES_COMPOSE_PATH"; then
  die "Failed to start Elasticsearch compose. See logs above."
fi

if ! wait_for_health "$ES_HEALTH_URL" "$WAIT_TIMEOUT" "$WAIT_INTERVAL"; then
  warn "Gathering Elasticsearch logs (last 200 lines):"
  run_compose "$ES_COMPOSE_PATH" logs --tail 200 || true
  die "Elasticsearch did not become healthy in time."
fi

# 4) Start Opensearch compose and wait for health
if ! compose_up "$OPENSEARCH_COMPOSE_PATH"; then
  die "Failed to start OpenSearch compose. See logs above."
fi

if ! wait_for_health "$OPENSEARCH_HEALTH_URL" "$WAIT_TIMEOUT" "$WAIT_INTERVAL"; then
  warn "Gathering OpenSearch logs (last 200 lines):"
  run_compose "$OPENSEARCH_COMPOSE_PATH" logs --tail 200 || true
  die "OpenSearch did not become healthy in time."
fi

log "Both Elasticsearch and OpenSearch appear healthy."

# show quick status
log "Docker containers status (matching names):"
docker ps --filter "name=elasticsearch" --filter "name=opensearch" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

log "Inspect logs:"
printf "  Elasticsearch logs: %s\n" "${COMPOSE_CMD[*]} -f $ES_COMPOSE_PATH logs -f"
printf "  OpenSearch logs:    %s\n" "${COMPOSE_CMD[*]} -f $OPENSEARCH_COMPOSE_PATH logs -f"

log "Done. Both stacks started successfully."
exit 0
