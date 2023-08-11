import json
import subprocess
from enum import Enum
import time
import os
from datetime import datetime
import itertools
import sys
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.gridspec as gridspec
import math


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



def runningAvg(avg, val, cnt):
    return float(avg) + ((float(val) - float(avg)) / float(cnt))

class JsonAnalyzer:
    root_filename = None
    raw_file = None
    date = None
    avg_file = None

    def __init__(self, file_name="json.txt"):
        self.root_filename = file_name

        split = os.path.split(file_name)


        self.raw_file = open(split[0]+"/raw_"+split[1], 'w+', encoding="utf-8")
        

    def add(self, string):
        self.raw_file.write(string)

    def average(self):
        self.raw_file.seek(0)
        json_dict = json.load(self.raw_file)

        average_dict = dict()
        average_dict["Experiments"] = []

        for i, exp in enumerate(json_dict["Experiments"]):
            print(f"Experiment #"+str(i))
            average_dict["Experiments"].append(exp)
            average_dict["Experiments"][i]["Averages"] = collapse_experiment(exp)
            del average_dict["Experiments"][i]["Run Count"]
            del average_dict["Experiments"][i]["Runs"]

        split = os.path.split(self.root_filename)


        self.avg_file = open(split[0]+"/avg_"+split[1], "w+")

        self.avg_file.write(json.dumps(average_dict))



ja = None

def run_strace(binary, json=False):

    command = ['sudo', '/usr/bin/perf', 'stat']

    if json==True:
        command.append('-j')

    command.append(binary)

    result = subprocess.run(command, capture_output=True, text=True)

    return result.stderr



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

    def __init__(self, binary, para_list):

        self.command = [binary]

        for para in para_list.parameters:
            self.command.append(para.format_opt())

    def get_command(self):
        return self.command

    def to_file(self, filename):
        self.command.append(">")
        self.command.append(filename)


class Parameter:
    name = None
    value = None
    curr_value = None
    idx = 0
    flag = None
    has_value = None
    ranged = None
    related = None



    def __init__(self, name, flag, values=None):
        self.name = name
        self.value = values
        self.flag = flag

        self.has_value = True if values != None else False 
        self.ranged = isinstance(values, list)

        if self.ranged == False:
            self.value = [self.value]

        related = False
        curr_value = self.value[self.idx]
    
    def __str__(self):
        if self.has_value == True:
            #return self.name + " : " + str(self.value[self.idx])
            return self.name + " : " + str(self.curr_value)
        else:
            return self.name + " : True"
    def __repr__(self):
        if self.has_value == True:
            #return self.name + " : " + str(self.value[self.idx])
            return self.name + " : " + str(self.curr_value)
        else:
            return self.name + " : True"

    def format_opt(self):
        if self.has_value == True:
            #return "-" + self.flag + " " + str(self.value[self.idx])
            return "-" + self.flag + " " + str(self.curr_value)
        else:
            return "-" + self.flag 

    def set_value(self, value):
        try:
            self.idx = self.value.index(value)
        except ValueError:
            print(f"{self.name}:{value}Requested Value not in Range")
            self.idx = 0

        if self.related == True:
            self.curr_value = value
        else:
            self.curr_value = self.value[self.idx] 


    def json_string(self):
        if self.has_value == True:
            #return "\"" + self.name + "\" : " + str(self.value[self.idx])
            return "\"" + self.name + "\" : " + str(self.curr_value)
        else:
            return "\"" + self.name + "\" : \"True\""

    def has_range(self):
        return self.ranged 

