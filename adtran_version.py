import requests
from lxml import html
import re
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import os

JOB_TO_COMPARE = os.environ['JOB_TO_COMPARE']

class Job:
    def __init__(self, name, last_success, last_fail, last_ran):
        self.name = name
        self.last_success = last_success
        self.last_fail = last_fail
        self.last_ran = last_ran
        self.status = ""


def most_recent_date(date1, date2):
    if "N/A" in date1 and "N/A" in date2:
        return "N/A"
    elif "N/A" in date1:
        return date2
    elif "N/A" in date2:
        return date1

    else:
        t1 = convert_time_to_minutes(date1)
        t2 = convert_time_to_minutes(date2)
        if (t1 < t2):
            return date1
        else:
            return date2


def convert_time_to_minutes(timein):
    time = 0
    m = re.search(
        '(?:([0-9]+) yr)?\s*(?:([0-9]+) mo)?\s*(?:([0-9]+) day(?:s)?)?\s*(?:([0-9]+) hr)?\s*(?:([0-9]+) min)?\s*(?:([0-9]+) sec)?\s*',
        timein)  # this regex is hideous.
    if m.group(1) is not None:
        time += int(m.group(1)) * 365 * 24 * 60

    if m.group(2) is not None:
        time += int(m.group(2)) * 30 * 24 * 60

    if m.group(3) is not None:
        time += int(m.group(3)) * 24 * 60

    if m.group(4) is not None:
        time += int(m.group(4)) * 60

    if m.group(5) is not None:
        time += int(m.group(5))

    return time


def audit(path, job_list, folder):

    r = requests.get(path)
    file = open('page_data.txt', 'w')
    file.write(r.content)
    tree = html.fromstring(r.content)
    jobs = tree.xpath('//tr[@id]')

    for job in jobs:

        job_id = job.get('id')[4:]

        if ('Folder' in html.tostring(job) 
            or 'GitHub Repository' in html.tostring(job) 
            or 'GitHub Organization' in html.tostring(job)):
            audit(path + "job/" + job_id + "/", job_list, folder + "job/" + job_id + "/")

        elif not 'top-nav' in html.tostring(job) and len(job.findall('td')) >= 5:
            success = ((job.findall('td')[3]).text).strip('- ').strip()
            fail = ((job.findall('td')[4]).text).strip('- ').strip()
            j = Job(
                folder +
                "job/" +
                job_id,
                success,
                fail,
                most_recent_date(
                    success,
                    fail))
            job_list.append(j)


def update_status(job_list, threshold):
    aj = 0
    for j in job_list:
        if j.last_ran != "N/A":
            t = convert_time_to_minutes(j.last_ran)
            if t <= threshold * 24 * 60:
                aj += 1
                j.status = "Active"
    return aj


def convert_table_to_list(table_url):
    import requests
    r = requests.get(table_url)
    name_list = []
    for line in r.text.splitlines():
        name_list.append(line.partition('\t')[0])
    del name_list[0]
    return name_list


def compare_last_audit(old_audit, new_audit, server_name):
    new_audit_names = set([job.name for job in new_audit])
    old_audit_names = set([x.encode('utf-8') for x in old_audit])
    deleted_jobs = old_audit_names.difference(new_audit_names)
    new_jobs = new_audit_names.difference(old_audit_names)
    with open(server_name + "_diff.txt", "w+") as myfile:
        myfile.write("Deleted Jobs:\n")
        for job in deleted_jobs:
            myfile.write("\t" + job + "\n")
        myfile.write("\nNew Jobs:\n")
        for job in new_jobs:
            myfile.write("\t" + job + "\n")


def make_table(job_list, m):
    f = open(m.group(2) + "_audit.txt", 'w+')
    f.write("Job Name\tLast Success\tLast Failure\tLast Ran\tStatus")
    for j in job_list:
        f.write(
            "\n" +
            j.name +
            "\t" +
            j.last_success +
            "\t" +
            j.last_fail +
            "\t" +
            j.last_ran +
            "\t" +
            j.status)


def entry_point(url, threshold):
    job_list = []
    m = re.search('/(([^/]+)/)$', url)
    audit(url, job_list, m.group(1))
    active_jobs = update_status(job_list, int(threshold))
    make_table(job_list, m)
    with open("overview.txt", "a") as myfile:
        myfile.write("Number of jobs on " + m.group(2) + ": " + str(len(job_list)) + "\n")
    old_audit = convert_table_to_list(JOB_TO_COMPARE + "artifact/" + m.group(2) + "_audit.txt")
    compare_last_audit(old_audit, job_list, m.group(2))
    print("output saved to " + m.group(2) + "_audit.txt")
    print("total number of jobs: " + str(len(job_list)))
    print("number of active jobs: " + str(active_jobs))
