#include <stdio.h>
#include <stdlib.h>
#include <liburing.h>
#include <string.h>
#include <unistd.h>
#include <limits.h>
#define QUEUE_DEPTH 1024


#define TOTAL BATCH * 1000
#define BATCH 1000

#define DBG_PENDING             0x1
#define DBG_INFLIGHT            0x2
#define DBG_INFLIGHT_PLOT       0x4
#define DBG_COMPLETIONS         0x8
#define DBG_COMPLETIONS_PLOT    0x10
#define DBG_TIMER               0x20

//Regular text
#define BLK "\e[0;30m"
#define RED "\e[0;31m"
#define GRN "\e[0;32m"
#define YEL "\e[0;33m"
#define BLU "\e[0;34m"
#define MAG "\e[0;35m"
#define CYN "\e[0;36m"
#define WHT "\e[0;37m"

//Reset
#define reset "\e[0m"
#define CRESET "\e[0m"
#define COLOR_RESET "\e[0m"

const char *dbg_colours[5] = {WHT, RED, YEL, MAG, CYN}; 


#define debug_print(lvl, curr_lvl, fmt, ...) \
    do { if(lvl <= curr_lvl) fprintf(stderr, "%s%s:%d:%s(): " CRESET fmt, dbg_colours[lvl], __FILE__, \
                                    __LINE__, __func__); } while(0);

enum debug_lvl {SUPPRESS, FATAL, ERROR, WARN, DEBUG};
enum ev_types {NORMAL, IO_URING};

//data types
struct ctx;
struct event_handler;
struct io_uring_state;

//ctx functions
int init_ctx(struct ctx *my_ctx, int argc, char *argv[]);
int finalize_ctx(struct ctx *my_ctx);   

//io_uring functions
int io_uring_init(struct ctx *my_ctx, void *init_args);
int io_uring_issue(struct ctx *my_ctx);    
int io_uring_cleanup(struct ctx *my_ctx);  

//normal functions
int normal_init(struct ctx *my_ctx, void *init_args){return 0;}      //not_defined yet
int normal_issue(struct ctx *my_ctx);
int normal_cleanup(struct ctx *my_ctx){return 0;}    //not defined yet

//other functions
void print_debug_info(struct ctx *my_ctx);


struct io_uring_state{
    struct io_uring *ring;
    int batch_size;
    int min_completions;
    int pending;
};

struct io_uring_init_args{
    int batch;
    int min_completions;
};

struct event_handler{
    enum ev_types type;
    void *data;
    void *state;
    int (*init)(struct ctx*, void* init_args);
    int (*issue)(struct ctx*);
    int (*cleanup)(struct ctx*);
};

struct min_max_avg{
    int min;
    int max;
    double avg;
    int cnt;
};

struct plot_data{
    int plot_count;
    int plot_size;
    int *plot_array;
};

struct debug_state{

    int pending_requests;
    struct min_max_avg inflight;
    struct min_max_avg completions;
    struct plot_data inflight_plot;
    struct plot_data completions_plot;
    clock_t begin;
};

struct ctx{
    struct event_handler *ev;
    int total_requests;
    int fd;
    char *write_buffer;
    char write_len;
    int debug_flags;
    struct debug_state ds; 
    enum debug_lvl dbg_lvl;
    int json;
};

void plot_data_init(struct plot_data *pd);
void add_plot_data(struct plot_data *pd, int value);
void print_plot_data_json(char *name, struct plot_data *pd);

void plot_data_init(struct plot_data *pd){
    pd->plot_count = 0;
    pd->plot_size = 0;
    pd->plot_array = NULL;
}
void add_plot_data(struct plot_data *pd, int value){
    pd->plot_array[pd->plot_count++] = value;
}
void print_plot_data_json(char *name, struct plot_data *pd){
    printf("\"%s\": {\"Type\" : 2, \"Value\" : [", name);

    int is_first = 1;

    for(int i = 0; i < pd->plot_count; i++){
        if(!is_first)   printf(", ");
        is_first = 0;
        printf("%d", pd->plot_array[i]);
    }

    printf("] }");

    //[TODO] Now actually use this function
    
}

