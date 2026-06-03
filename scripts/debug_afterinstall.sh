#!/bin/bash
# =============================================================================
# debug_afterinstall.sh
# Temporary debug script to gather troubleshooting info for AfterInstall failures
# in the CodeDeploy pipeline for searchgov-spider.
#
# Run this on the EC2 host as the 'search' user (same runas as appspec.yml):
#   bash scripts/debug_afterinstall.sh 2>&1 | tee /tmp/afterinstall_debug.log
# =============================================================================

set -uo pipefail

DIVIDER="============================================================"
DEPLOY_DIR="/opt/codedeploy-agent/deployment-root"

print_section() {
    echo ""
    echo "$DIVIDER"
    echo ">>> $1"
    echo "$DIVIDER"
}

# ------------------------------------------------------------------------------
print_section "SYSTEM INFO"
echo "Date/Time  : $(date)"
echo "Hostname   : $(hostname)"
echo "User       : $(whoami)"
echo "Home       : $HOME"
echo "PWD        : $(pwd)"
echo "Shell      : $SHELL"
echo "OS Release :"
cat /etc/os-release 2>/dev/null || echo "N/A"

# ------------------------------------------------------------------------------
print_section "PYTHON AVAILABILITY"
echo "--- python3.12 ---"
command -v python3.12 && python3.12 --version || echo "ERROR: python3.12 not found in PATH"

echo "--- python3 ---"
command -v python3 && python3 --version || echo "python3 not found"

echo "--- which python* ---"
ls /usr/bin/python* /usr/local/bin/python* 2>/dev/null || echo "No python binaries found in common locations"

echo "--- PATH ---"
echo "$PATH"

# ------------------------------------------------------------------------------
print_section "PROFILE / ENVIRONMENT"
echo "--- ~/.profile exists? ---"
if [ -f "$HOME/.profile" ]; then
    echo "YES — contents:"
    cat "$HOME/.profile"
else
    echo "NO — ~/.profile does not exist"
fi

echo ""
echo "--- Key env vars ---"
for VAR in PYTHONPATH VIRTUAL_ENV SPIDER_PYTHON_VERSION DB_HOST REDIS_HOST ES_HOSTS AWS_DEFAULT_REGION; do
    echo "  $VAR=${!VAR:-<not set>}"
done

# ------------------------------------------------------------------------------
print_section "AWS / EC2 METADATA"
echo "--- ec2metadata availability ---"
command -v ec2metadata && echo "ec2metadata found" || echo "ec2metadata NOT found"

echo "--- Region via ec2metadata ---"
ec2metadata --availability-zone 2>/dev/null | sed 's/.$//' || echo "Could not retrieve region"

echo "--- AWS CLI identity ---"
aws sts get-caller-identity 2>&1 || echo "aws sts failed"

# ------------------------------------------------------------------------------
print_section "AWS SSM PARAMETER STORE CONNECTIVITY"
echo "Attempting to list parameters (no decryption) to verify IAM access..."
REGION=$(ec2metadata --availability-zone 2>/dev/null | sed 's/.$//' || echo "us-east-1")
echo "Using region: $REGION"
# Just test one known param to verify access without leaking secrets
aws ssm get-parameter --name "SPIDER_PYTHON_VERSION" --region "$REGION" --query "Parameter.Name" --output text 2>&1 \
    && echo "SSM access OK" \
    || echo "SSM access FAILED — check IAM role/permissions"

# ------------------------------------------------------------------------------
print_section "VENV STATE"
VENV_DIR="./venv"
echo "--- venv directory exists? ---"
if [ -d "$VENV_DIR" ]; then
    echo "YES: $VENV_DIR"
    ls -la "$VENV_DIR/bin/" 2>/dev/null | head -20
else
    echo "NO: $VENV_DIR does not exist (expected — stop script removes it)"
fi

# ------------------------------------------------------------------------------
print_section "DISK SPACE"
df -h . 2>/dev/null

