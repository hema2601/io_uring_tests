import json
import subprocess
from enum import Enum
import time
import datetime
import itertools
import sys

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
        if self.data_type == 0:
            return ("\"" + str(self.name) + "\" : " + str(self.value) )

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

    def to_file(self, filename):
        self.command.append(">")
        self.command.append(filename)


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
    
    def __str__(self):
        if self.has_value == True:
            return self.name + " : " + str(self.value[self.idx])
        else:
            return self.name + " : True"
    def __repr__(self):
        if self.has_value == True:
            return self.name + " : " + str(self.value[self.idx])
        else:
            return self.name + " : True"

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

        do = DataObject("Thread Count", 0) if self.thread_count_mode == 1 else DataObject("Thread Count", 2)
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
       
        #self.command.to_file("output.txt")

        #print(self.command.get_command())
        f = open("output.txt", "w+")

        p = subprocess.Popen(self.command.get_command(), stdout=f)

        if self.thread_count_mode != 0:
            self.count_threads(p)
            self.analyzer.add(", ")

        p.wait()

        #print(p.stdout.read().decode("utf-8"))
        #self.analyzer.add(p.stdout.read().decode("utf-8"))
    
        f.close()
        f = open("output.txt", "r")
                
        self.analyzer.add(f.read())

        f.close()

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
    runs = None

    def __init__(self, analyzer, idx, binary, parameters, runs, thread_count_mode=0):
        self.analyzer = analyzer
        self.idx = idx
        self.parameters = parameters
        self.binary = binary
        self.command = Command(binary, parameters)
        self.thread_count_mode = thread_count_mode
        self.runs = runs
    
    def __str__(self):
        string = f"----\nExperiment #{self.idx}\nParameter List:\n"
        for para in self.parameters:
            string += str(para) + "\n"

        string += "\n\n"

        return string

    def run_experiment(self):
        self.print_prologue()
        """
        print(self.command.get_command())

        run_paras = self.get_para_combination()    

        for para_set in run_paras:
            self.assign_paras(para_set)
            self.command = Command(self.binary, self.parameters)
            run = Run(self.run_counter, self.command, self.analyzer, 2)
            self.run_counter += 1;
            run.run()
            
        """

        is_first = True

        for i in range(self.runs):
            if is_first == False:
                self.analyzer.add(", ")
            is_first = False
            run = Run(self.run_counter, self.command, self.analyzer, self.thread_count_mode)
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
    parameters = None
    runs = None
    threading = None

    def __init__(self, binary, parameters, filename="json.txt", runs = 1, threading = 0):
        self.binary = binary
        self.title = "abc"
        self.date = "Today"
        self.analyzer = JsonAnalyzer(filename)
        self.parameters = parameters
        self.runs = runs
        self.threading = threading

    def get_para_combination(self):
        ranged_paras = [para.value for para in self.parameters if para.has_range()]
        #print(ranged_paras)
        if len(ranged_paras) == 0:
            return None

        comb = ranged_paras[0]

        #print(comb)

        is_first = True
        for para in ranged_paras[1:]:
            if is_first == True:
                comb = list(itertools.product(comb, para))
                is_first = False
            else:
                comb = [(*flatten, rest) for flatten, rest in list(itertools.product(comb, para))]

        if is_first == True:
            ret = []
            for x in comb:
                ret.append((x, ))
            #print(ret)
            return ret

        #print(comb)
        return comb

    def assign_paras(self, values):
        ranged_paras = [para for para in self.parameters if para.has_range()]

        if len(ranged_paras) == 0:
            return

        for i, para in enumerate(ranged_paras):
            para.set_value(values[i])


    def run_benchmark(self):
        self.print_prologue()

        #create parameters
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

        run_paras = self.get_para_combination()    

        is_first = True

        for para_set in run_paras:


            if is_first == False:
                self.analyzer.add(", ")
            is_first = False
            self.assign_paras(para_set)
            experiment = ExperimentObj(self.analyzer, self.experiment_count, self.binary, self.parameters, self.runs, self.threading)
            print(experiment)
            self.experiment_count += 1
            experiment.run_experiment()




        self.print_epilogue()     
    def print_prologue(self):
        self.analyzer.add("{ \"Title\" : \"" + self.title + "\", \"Date\" : \"" + self.date + "\", \"Experiments\" : [ ")
    def print_epilogue(self):
        self.analyzer.add("], \"Experiment Count\" : " + str(self.experiment_count) + "}")

    def finalize(self):
        self.analyzer.raw_file.close()
"""
#######################################################################
##### define your application parameters here #########################

parameters = []
parameters.append(Parameter("Type", "t", 0))
parameters.append(Parameter("Total Requests", "r", 1000000))
parameters.append(Parameter("Write Size", "s", [8, 64, 512, 8192]))
parameters.append(Parameter("Execution Time", "T"))
parameters.append(Parameter("Json", "j"))

##### define your benchmarking parameters #############################

thread_counting = 0  # 0 - off, 
                     # 1 - track highest thread count, 
                     # 2 - track changing values of thread count during execution 

runs = 10            # How often is the experiment repeated per parameter set

#######################################################################

bo = BenchmarkObj("./write_test", filename="write_json.txt", parameters=parameters, runs=runs, threading=thread_counting)

#bo.run_benchmark()


"""



#######################################################################
##### define your application parameters here #########################