void mma_init(struct min_max_avg *mma);
void mma_compute_next(struct min_max_avg *mma, int value);
void print_mma_json(char *name, struct min_max_avg mma);

void mma_init(struct min_max_avg *mma){
    mma->cnt = 0;
    mma->max = 0;
    mma->min = INT_MAX;
    mma->avg = 0;
}

void mma_compute_next(struct min_max_avg *mma, int value){
    double avg = mma->avg;
    mma->cnt++;
    mma->avg = avg + ((value - avg) / mma->cnt);

    if(value > mma->max)    mma->max = value;
    if(value < mma->min)    mma->min = value;

}

void print_mma_json(char *name, struct min_max_avg mma){
    printf("\"%s\": {\"Type\" : 1, \"Value\" : [%lf, %d, %d, %d]}", name, mma.avg, mma.min, mma.max, mma.cnt);

}

void print_help(){
    printf("Available Options:\n \
            \t-t\tDecide type of event handler\n \
            \t\t 0 - Normal, 1 - io_uring\n \
            \t-r\tTotal number of requests (default: 10000)\n \
            \t-b\t(io_uring only) batch size for submission (default: 10)\n \
            \t-c\t(io_uring only) number of completions to await (default: 1)\n \
            \t-p\t(io_uring only) track pending requests\n \
            \t-P\t(io_uring only) plot pending requests\n \
            \t-o\t(io_uring only) track completions\n \
            \t-O\t(io_uring only) plot completions\n \
            \t-f\tspecify file name (max len: 256)\n \
            \t-e\t(io_uring_only) check pending requests at exit time\n \
            \t-v\tspecify verbosity (default: ERROR)\n \
            \t\t0 - SUPPRESS, 1 - FATAL, 2 - ERROR, 3 - WARN, 4 - DEBUG\n \
            \t-T\tprint time from initialization to end\n \
            \t-j\tprint measuring output as json\n \
            \t-s\tset write size in bytes (default: 6)\n");
}