echo "--- /tmp usage ---"
df -h /tmp 2>/dev/null

# ------------------------------------------------------------------------------
print_section "PERMISSIONS ON CICD-SCRIPTS"
ls -la cicd-scripts/ 2>/dev/null || echo "cicd-scripts/ not found from $(pwd)"
ls -la cicd-scripts/helpers/ 2>/dev/null || echo "helpers dir not found"

echo "--- Executable bits on key scripts ---"
for SCRIPT in cicd-scripts/app_install.sh cicd-scripts/app_start.sh cicd-scripts/app_stop.sh \
              cicd-scripts/helpers/ensure_executable.sh cicd-scripts/helpers/fetch_env_vars.sh \
              cicd-scripts/helpers/update_pythonpath.sh cicd-scripts/helpers/check_cloudwatch.sh \
              cicd-scripts/helpers/check_codedeploy.sh cicd-scripts/helpers/check_ssm.sh; do
    if [ -f "$SCRIPT" ]; then
        echo "  $(ls -la $SCRIPT)"
    else
        echo "  MISSING: $SCRIPT"
    fi
done

# ------------------------------------------------------------------------------
print_section "RUNNING PROCESSES (spider-related)"
ps aux | grep -E "python|scrapy|playwright|codedeploy|cloudwatch|ssm" | grep -v grep || echo "None found"

# ------------------------------------------------------------------------------
print_section "CRONTAB (current user)"
crontab -l 2>/dev/null || echo "No crontab for $(whoami)"

# ------------------------------------------------------------------------------
print_section "CODEDEPLOY AGENT STATUS"
sudo service codedeploy-agent status 2>&1 || sudo systemctl status codedeploy-agent 2>&1 || echo "Could not get codedeploy-agent status"

echo ""
echo "--- Last CodeDeploy deployment logs ---"
LATEST_DEPLOY=$(ls -td "$DEPLOY_DIR"/*/logs/ 2>/dev/null | head -1)
if [ -n "$LATEST_DEPLOY" ]; then
    echo "Log dir: $LATEST_DEPLOY"
    ls "$LATEST_DEPLOY" 2>/dev/null
    echo ""
    echo "--- scripts-log (last 100 lines) ---"
    tail -100 "${LATEST_DEPLOY}/scripts.log" 2>/dev/null || echo "scripts.log not found"
else
    echo "No deployment logs found at $DEPLOY_DIR"
fi

# ------------------------------------------------------------------------------
print_section "CLOUDWATCH AGENT STATUS"
sudo service amazon-cloudwatch-agent status 2>&1 || sudo systemctl status amazon-cloudwatch-agent 2>&1 || echo "CloudWatch agent not found/running"

# ------------------------------------------------------------------------------
print_section "SSM AGENT STATUS"
sudo service amazon-ssm-agent status 2>&1 || sudo systemctl status amazon-ssm-agent 2>&1 || echo "SSM agent not found/running"

# ------------------------------------------------------------------------------
print_section "SETFACL / ACL SUPPORT"
command -v setfacl && echo "setfacl available: $(setfacl --version 2>&1 | head -1)" || echo "setfacl NOT found — acl package may be missing"

# ------------------------------------------------------------------------------
print_section "PIP CACHE"
du -sh ~/.cache/pip 2>/dev/null || echo "No pip cache found"

# ------------------------------------------------------------------------------
print_section "REQUIREMENTS FILE CHECK"
REQ_FILE="./search_gov_crawler/requirements.txt"
if [ -f "$REQ_FILE" ]; then
    echo "Found: $REQ_FILE ($(wc -l < $REQ_FILE) lines)"
else
    echo "MISSING: $REQ_FILE"
fi

# ------------------------------------------------------------------------------
print_section "SUMMARY"
echo "Debug info collection complete."
echo "Share /tmp/afterinstall_debug.log for analysis."
echo ""