class ParameterList:
    parameters = None
    count = None
    relations = None
    def __init__(self):
        self.parameters = []
        self.count = 0
        self.relations = []

    def add_para(self, para):
        self.parameters.append(para)
        self.count += 1
    
    def set_relation(self, para1, para2):
        if para1 >= self.count or para2 >= self.count:
            print("Parameter Index not in Range")
            return
        self.relations.append((para1, para2))
        self.parameters[para1].related = True

    def fill_in_static_paras(self, tup):
        
        ranged_paras_idx = [i for i, para in enumerate(self.parameters) if para.has_range()]
    
        values = []
        ranged_idx = 0

        for i in range(self.count):
            if i in ranged_paras_idx:
                values.append(tup[ranged_idx])
                ranged_idx += 1
            elif self.parameters[i].has_value == True:
                values.append(self.parameters[i].value[0])
            else:
                values.append(None)

        #print(tuple(values))

        return tuple(values)

    def complete_para_combs(self, combs):
    
        completed_combs = []

        for each in combs:
            completed_combs.append(self.fill_in_static_paras(each))

        return completed_combs

    def resolve_relations(self, combs):
        
        if len(self.relations) == 0:
            return combs

        for i in range(len(combs)):
            temp = list(combs[i])
            for relation in self.relations:
                temp[relation[0]] *= temp[relation[1]]
                temp[relation[0]] = int(temp[relation[0]])
            combs[i] = tuple(temp)

        return combs
                


    def get_para_combinations(self):

        #Resolve Ranged Parameters
        combs = self.resolve_ranged()

        #Add Static Parameters
        combs = self.complete_para_combs(combs)

        #Resolve Relations
        combs = self.resolve_relations(combs) 

        #Remove Duplicates
        combs = list(set(combs))

        return combs


    def resolve_ranged(self):
        ranged_paras = [para.value for para in self.parameters if para.has_range()]
        #print(ranged_paras)

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

        if is_first == True:
            ret = []
            for x in comb:
                ret.append((x, ))
            return ret

        return comb

    def assign_paras(self, values):
        for i, para in enumerate(self.parameters):
            if para.has_value == True:
                para.set_value(values[i])



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
       
        f = open("output.txt", "w+")

        p = subprocess.Popen(self.command.get_command(), stdout=f)

        if self.thread_count_mode != 0:
            self.count_threads(p)
            self.analyzer.add(", ")

        p.wait()
    
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
        for para in self.parameters.parameters:
            string += str(para) + "\n"

        string += "\n\n"

        return string

    def run_experiment(self):
        self.print_prologue()
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
        for i, para in enumerate(self.parameters.parameters):
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
    dir_path = None


    def __init__(self, title, binary, parameters, filename="json.txt", runs = 1, threading = 0):
        self.binary = binary
        self.title = title
        self.date = datetime.now()
        self.date_str = self.date.strftime("%Y-%m-%d_%H:%M")
        self.parameters = parameters
        self.runs = runs
        self.threading = threading

        self.dir_path = "./"+self.title+"_"+self.date_str+"/"

        os.mkdir(self.dir_path)
        self.analyzer = JsonAnalyzer(self.dir_path+filename)
    """
    def get_para_combination(self):
        ranged_paras = [para.value for para in self.parameters if para.has_range()]
        #print(ranged_paras)
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

        if is_first == True:
            ret = []
            for x in comb:
                ret.append((x, ))
            return ret

        return comb

    def assign_paras(self, values):
        ranged_paras = [para for para in self.parameters if para.has_range()]

        if len(ranged_paras) == 0:
            return

        for i, para in enumerate(ranged_paras):
            para.set_value(values[i])
    """

    def run_benchmark(self):
        self.print_prologue()

        run_paras = self.parameters.get_para_combinations()    

        is_first = True
        for para_set in run_paras:
            if is_first == False:
                self.analyzer.add(", ")
            is_first = False
            self.parameters.assign_paras(para_set)
            experiment = ExperimentObj(self.analyzer, self.experiment_count, self.binary, self.parameters, self.runs, self.threading)
            print(experiment)
            self.experiment_count += 1
            experiment.run_experiment()




        self.print_epilogue()     
    def print_prologue(self):
        self.analyzer.add("{ \"Title\" : \"" + self.title + "\", \"Date\" : \"" + self.date_str + "\", \"Experiments\" : [ ")
    def print_epilogue(self):
        self.analyzer.add("], \"Experiment Count\" : " + str(self.experiment_count) + "}")

    def finalize(self):
        self.analyzer.raw_file.close()


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


    fig = plt.figure(layout='constrained')
    #fig = plt.figure(tight_layout=True)

    root = math.ceil(math.sqrt(len(main.value)))

    gs = gridspec.GridSpec(root, root, figure=fig)

    xlabel = second.name
    ylabel = name

    for key, idx in zip(graphs.keys(), itertools.product(range(0, root), range(0, root))):

        x = []
        y = []
        for exp in graphs[key]:
            x.append(exp["Parameters"][second.name])
            y.append(exp["Averages"][name]["avg"])

        zipped = sorted(zip(x, y))

        print(zipped)

        for i in range(len(x)):
            x[i], y[i] = zipped[i] 
        

        ax = fig.add_subplot(gs[idx[0], idx[1]])
    
        x = [str(i) for i in x]

        p = ax.bar(x, y , label=x)
        ax.set_title(f"{main.name} {key}")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.bar_label(p, label_type='center')

        ax.set(ylim=(0,upper_limit))


    plt.savefig("AVG_" + name + "_per_" + main.name +"_and_"+second.name+".png")

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

