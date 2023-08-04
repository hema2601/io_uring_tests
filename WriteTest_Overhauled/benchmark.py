import json
import subprocess
from enum import Enum
import time
import datetime


class TestCases(Enum):
    TIMER = 0
    INFLIGHT = 1
    COMPLETIONS = 2
    PENDING = 3
    PLOT_INFLIGHT = 4
    PLOT_COMPLETIONS = 5

flags = ('-T', '-p', '-o', '-e', '-P', '-O')

def runningAvg(avg, val, cnt):
    return float(avg) + ((float(val) - float(avg)) / float(cnt))

class JsonAnalyzer:
    raw_file = None
    date = None
    avg_file = None

    def __init__(self, file_name="json.txt", init_file=False):
        if init_file == True:
            self.raw_file = open(file_name, 'r+', encoding="utf-8")
        else:
            self.raw_file = open(file_name, 'w+', encoding="utf-8")
        #date = datetime.now()        
        

    def add(self, string):
        self.raw_file.write(string)

    def average(self, file_name="json_avg.txt"):
        self.avg_file = open(file_name, 'w', encoding="utf-8")

        json_dict = json.load(self.raw_file)

        exp = json_dict["Experiments"]

        for x in exp:
            agg = x["Runs"][0]["Output"]
            counter = 1

            print(agg[0])
            for each in x["Runs"][1:]:
                agg[0]["Pending"] = runningAvg(agg[0]["Pending"], each["Output"][0]["Pending"], ++counter)
                agg[0]["Execution Time"] = runningAvg(agg[0]["Execution Time"], each["Output"][0]["Execution Time"], ++counter)
                agg[0]["Completions"][0]["avg"] = runningAvg(agg[0]["Completions"][0]["avg"], each["Output"][0]["Completions"][0]["avg"], ++counter)
                agg[0]["Inflight Packets"][0]["avg"] = runningAvg(agg[0]["Inflight Packets"][0]["avg"], each["Output"][0]["Inflight Packets"][0]["avg"], ++counter)
                agg[1]["Thread Count"] = runningAvg(agg[1]["Thread Count"], each["Output"][1]["Thread Count"], ++counter)

            self.avg_file.write(json.dumps(agg))
            self.avg_file.write("\n\n")

            print(agg)


ja = None

#json_file = open("json.txt", 'w', encoding="utf-8")

def run_strace(binary, json=False):

    command = ['sudo', '/usr/bin/perf', 'stat']

    if json==True:
        command.append('-j')

    command.append(binary)

    result = subprocess.run(command, capture_output=True, text=True)

    return result.stderr


class Command:
    def __init__(self, binary, traits, mode=1, json=True, batch=-1, min_completions=-1, total=-1):

        self.command = [binary, '-t '+str(mode)]

        if json==True:
            self.command.append('-j')

        for idx, x in enumerate(traits):
            if x == True:
                self.command.append(flags[idx])
    
        if batch != -1:
            self.command.append('-b '+str(batch))
        if total != -1:
            self.command.append('-r '+str(total))
        if min_completions != -1:
            self.command.append('-c '+str(min_completions))



    def get_command(self):
        return self.command


class WriteTest:

    traits = [False] * len(TestCases)    

    def __init__(self, num_runs, mode=1, batch=10, total=1000000, min_completions=1, threads=0):
        self.json = True
        self.binary = "./write_test"
        self.num_runs = num_runs;
        self.type = mode   
        self.batch= batch
        self.total = total
        self.threads = threads
        self.min_completions = min_completions

    def run_test(self):
        self.command = Command(binary=self.binary, mode=self.mode, traits=self.traits, batch=self.batch, total=self.total, min_completions=self.min_completions)

        for i in range(self.num_runs):
            if i != 0 :
                ja.add(", ")
            self.iteration(i)

    def iteration(self, i):
    
        ja.add("{\"Index\":"+str(i)+", \"Output\":[")

        p = subprocess.Popen(self.command.get_command(), stdout=subprocess.PIPE)
        tc = [0]
        while(p.poll() == None):
            if self.threads != 0:
                p2 = subprocess.run('/bin/ps --no-headers -o thcount '+ str(p.pid),shell=True, stdout=subprocess.PIPE)
                out = int(p2.stdout.decode("utf-8"))
                if self.threads == 2:
                    tc.append(out)
                else:
                    tc[0] = out if out > tc[0] else tc[0]
                time.sleep(0.1)
        ja.add(p.stdout.read().decode("utf-8"))
        #print(p.stdout.read().decode("utf-8"))

        if self.threads == 1:
            ja.add(", {\"Thread Count\": "+ str(tc[0])+ "}")
            #print(", {\"Thread Count\": "+ str(tc[0])+ "}")
        elif self.threads == 2:
            ja.add(", {\"Thread Count\": [")
            #print(", {\"Thread Count\": [", end="")
            for x in tc[1:-1]:
                ja.add(str(x) +",")
                #print(str(x) +",", end="")
            ja.add(str(tc[-1]) + "]}")
            #print(str(tc[-1]) + "]}")
            
        ja.add("]}")


    def activate_trait(self, enum_idx):
        self.traits[enum_idx.value] = True
    def deactivate_trait(self, enum_idx):
        self.traits[enum_idx.value] = True

    def set_batch(self, val):
        self.batch = val
    def set_min_completions(self, val):
        self.min_completions = val
    def set_total(self, val):
        self.total = val
    def set_mode(self, val):
        self.mode = val
    def set_threads(self, val):
        self.threads = val




"""
ja = JsonAnalyzer(init_file=True)
ja.average()
"""
ja = JsonAnalyzer(init_file=True)

total = 1000000

test = WriteTest(10, total=total)

test.activate_trait(TestCases.PENDING)
test.activate_trait(TestCases.INFLIGHT)
test.activate_trait(TestCases.COMPLETIONS)
test.activate_trait(TestCases.TIMER)
test.set_threads(1)
batch_sizes = [1, 10, 100, 1000];

idx = 0
ja.add("{ \"Experiments\":[")

test.set_mode(0)

ja.add("{\"Index\":"+str(idx)+", \"Type\":0, \"Total\":"+str(total)+", \"Runs\":[")
idx += 1
test.run_test()

ja.add("]}")


test.set_mode(1)

for i in batch_sizes:
    comps = [0, 1, int(i/2), i]
    comps = [*set(comps)] 
    for j in comps:
        test.set_batch(i)
        test.set_min_completions(j)
        ja.add(", {\"Index\":"+str(idx)+", \"Type\":1, \"Total\":"+str(total)+", \"Batch Size\":"+str(i)+", \" Minimum Completions\":"+str(j)+", \"Runs\":[")
        idx += 1
        print(f"Batch: {i}\t Completions: {j}")
        test.run_test()
        ja.add("]}")

ja.add("]}")




