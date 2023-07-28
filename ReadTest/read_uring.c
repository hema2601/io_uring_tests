#include <stdio.h>
#include <stdlib.h>
#include <liburing.h>
#include <string.h>
#include <unistd.h>

#define QUEUE_DEPTH 1024


#define TOTAL BATCH * 100000
#define BATCH 80


int main(int argc, char *argv[]){

  struct io_uring ring;
  memset (&ring, 0, sizeof (ring));
  
  struct io_uring_params params;
  memset (&params, 0, sizeof params);
  params.flags = (IORING_SETUP_SINGLE_ISSUER | IORING_SETUP_DEFER_TASKRUN);
  
  int err = io_uring_queue_init_params (QUEUE_DEPTH, &ring, &params);
  if (err < 0) {
    errno = -err;
    perror("io_uring_queue_init");
    return -1;
  }

  int fd = open("./file", 0);
  
  char buffer[8];
  
  struct io_uring_sqe *sqe;
  struct io_uring_cqe *cqe;
 
  int pending = 0;
 
  for(int i = 0; i < TOTAL; i += BATCH){
    
    for(int j = 0; j < BATCH; j++){
        sqe = io_uring_get_sqe(&ring);
        io_uring_prep_read(sqe, fd, buffer, 6, 0);
    }
    io_uring_submit(&ring);

    pending += BATCH;

    io_uring_wait_cqe(&ring, &cqe);

    int head;
    int count = 0;
    io_uring_for_each_cqe(&ring, head, cqe){

      if(cqe->res < 0){
        printf("Issue with cqe, res %d\n", cqe->res);
      }
      count++;
    }

    io_uring_cq_advance(&ring, count);
    pending -= count;
  }

  while(pending){
    io_uring_wait_cqe(&ring, &cqe);

    int head;
    int count = 0;
    io_uring_for_each_cqe(&ring, head, cqe){

      if(cqe->res < 0){
        printf("Issue with cqe, res %d\n", cqe->res);
      }
      count++;
    }

    io_uring_cq_advance(&ring, count);
    pending -= count;

  }


  close(fd);

}