int init_ctx(struct ctx *my_ctx, int argc, char *argv[]){
    
    struct event_handler *ev_tmp = NULL;
    void *init_args = NULL;

    int opt;

    //set defaults
    enum ev_types ev = IO_URING;
    //memcpy(my_ctx->write_buffer, "Hello\n", 6);
    my_ctx->write_len = 6;
    my_ctx->total_requests = 10000; 
    my_ctx->debug_flags = 0;
    my_ctx->dbg_lvl = ERROR;
    my_ctx->json = 0;
    int batch = 10;
    int min_completions = 1;
    int write_len = 6;
    char filename[256] = "file";

    
    //parse options
    while((opt = getopt(argc, argv, "ht:r:b:c:pPoOf:ev:Tjs:")) != -1){
        switch(opt){
            case 'h':
                print_help();
                exit(1);
            case 't':
                ev = atoi(optarg);    
                break;
            case 'r':
                my_ctx->total_requests = atoi(optarg);
                break;
            case 'b':
                batch = atoi(optarg);
                break;
            case 's':
                write_len = atoi(optarg);
                break;
            case 'c':
                min_completions = atoi(optarg);
                break;
            case 'P':
                my_ctx->debug_flags |= DBG_INFLIGHT_PLOT; 
                //intentional fallthrough 
            case 'p':
                my_ctx->debug_flags |= DBG_INFLIGHT; 
                break;
            case 'O':
                my_ctx->debug_flags |= DBG_COMPLETIONS_PLOT;
                //intentional fallthrough 
            case 'o':
                my_ctx->debug_flags |= DBG_COMPLETIONS; 
                break;
            case 'f':
                memcpy(filename, optarg, 255);
                filename[255] = '\0';
                break;
            case 'e':
                my_ctx->debug_flags |= DBG_PENDING; 
                break;
            case 'v':
                my_ctx->dbg_lvl = atoi(optarg);
                break;
            case 'T':
                my_ctx->debug_flags |= DBG_TIMER; 
                break;
            case 'j':
                my_ctx->json = 1;
                break;
            default:
                print_help();
                goto failed;
        }
    }


    my_ctx->write_buffer = (char*)calloc(sizeof(char), write_len + 2);

    memcpy(my_ctx->write_buffer, "a", write_len);
    my_ctx->write_buffer[write_len] = '\0';


 
    int fd = open(filename, O_WRONLY | O_APPEND | O_CLOEXEC | O_CREAT , 0666);
    if(fd < 0){
        perror("Failed to open file");
        goto failed;
    }

    my_ctx->fd = fd;

    ev_tmp = (struct event_handler*)malloc(sizeof(struct event_handler));

    if(!ev_tmp){
        debug_print(FATAL, my_ctx->dbg_lvl, "Out of Memory\n");
        goto failed;
    }


    switch(ev){
        case NORMAL:
            ev_tmp->init   = normal_init;
            ev_tmp->issue   = normal_issue;
            ev_tmp->cleanup = normal_cleanup;
            break;
        case IO_URING:
            ev_tmp->init   = io_uring_init;
            ev_tmp->issue   = io_uring_issue;
            ev_tmp->cleanup = io_uring_cleanup;
            init_args = malloc(sizeof(struct io_uring_init_args));
            if(!init_args){
                debug_print(FATAL, my_ctx->dbg_lvl, "Out of Memory\n");
                goto failed;
            }
            ((struct io_uring_init_args*)init_args)->batch = batch;
            ((struct io_uring_init_args*)init_args)->min_completions = min_completions;
            break;
        default:
            //LOGGING
            debug_print(FATAL, my_ctx->dbg_lvl, "Unsupported Event Type\n");
            goto failed;
    }



    my_ctx->ds.pending_requests  = 0;
    mma_init(&my_ctx->ds.inflight);
    mma_init(&my_ctx->ds.completions);
    plot_data_init(&my_ctx->ds.inflight_plot);
    plot_data_init(&my_ctx->ds.completions_plot);
    
    if(my_ctx->debug_flags & DBG_TIMER)
        my_ctx->ds.begin = clock();

    ev_tmp->type = ev;
    my_ctx->ev = ev_tmp;
    if(my_ctx->ev->init(my_ctx, init_args) < 0){
        debug_print(FATAL, my_ctx->dbg_lvl, "Failed to initialize event handler\n");
        goto failed;
    }
    
    if(init_args) free(init_args); 

    return 0;

failed:

    if(init_args) free(init_args); 
    if (ev_tmp) free(ev_tmp);
    return -1;
}

