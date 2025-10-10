#! /bin/bash

set_defaults_env() {
    # Set default values only if they are not already defined
    export CRAWL_CONFIG_TABLE="crawl_configs"
    export DB_USER="${DB_USER:-root}"
    export DB_PASSWORD="${DB_PASSWORD:-""}"
    export DB_HOST="${DB_HOST:-127.0.0.1}"
    export DB_PORT="${DB_PORT:-3306}"
    export DB_NAME="${DB_NAME:-usasearch_development}"
}

_run_sql() {
    mysql -vvv -u $DB_USER --password=$DB_PASSWORD -h $DB_HOST -P $DB_PORT -e "$@"
}


drop_table() {
    echo -e "\nDropping Table:"
    _run_sql "USE ${DB_NAME}; DROP TABLE IF EXISTS ${CRAWL_CONFIG_TABLE};"
}

create_database() {
    echo -e "\nCreating Database:"
    _run_sql "CREATE DATABASE IF NOT EXISTS ${DB_NAME};"
}

create_table() {
    _run_sql "USE ${DB_NAME}; \
    CREATE TABLE ${CRAWL_CONFIG_TABLE} (\
      id bigint NOT NULL AUTO_INCREMENT,\
      name varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,\
      active tinyint(1) NOT NULL DEFAULT '1',\
      allowed_domains varchar(2048) COLLATE utf8mb4_unicode_ci NOT NULL,\
      starting_urls text COLLATE utf8mb4_unicode_ci NOT NULL,\
      sitemap_urls text COLLATE utf8mb4_unicode_ci,\
      deny_paths text COLLATE utf8mb4_unicode_ci,\
      depth_limit int NOT NULL DEFAULT '3',\
      sitemap_check_hours int DEFAULT NULL,\
      allow_query_string tinyint(1) NOT NULL DEFAULT '0',\
      handle_javascript tinyint(1) NOT NULL DEFAULT '0',\
      schedule varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,\
      output_target varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,\
      created_at datetime(6) NOT NULL,\
      updated_at datetime(6) NOT NULL,\
      PRIMARY KEY (id),\
      UNIQUE KEY index_crawl_configs_on_output_target_and_allowed_domains (output_target,allowed_domains(255))\
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
}


main() {
    if ! command -v mysql &> /dev/null; then
        echo "mysql client could not be found, please install before running!"
        return 1
    fi

    # Load environment variables from .env
    if [ -f .env ]; then
        set -o allexport
        source .env
        set +o allexport
    fi

    set_defaults_env
    create_database
    drop_table
    create_table
}

main "$@"