parameters = []
parameters.append(Parameter("Type", "t", 1))
parameters.append(Parameter("Batch Size", "b", [1, 10, 50 ,100, 1000]))
parameters.append(Parameter("Total Requests", "r", 1000000))
parameters.append(Parameter("Minimum Completions", "c", 1))
parameters.append(Parameter("Write Size", "s", [8, 64, 512, 8192]))
parameters.append(Parameter("Track Pending", "p"))
#parameters.append(Parameter("Plot Pending", "P"))
parameters.append(Parameter("Track Completions", "o"))
#parameters.append(Parameter("Plot Completions", "O"))
parameters.append(Parameter("Completions at Exit", "e"))
parameters.append(Parameter("Execution Time", "T"))
parameters.append(Parameter("Json", "j"))

##### define your benchmarking parameters #############################

thread_counting = 1  # 0 - off, 
                     # 1 - track highest thread count, 
                     # 2 - track changing values of thread count during execution 

runs = 10            # How often is the experiment repeated per parameter set

#######################################################################

#bo = BenchmarkObj("./write_test", filename="new_test.txt", parameters=parameters, runs=runs, threading=thread_counting)

#bo.run_benchmark()

#bo.finalize()

class min_max_avg:
    minimum = None
    maximum = None
    average = None
    count = None

    def __repr__(self):
        return "["+str(self.average)+", "+str(self.minimum)+", "+str(self.maximum)+"]"

    def __init__(self, average=0, minimum=sys.maxsize, maximum=0, count=0):
        self.count = count
        self.maximum = maximum
        self.average  = average
        self.minimum = minimum

    def compute_next(self, value):

        self.count += 1
        self.average = self.average + ((value - self.average) / self.count)

        if(value > self.maximum):
            self.maximum = value
        if(value < self.minimum):
            self.minimum = value

    def combine_mma(self, mma):
        if self.count !=  mma.count:
            print("This is probably an error...")
            return

        self.average = (self.average + mma.average) / 2

        if(mma.maximum > self.maximum):
            self.maximum = mma.maximum
        if(mma.minimum < self.minimum):
            self.minimum = mma.minimum

    def return_dict(self):
        ret_dict = dict()
        ret_dict["avg"] = self.average
        ret_dict["min"] = self.minimum
        ret_dict["max"] = self.maximum
        ret_dict["cnt"] = self.count

        return ret_dict

        

def collapse_experiment(exp):
    averages = dict()

    for run in exp["Runs"]:
        for out in run["Outputs"]:
            for key in out.keys():
                if isinstance(out[key], dict) == False:
                    if key not in averages.keys():
                        averages[key] = min_max_avg()
                    averages[key].compute_next(out[key])
                elif out[key]["Type"] == 1:
                    mma = min_max_avg(average=out[key]["Value"][0], 
                                      minimum=out[key]["Value"][1], 
                                      maximum=out[key]["Value"][2], 
                                      count=out[key]["Value"][3])
                    if key not in averages.keys():
                        averages[key] = mma
                    else:
                        averages[key].combine_mma(mma)

    for key in averages.keys():
        averages[key] = averages[key].return_dict()
        #print(DataObject(key, 1, averages[key].return_dict()).json_string())
    
    return averages



fp = open("new_test.txt", "r")


json_dict = json.load(fp)

average_dict = dict()
average_dict["Experiments"] = []

for i, exp in enumerate(json_dict["Experiments"]):
    print(f"Experiment #"+str(i))
    average_dict["Experiments"].append(exp)
    average_dict["Experiments"][i]["Averages"] = collapse_experiment(exp)
    del average_dict["Experiments"][i]["Run Count"]
    del average_dict["Experiments"][i]["Runs"]

avg_file = open("average_io_uring.txt", "w+")

avg_file.write(json.dumps(average_dict))


avg_file.close()
avg_file = open("average_io_uring.txt", "r+")




import matplotlib.pyplot as plt
import numpy as np
#plt.style.use('_mpl-gallery')
import matplotlib.gridspec as gridspec
import math


def plot_avg(file, name, main, second, plot_type):
   
    file.seek(0)

    json_dict = json.load(file)

    graphs = dict()

    for x in main.value:
        graphs[x] = list()

    upper_limit = 0

    for exp in json_dict["Experiments"]:
        graphs[exp["Parameters"][main.name]].append(exp)
        if exp["Averages"][name]["avg"] > upper_limit:
            upper_limit = exp["Averages"][name]["avg"]
  
    upper_limit = int(upper_limit) + 1


    fig = plt.figure(tight_layout=True)

    root = math.ceil(math.sqrt(len(main.value)))

    gs = gridspec.GridSpec(root, root)

    xlabel = "Write Size in Bytes"
    ylabel = "Seconds"

    for key, idx in zip(graphs.keys(), itertools.product(range(0, root), range(0, root))):

        x = []
        y = []
        for exp in graphs[key]:
            x.append(exp["Parameters"][second.name])
            y.append(exp["Averages"][name]["avg"])

        ax = fig.add_subplot(gs[idx[0], idx[1]])
    
        x = [str(i) for i in x]

        p = ax.bar(x, y , label=x)
        ax.set_title(f"Batch Size {key}")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.bar_label(p, label_type='center')

        ax.set(ylim=(0,upper_limit))


    plt.savefig("AVG_" + name + "_per_" + main.name +"_and_"+second.name+".pdf")

plot_avg(avg_file, "Execution Time", parameters[1], parameters[4], 1)
plot_avg(avg_file, "Pending", parameters[1], parameters[4], 1)
plot_avg(avg_file, "Thread Count", parameters[1], parameters[4], 1)
    