int finalize_ctx(struct ctx *my_ctx){

    if(my_ctx->ev->cleanup(my_ctx) < 0){
        debug_print(FATAL, my_ctx->dbg_lvl, "Cleaning up event handler failed\n");
        goto failed;
    }
    
    print_debug_info(my_ctx);

    free(my_ctx->ev);

    if(close(my_ctx->fd) < 0){
        debug_print(ERROR, my_ctx->dbg_lvl, "Close failed\n");
        goto failed;
    }

    if(my_ctx->ds.inflight_plot.plot_array) free(my_ctx->ds.inflight_plot.plot_array);
    if(my_ctx->ds.completions_plot.plot_array) free(my_ctx->ds.completions_plot.plot_array);

    free(my_ctx);

    return 0;

failed:
    if(my_ctx->ev)  free(my_ctx->ev);
    if(my_ctx)      free(my_ctx);

    return -1;

}
int io_uring_init(struct ctx *my_ctx, void *init_args){

    struct io_uring_init_args *args = (struct io_uring_init_args*)init_args;

    struct io_uring_state *st   = NULL;
    struct io_uring *ring       = NULL;

    st = (struct io_uring_state*)malloc(sizeof(struct io_uring_state));
    if(!st){
        debug_print(FATAL, my_ctx->dbg_lvl, "Out of Memory\n");
        goto failed;
    }

    ring = (struct io_uring*)malloc(sizeof(struct io_uring));
    if(!ring){
        debug_print(FATAL, my_ctx->dbg_lvl, "Out of Memory\n");
        goto failed;
    }
    memset (ring, 0, sizeof(*ring));

    struct io_uring_params params;
    memset (&params, 0, sizeof params);
    //params.flags = (IORING_SETUP_SINGLE_ISSUER | IORING_SETUP_DEFER_TASKRUN | IORING_SETUP_IOPOLL);
    params.flags = (IORING_SETUP_SINGLE_ISSUER | IORING_SETUP_DEFER_TASKRUN);

    int err = io_uring_queue_init_params (QUEUE_DEPTH, ring, &params);
    if (err < 0) {
        debug_print(FATAL, my_ctx->dbg_lvl, "Failed to init\n");
        goto failed;
    }

    st->ring = ring;

    //[TODO] Make adjustable
    st->batch_size = args->batch;
    if(my_ctx->total_requests % st->batch_size){
        debug_print(WARN, my_ctx->dbg_lvl, "Adjusting total requests at runtime\n");
        my_ctx->total_requests += st->batch_size - (my_ctx->total_requests % st->batch_size);
    }
    
    
    if(args->min_completions > args->batch){
        debug_print(WARN, my_ctx->dbg_lvl, "Adjusting completion number to match batch size\n");
        st->min_completions = args->batch;
    }else{
        st->min_completions = args->min_completions;
    }   

    if(my_ctx->debug_flags & DBG_INFLIGHT_PLOT){

        int plot_size = my_ctx->total_requests / st->batch_size;
        my_ctx->ds.inflight_plot.plot_array = (int*)malloc(sizeof(int) * plot_size);
        if(!my_ctx->ds.inflight_plot.plot_array){
            debug_print(FATAL, my_ctx->dbg_lvl, "Out Of Memory\n");
            goto failed;
        }
        my_ctx->ds.inflight_plot.plot_size = plot_size;
    }
    if(my_ctx->debug_flags & DBG_COMPLETIONS_PLOT){
        int plot_size = my_ctx->total_requests / st->batch_size;
        my_ctx->ds.completions_plot.plot_array = (int*)malloc(sizeof(int) * plot_size);
        if(!my_ctx->ds.completions_plot.plot_array){
            debug_print(FATAL, my_ctx->dbg_lvl, "Out Of Memory\n");
            goto failed;
        }
        my_ctx->ds.completions_plot.plot_size = plot_size;
        
    }

 
    st->pending = 0;

    my_ctx->ev->state = (void*)st;

    return 0;

failed:
    if(st)      free(st);
    if(ring)    free(ring);
    if(my_ctx->ds.inflight_plot.plot_array) free(my_ctx->ds.inflight_plot.plot_array);
    if(my_ctx->ds.completions_plot.plot_array) free(my_ctx->ds.completions_plot.plot_array);
    return -1;
}

struct io_uring_state *get_io_uring_state(struct ctx *ctx){
    if(ctx->ev->type != IO_URING)   return NULL;
    return (struct io_uring_state*)ctx->ev->state;
}

int normal_issue(struct ctx *my_ctx){
    write(my_ctx->fd, my_ctx->write_buffer, my_ctx->write_len);

    return 1;
}

