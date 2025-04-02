# Operations
This page is mean to help people use a deployed version of the spider by providing common commands and instructions on how to fix issues that may arise.  These instructions assume the ability to execute commands on the host.

## Common Commands

### Investigation

#### Check if any scrapy jobs are running
We may often want to know if any or how many scrapy jobs are running.  We can see that by running the following command.
```bash
ps aux | grep "scrapy"
```
This should show any on going scrapy processes as well as the scrapy_schedule process if running.

#### Check if Cloudwatch agent is running
This should show an active status if cloudwatch is running
```bash
sudo service amazon-cloudwatch-agent status
```

#### Check if Codedeploy agent is running
This should show an active status if codedeploy is running
```bash
sudo service codedeploy-agent status
```

#### See most recent entries in logfile
```
tail -f /var/log/scrapy_scheduler.log
```

### Execution
When running python commands be sure to first:
* Move to the correct deployment directory (the PYTHONPATH env var can be used for this)
* Source the virtual environment
```bash
cd $PYTHONPATH
source venv/bin/activate
```

#### Wrap commands in nohup and redirect to logfile
When starting a spider process, we need to ensure that the logs are captured and the process is not tied to the terminal session.  Most commands to start an execution should be wrapped like this, with `"command"` being the command you want to run.
```bash
nohup "command" >> /var/log/scrapy_scheduler.log 2>&1 &
```

For example, to kick of a manual benchmark run for the `usa.gov` domain with an output target of `endpoint` you would run:
```bash
nohup python search_gov_crawler/benchmark.py -d usa.gov -u https://www.usa.gov/ -o endpoint >> /var/log/scrapy_scheduler.log 2>&1 &
```

### Resolution

#### Restart the Scheduler
In some cases we may need to restart the scheudler using the normal process.  In that case it is best to use the same scripts as the deployment process.
* Move to the correct deployment directory (the PYTHONPATH env var can be used for this)
* Source the run script
```bash
cd $PYTHONPATH
source cicd-scripts/app_start.sh
```
