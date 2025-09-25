#!/bin/sh
# A script to allow for simple spider usage in docker.

DOCKER_WORK_DIR=/usr/src/searchgov-spider

_show_help() {
    echo "crawl - A simple interface allowing for ad hoc spider runs."
    echo ""
    echo "Usage: crawl <domain> <starting-url> [OPTIONS]"
    echo ""
    echo "Required Arguments:"
    echo "domain:           Domain used to limit crawls"
    echo "starting-url:     URL to start crawling at"
    echo ""
    echo "Options:"
    echo "  --help           Display this help message"
    echo ""
    echo "Examples:"
    echo "   Crawl starting at https://www.gsa.gov, limited to links that are in the www.gsa.gov domain"
    echo "     - crawl www.gsa.gov https://www.gsa.gov"
}

_has_args() {
    if [ "$#" -lt 2 ]; then
        echo "ERROR: Not Enough Arguments!"
        echo ""
        _show_help
        return 1
    fi
}

crawl() {
    (_has_args $@) || exit 1

    ALLOWED_DOMAINS=$1
    STARTING_URLS=$2

    cd $DOCKER_WORK_DIR/search_gov_crawler
    echo $ALLOWED_DOMAINS $STARTING_URLS
    python benchmark.py -d $ALLOWED_DOMAINS -u $STARTING_URLS
}

"$@"
