import json
import subprocess
from enum import Enum
import time
import datetime
import itertools

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
"""
class DataObject:
    name = None
    data_type = None
    value = None
    
    def __init__(self, name, data_type, value = 0):
        self.name = name
        self.data_type = data_type
        self.value = value

    def json_string(self):
        return ("\"" + str(self.name) + "\" : { \"Type\" : " + str(self.data_type) + ", \"Value\" : " + str(self.value) + " }")

    def set_value(self, value):
        self.value = value

class Command:

    command = None

    def __init__(self, binary, parameters):

        self.command = [binary]

        for para in parameters:
            self.command.append(para.format_opt())

    def get_command(self):
        return self.command


class Parameter:
    name = None
    value = None
    idx = 0
    flag = None
    has_value = None
    in_relation_to = None
    ranged = None

    def __init__(self, name, flag, values=None, in_relation_to=None):
        self.name = name
        self.value = values
        self.flag = flag
        self.in_relation_to = in_relation_to

        self.has_value = True if values != None else False 
        self.ranged = isinstance(values, list)

        if self.ranged == False:
            self.value = [self.value]


    def format_opt(self):
        if self.has_value == True:
            return "-" + self.flag + " " + str(self.value[self.idx])
        else:
            return "-" + self.flag 

    def set_value(self, value):
        try:
            self.idx = self.value.index(value)
        except ValueError:
            print("Requested Value not in Range")
            self.idx = 0

        #if self.value.index(value)
        #self.value = value

    def json_string(self):
        if self.has_value == True:
            return "\"" + self.name + "\" : " + str(self.value[self.idx])
        else:
            return "\"" + self.name + "\" : \"True\""

    def has_relation(self):
        return self.in_relation_to != None
        
    def has_range(self):
        return self.ranged 

class Run:
    idx = None
    command = None
    analyzer = None
    thread_count_mode = None
    output_counter = 0

    def __init__(self, idx, command, analyzer, thread_count_mode=0):
        self.idx = idx
        self.command = command
        self.analyzer = analyzer
        self.thread_count_mode = thread_count_mode

    def count_threads(self, proc):

        do = DataObject("Thread Count", 1) if self.thread_count_mode == 1 else DataObject("Thread Count", 2)
        tc = [0]
        while(proc.poll() == None):

            p2 = subprocess.run('/bin/ps --no-headers -o thcount '+ str(proc.pid), shell=True, stdout=subprocess.PIPE)
            out = int(p2.stdout.decode("utf-8"))
            if self.thread_count_mode == 2:
                tc.append(out)
            else:
                tc[0] = out if out > tc[0] else tc[0]
            time.sleep(0.1)
           
        if self.thread_count_mode == 1:
            do.set_value(tc[0])
        elif self.thread_count_mode == 2:
            do.set_value(tc[1:])

        self.analyzer.add( "{ " + do.json_string() + " }")
        self.output_counter += 1

    def run(self):
        self.print_prologue()
        
        p = subprocess.Popen(self.command.get_command(), stdout=subprocess.PIPE)

        if self.thread_count_mode != 0:
            self.count_threads(p)
            self.analyzer.add(", ")

        #print(p.stdout.read().decode("utf-8"))
        self.analyzer.add(p.stdout.read().decode("utf-8"))
        self.output_counter += 1
        
        self.print_epilogue()

    def print_prologue(self):
        self.analyzer.add("{ \"Run Index\" : " + str(self.idx) + ", \"Outputs\" : [ ")

    def print_epilogue(self):
        self.analyzer.add("], \"Output Count\" : " + str(self.output_counter) + " }")

class ExperimentObj:
    idx = None
    parameters = None
    command = None
    binary = None
    analyzer = None
    run_counter = 0
    thread_count_mode = None 

    def __init__(self, analyzer, idx, binary, parameters, thread_count_mode=0):
        self.analyzer = analyzer
        self.idx = idx
        self.parameters = parameters
        self.binary = binary
        self.command = Command(binary, parameters)
        self.thread_count_mode = thread_count_mode

    def get_para_combination(self):
        ranged_paras = [para.value for para in self.parameters if para.has_range()]
        print(ranged_paras)
        if len(ranged_paras) == 0:
            return None

        comb = ranged_paras[0]

        is_first = True
        for para in ranged_paras[1:]:
            if is_first == True:
                comb = list(itertools.product(comb, para))
                is_first = False
            else:
                comb = [(*flatten, rest) for flatten, rest in list(itertools.product(comb, para))]

        print(comb)
        return comb

    def assign_paras(self, values):
        ranged_paras = [para for para in self.parameters if para.has_range()]

        if len(ranged_paras) == 0:
            return

        for i, para in enumerate(ranged_paras):
            para.set_value(values[i])


    def run_experiment(self):
        self.print_prologue()

        print(self.command.get_command())

        run_paras = self.get_para_combination()    

        for para_set in run_paras:
            self.assign_paras(para_set)
            self.command = Command(self.binary, self.parameters)
            run = Run(self.run_counter, self.command, self.analyzer, 2)
            self.run_counter += 1;
            run.run()
            




        self.print_epilogue()

    def print_prologue(self, print_no_val=False):
        self.analyzer.add("{ \"Experiment Index\" : " + str(self.idx) + ", \"Parameters\" : { ")

        not_first = False
        for i, para in enumerate(self.parameters):
            if para.has_value == True:
                if not_first == True:
                    self.analyzer.add(", ")
                else:
                    not_first = True
                    
                self.analyzer.add(para.json_string())
            elif print_no_val == True:
                if not_first == True:
                    self.analyzer.add(", ")
                else:
                    not_first = True
                self.analyzer.add(para.json_string())

        self.analyzer.add(" }, \"Runs\" : [ ")


    def print_epilogue(self):
        
        self.analyzer.add(" ], \"Run Count\" : " + str(self.run_counter) + " }")

class BenchmarkObj:
    date = None
    title = None
    analyzer = None
    experiment_count = 0
    binary = None
    def __init__(self, binary, filename="json.txt"):
        self.binary = binary
        self.title = "abc"
        self.date = "Today"
        self.analyzer = JsonAnalyzer(filename)

    def run_benchmark(self):
        self.print_prologue()

        #create parameters
        parameters = []
        parameters.append(Parameter("Type", "t", [0, 1]))
        parameters.append(Parameter("Batch Size", "b", 10))
        parameters.append(Parameter("Total Requests", "r", [1000, 1000000]))
        parameters.append(Parameter("Minimum Completions", "c", 1))
        parameters.append(Parameter("Write Size", "s", 8))
        parameters.append(Parameter("Track Pending", "p"))
        parameters.append(Parameter("Track Completions", "o"))
        parameters.append(Parameter("Completions at Exit", "e"))
        parameters.append(Parameter("Execution Time", "T"))
        parameters.append(Parameter("Json", "j"))
        """
        parameters.append(Parameter("Type", "t", 1))
        parameters.append(Parameter("Batch Size", "b", 10))
        parameters.append(Parameter("Total Requests", "r", 1000000))
        parameters.append(Parameter("Minimum Completions", "c", 1))
        parameters.append(Parameter("Write Size", "s", 10))
        parameters.append(Parameter("Track Pending", "p"))
        parameters.append(Parameter("Track Completions", "o"))
        parameters.append(Parameter("Completions at Exit", "e"))
        parameters.append(Parameter("Execution Time", "T"))
        parameters.append(Parameter("Json", "j"))
        """
        experiment = ExperimentObj(self.analyzer, self.experiment_count, self.binary, parameters)

        self.experiment_count += 1

        experiment.run_experiment()



        self.print_epilogue()     
    def print_prologue(self):
        self.analyzer.add("{ \"Title\" : \"" + self.title + "\", \"Date\" : \"" + self.date + "\", \"Experiments\" : [ ")
    def print_epilogue(self):
        self.analyzer.add("], \"Experiment Count\" : " + str(self.experiment_count) + "}")



bo = BenchmarkObj("./write_test", "test2.txt")

bo.run_benchmark()


"""
ja = JsonAnalyzer(init_file=True)
ja.average()

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



"""
