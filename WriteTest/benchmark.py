import json
import subprocess


def run_strace(binary, json=False):

    command = ['sudo', '/usr/bin/perf', 'stat']

    if json==True:
        command.append('-j')

    command.append(binary)

    result = subprocess.run(command, capture_output=True, text=True)

    return result.stderr






objs = run_strace("./write_normal", json=True).split("\n")

objs = objs[:-1] 
for obj in objs:
    obj = json.loads(obj)