int io_uring_issue(struct ctx *my_ctx){
    
    struct io_uring_state *state = get_io_uring_state(my_ctx);

    if(!state){
        debug_print(FATAL, my_ctx->dbg_lvl, "Wrong Handler Type\n");
        return -1;
    }

    int batch = state->batch_size; 
    int min_completions = state->min_completions;
    struct io_uring *ring= state->ring;
    int fd = my_ctx->fd;

    char *buffer = my_ctx->write_buffer;

    struct io_uring_sqe *sqe;
    struct io_uring_cqe *cqe;

    int *pending = &state->pending;
    int submitted = 0;

    for(int i = 0; i < batch; i++){
        sqe = io_uring_get_sqe(ring);
        if(!sqe){
            debug_print(ERROR, my_ctx->dbg_lvl, "Submission Queue is full, cannot get new sqe\n");
            break;
        }
        io_uring_prep_write(sqe, fd, buffer, my_ctx->write_len, 0);
        submitted++;
    }

    *pending += submitted;
    io_uring_submit_and_wait(ring, min_completions);


    int head;
    int count = 0;
    io_uring_for_each_cqe(ring, head, cqe){

      if(cqe->res < 0){
        debug_print(ERROR, my_ctx->dbg_lvl, "CQE returned non-zero result\n");
        errno = -cqe->res;
        perror("CQE Failed");
      }
      count++;
    }


    io_uring_cq_advance(ring, count);
    *pending -= count;
    
    //printf("Pending:\t%d\nCompleted:\t%d\n", *pending, count);

    if(my_ctx->debug_flags & DBG_INFLIGHT_PLOT){
        add_plot_data(&my_ctx->ds.inflight_plot, *pending);
        //my_ctx->ds.inflight_plot[my_ctx->ds.inflight_plot.plot_count++] = *pending;
    }
    if(my_ctx->debug_flags & DBG_INFLIGHT){
        mma_compute_next(&my_ctx->ds.inflight, *pending);
    }
    if(my_ctx->debug_flags & DBG_COMPLETIONS_PLOT){
        add_plot_data(&my_ctx->ds.completions_plot, count);
        //my_ctx->ds.completions_plot[my_ctx->ds.completions.cnt] = count;
    }
    if(my_ctx->debug_flags & DBG_COMPLETIONS){
        mma_compute_next(&my_ctx->ds.completions, count);
    }


    return submitted;

}

int io_uring_cleanup(struct ctx *my_ctx){

    struct io_uring_state *state = get_io_uring_state(my_ctx);
    if(!state){
        debug_print(FATAL, my_ctx->dbg_lvl, "Wrong Handler Type\n");
        return -1;
    }

    struct io_uring_cqe *cqe;

    if(my_ctx->debug_flags & DBG_PENDING)   my_ctx->ds.pending_requests = state->pending;

    while(state->pending){
        io_uring_wait_cqe(state->ring, &cqe);

        int head;
        int count = 0;
        io_uring_for_each_cqe(state->ring, head, cqe){

            if(cqe->res < 0){
                debug_print(ERROR, my_ctx->dbg_lvl, "CQE returned non-zero result\n");
            }
            count++;
        }

        io_uring_cq_advance(state->ring, count);
        state->pending -= count;
    }

    free(((struct io_uring_state*)(my_ctx->ev->state))->ring);
    free(my_ctx->ev->state);

    return 0;
}

int run_main_loop(struct ctx *ctx){
    
    int issued = 0;
    int ret;

    while (issued < ctx->total_requests){
        ret = ctx->ev->issue(ctx);

        if(ret < 0){
            debug_print(FATAL, ctx->dbg_lvl, "Failure while issuing requests\n");
            return -1;
        }

        issued += ret;
    }

    return 0;

}

