#!/bin/bash

# Define the .profile file location.  The .profile is used here because it is sourced
# for non-interactive shells, which is what the codedeploy agent uses to run things.
PROFILE=$HOME/.profile

# Use ec2metadata from cloud-utils to get the region containing the EC2
REGION=$(ec2metadata --availability-zone | sed 's/.$//')

# This is the list of parameters we want to get and apply to the .profile
# Certain values will have blank spaces, quotes, and brackets removed from exported
# value due to concerns about quality of the values.
PARAMS="
  DAP_API_BASE_URL
  DAP_EXTRACTOR_SCHEDULE
  DAP_VISITS_DAYS_BACK
  DAP_VISITS_MAX_AGE
  DATA_GOV_API_KEY
  ES_HOSTS
  ES_USER
  ES_PASSWORD
  REDIS_HOST
  REDIS_PORT
  SEARCHELASTIC_INDEX
  SPIDER_CRAWL_SITES_FILE_NAME
  SPIDER_PYTHON_VERSION
  SPIDER_SCRAPY_MAX_WORKERS
  SPIDER_SPIDERMON_ENABLED
  SPIDER_URLS_API
  SEARCH_AWS_ACCESS_KEY_ID
  SEARCH_AWS_SECRET_ACCESS_KEY
"

# For each param in list, get the value from parameter store and add it to the .profile.  If an export
# already exists update the value, otherwise append the export to the end of the .profile. Sourcing is done
# on each parameter to better ensure successful export.
for PARAM in $PARAMS; do
    RAW_VALUE=$(aws ssm get-parameter --name $PARAM --query "Parameter.Value" --output text --region $REGION --with-decryption)

    if [[ -z "$RAW_VALUE" ]]; then
        echo "ERROR! Could not retrive value from param store for $PARAM"
        exit 1
    fi

    # clean and prep value for some.  ES_HOSTS sometimes has blanks and leading/trailing brackets.
    # DAP_EXTRACTOR_SCHEDULE contains spaces so needs quotes added around it.
    if [[ $PARAM == "ES_HOSTS" ]]; then
        VALUE=$(echo $RAW_VALUE | tr -d '[:blank:]|[\"\[\]]')
    elif [[ $PARAM == "DAP_EXTRACTOR_SCHEDULE" ]]; then
        VALUE=$(echo \""$RAW_VALUE"\")
    else
        VALUE=$RAW_VALUE
    fi
    EXPORT_STATEMENT="export $PARAM=${VALUE}"

    if grep -q "^export $PARAM=" $PROFILE; then
        sed -i "s|^export $PARAM=.*|${EXPORT_STATEMENT}|" $PROFILE
    else
        echo "$EXPORT_STATEMENT" >> $PROFILE
    fi

    # Apply changes for the current session and verify
    source $PROFILE
    if [[ "$(eval echo \"\$$PARAM\")" != "$(sed -e 's/^"//' -e 's/"$//' <<< "$VALUE")" ]]; then
            echo "ERROR! Value for $PARAM not set properly!"
        exit 2
    fi

    echo "Successfully feteched and exported $PARAM from parameter store"
done
