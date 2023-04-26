#include <stdlib.h>
#include <liburing.h>

#define BATCH 10

int main(int argc, char *argv[]){

    struct io_uring_sqe *sqe;
    struct io_uring ring;

    io_uring_queue_init(BATCH, &ring, 0);


}