void print_debug_info(struct ctx *my_ctx){

    if(my_ctx->json){
        int tmp = my_ctx->debug_flags;
        printf("{ ");
        
        if(my_ctx->debug_flags & DBG_PENDING){
            if(my_ctx->ev->type == IO_URING){
                printf("\"Pending\" : %d", my_ctx->ds.pending_requests);
                if(tmp ^ DBG_PENDING)
                    printf(", ");
            }
            tmp ^= DBG_PENDING;

        }
        if(my_ctx->debug_flags & DBG_INFLIGHT){
            if(my_ctx->ev->type == IO_URING){
                print_mma_json("Inflight Packets", my_ctx->ds.inflight);
                //printf("\"Inflight Packets\":{\"avg\":%lf, \"min\":%d, \"max\":%d, \"cnt\":%d}", my_ctx->ds.inflight.avg, my_ctx->ds.inflight.min, my_ctx->ds.inflight.max, my_ctx->ds.inflight.cnt);
                if(tmp ^ DBG_INFLIGHT)
                    printf(", ");
            }
            tmp ^= DBG_INFLIGHT;
            
        }
        
        if(my_ctx->debug_flags & DBG_COMPLETIONS){
            if(my_ctx->ev->type == IO_URING){
                print_mma_json("Completions", my_ctx->ds.completions);
                //printf("\"Completions\":{\"avg\":%lf, \"min\":%d, \"max\":%d, \"cnt\":%d}", my_ctx->ds.completions.avg, my_ctx->ds.completions.min, my_ctx->ds.completions.max, my_ctx->ds.completions.cnt);
                if(tmp ^ DBG_COMPLETIONS)
                    printf(", ");
            }
            tmp ^= DBG_COMPLETIONS;
        }
        if(my_ctx->debug_flags & DBG_TIMER){
            printf("\"Execution Time\" : %lf", (double)(clock() - my_ctx->ds.begin) / CLOCKS_PER_SEC);
            if(tmp ^ DBG_TIMER){
                printf(", ");
            }
            tmp ^= DBG_TIMER;
        }

        if(my_ctx->debug_flags & DBG_COMPLETIONS_PLOT){
            print_plot_data_json("Completion Plot", &my_ctx->ds.completions_plot);
            if(tmp ^ DBG_COMPLETIONS_PLOT){
                printf(", ");
            }
            tmp ^= DBG_COMPLETIONS_PLOT;
        }
        
        if(my_ctx->debug_flags & DBG_INFLIGHT_PLOT){
            print_plot_data_json("Inflight Plot", &my_ctx->ds.inflight_plot);
            if(tmp ^ DBG_INFLIGHT_PLOT){
                printf(", ");
            }
            tmp ^= DBG_INFLIGHT_PLOT;
        }
        printf("}");

    }else{

        if(my_ctx->debug_flags & DBG_PENDING)
            printf("Pending Requests at Exit Time:\t%d\n", my_ctx->ds.pending_requests);

        if(my_ctx->debug_flags & DBG_INFLIGHT)
            printf("Inflight Packets:\t\t%lf (%d, %d) # AVG (MIN, MAX)\n", my_ctx->ds.inflight.avg, my_ctx->ds.inflight.min, my_ctx->ds.inflight.max);
        if(my_ctx->debug_flags & DBG_COMPLETIONS)
            printf("Completions:\t\t\t%lf (%d, %d) # AVG (MIN, MAX)\n", my_ctx->ds.completions.avg, my_ctx->ds.completions.min, my_ctx->ds.completions.max);

        if(my_ctx->debug_flags & DBG_TIMER)
            printf("\nExecution Time:\t\t\t%lf sec.\n", (double)(clock() - my_ctx->ds.begin) / CLOCKS_PER_SEC);

    }
}


int main(int argc, char *argv[]){

    int ret;

    struct ctx *my_ctx = (struct ctx*)malloc(sizeof(struct ctx));

    if(init_ctx(my_ctx, argc, argv) < 0){
        debug_print(FATAL, my_ctx->dbg_lvl, "Failed to initialize context\n");
        free(my_ctx);
        return -1;
    }

    run_main_loop(my_ctx);



    if(finalize_ctx(my_ctx) < 0){
        debug_print(FATAL, my_ctx->dbg_lvl, "Failed to finalize context\n");
        return -1;
    }

    return 1;

}