parameters = ParameterList()
parameters.add_para(Parameter("Type", "t", 1))
parameters.add_para(Parameter("Batch Size", "b", [1, 10, 100, 1000]))
parameters.add_para(Parameter("Total Requests", "r", 1000000))
parameters.add_para(Parameter("Minimum Completions", "c", 0))
parameters.add_para(Parameter("Write Size", "s", [64, 256, 1024, 4096]))
parameters.add_para(Parameter("Track Pending", "p"))
#parameters.add_para(Parameter("Plot Pending", "P"))
parameters.add_para(Parameter("Track Completions", "o"))
#parameters.add_para(Parameter("Plot Completions", "O"))
parameters.add_para(Parameter("Completions at Exit", "e"))
parameters.add_para(Parameter("Execution Time", "T"))
parameters.add_para(Parameter("Json", "j"))


##### define your benchmarking parameters #############################

thread_counting = 1  # 0 - off, 
                     # 1 - track highest thread count, 
                     # 2 - track changing values of thread count during execution 

runs = 1000            # How often is the experiment repeated per parameter set

#######################################################################



bo = BenchmarkObj("io_uring_batch_writeSize", "./write_test", filename="new_test.txt", parameters=parameters, runs=runs, threading=thread_counting)

bo.run_benchmark()

bo.analyzer.average()

plot_avg(bo.analyzer.avg_file, "Execution Time", parameters.parameters[1], parameters.parameters[4], 1)
plot_avg(bo.analyzer.avg_file, "Pending", parameters.parameters[1], parameters.parameters[4], 1)
plot_avg(bo.analyzer.avg_file, "Thread Count", parameters.parameters[1], parameters.parameters[4], 1)
plot_avg(bo.analyzer.avg_file, "Completions", parameters.parameters[1], parameters.parameters[4], 1)
plot_avg(bo.analyzer.avg_file, "Inflight Packets", parameters.parameters[1], parameters.parameters[4], 1)
  

#######################################################################
##### define your application parameters here #########################

parameters = ParameterList()
parameters.add_para(Parameter("Type", "t", 1))
parameters.add_para(Parameter("Batch Size", "b", [1, 10, 100, 1000]))
parameters.add_para(Parameter("Total Requests", "r", 1000000))
parameters.add_para(Parameter("Minimum Completions", "c", [0, 1/2, 1]))
parameters.add_para(Parameter("Write Size", "s", 256))
parameters.add_para(Parameter("Track Pending", "p"))
#parameters.add_para(Parameter("Plot Pending", "P"))
parameters.add_para(Parameter("Track Completions", "o"))
#parameters.add_para(Parameter("Plot Completions", "O"))
parameters.add_para(Parameter("Completions at Exit", "e"))
parameters.add_para(Parameter("Execution Time", "T"))
parameters.add_para(Parameter("Json", "j"))

parameters.set_relation(3, 1)

##### define your benchmarking parameters #############################

thread_counting = 1  # 0 - off, 
                     # 1 - track highest thread count, 
                     # 2 - track changing values of thread count during execution 

runs = 1000            # How often is the experiment repeated per parameter set

#######################################################################



bo = BenchmarkObj("io_uring_batch_completions", "./write_test", filename="new_test.txt", parameters=parameters, runs=runs, threading=thread_counting)

bo.run_benchmark()

bo.analyzer.average()

plot_avg(bo.analyzer.avg_file, "Execution Time", parameters.parameters[1], parameters.parameters[3], 1)
plot_avg(bo.analyzer.avg_file, "Pending", parameters.parameters[1], parameters.parameters[3], 1)
plot_avg(bo.analyzer.avg_file, "Thread Count", parameters.parameters[1], parameters.parameters[3], 1)
plot_avg(bo.analyzer.avg_file, "Completions", parameters.parameters[1], parameters.parameters[3], 1)
plot_avg(bo.analyzer.avg_file, "Inflight Packets", parameters.parameters[1], parameters.parameters[3], 1)
  
#######################################################################
##### define your application parameters here #########################

parameters = ParameterList()
parameters.add_para(Parameter("Type", "t", 0))
parameters.add_para(Parameter("Total Requests", "r", 1000000))
parameters.add_para(Parameter("Write Size", "s", [64, 256, 1024, 4096]))
parameters.add_para(Parameter("Execution Time", "T"))
parameters.add_para(Parameter("Json", "j"))

##### define your benchmarking parameters #############################

thread_counting = 0  # 0 - off, 
                     # 1 - track highest thread count, 
                     # 2 - track changing values of thread count during execution 

runs = 1000            # How often is the experiment repeated per parameter set

#######################################################################



bo = BenchmarkObj("normal_write", "./write_test", filename="new_test.txt", parameters=parameters, runs=runs, threading=thread_counting)

bo.run_benchmark()

bo.analyzer.average()

plot_avg(bo.analyzer.avg_file, "Execution Time", parameters.parameters[0], parameters.parameters[2], 1)
  










