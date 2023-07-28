#include <stdlib.h>
#include <sys/socket.h>
#include <stdio.h>
#include <netinet/in.h>
#include <sys/epoll.h>
#include <unistd.h>
#include <liburing.h>

#define MAX_EVENTS 512
#define TIMEOUT 5000
#define BATCH 2048

#define NUM_BUF 4096//8192
#define MSG_LEN 2048


enum req_type {ACCEPT=1, SEND, RECV, BUF, CLOSE};

char buffers[NUM_BUF][MSG_LEN];

void add_accept(struct io_uring *ring, int fd, struct sockaddr *server, int *len){

    if(fd > 0xffff || fd < 0)
        printf("We have a problem...\n");

    struct io_uring_sqe *sqe = io_uring_get_sqe(ring);
    io_uring_prep_accept(sqe, fd & 0xffff, server, len, 0);   
    io_uring_sqe_set_data64 (sqe, ACCEPT << 16 | (fd & 0xffff));

};
void add_recv(struct io_uring *ring, int fd, int gid, int flags){
    if(fd > 0xffff || fd < 0)
        printf("We have a problem...\n");
    struct io_uring_sqe *sqe = io_uring_get_sqe(ring);
    io_uring_prep_recv(sqe, fd, NULL, MSG_LEN, 0);   
    io_uring_sqe_set_flags(sqe, flags);
    sqe->buf_group = gid;
    io_uring_sqe_set_data64 (sqe, RECV << 16 | ((uint64_t)fd&0xffff));

};
void add_send(struct io_uring *ring, int fd, int bid, int bytes){
    if(fd > 0xffff || fd < 0)
        printf("We have a problem...\n");
    if(bid > 0xffff || bid < 0)
        printf("We have a problem...\n");
    struct io_uring_sqe *sqe = io_uring_get_sqe(ring);
    io_uring_prep_send(sqe, fd & 0xffff, buffers[bid], bytes, 0);   
    io_uring_sqe_set_data64 (sqe, SEND << 16 | (bid & 0xffff));

};
void return_buf(struct io_uring *ring, int bid, int gid){
    struct io_uring_sqe *sqe = io_uring_get_sqe(ring);
    io_uring_prep_provide_buffers(sqe, buffers[bid], MSG_LEN, 1, gid, 0);
    io_uring_sqe_set_data64 (sqe, BUF << 16 );

};


void do_iou(uint32_t listening_sock, struct sockaddr *server){
    
    int len = sizeof(struct sockaddr_in);

    int group_id = 9876;

    struct io_uring_sqe *sqe;
    struct io_uring_cqe *cqe;
    struct io_uring ring;

    io_uring_queue_init(BATCH, &ring, 0);


    

    sqe = io_uring_get_sqe(&ring);
    io_uring_prep_provide_buffers(sqe, buffers, MSG_LEN, NUM_BUF, group_id, 0);
    io_uring_submit(&ring);

    io_uring_wait_cqe(&ring, &cqe);

    if(cqe->res < 0){
        perror("Providing buffers failed");
        exit(22);
    }

    io_uring_cqe_seen(&ring, cqe);
    

    add_accept(&ring, listening_sock & 0xffff, server, &len);
/*
    sqe = io_uring_get_sqe(&ring);
    io_uring_prep_accept(sqe, listening_sock, server, &len, 0);   
    io_uring_sqe_set_data64 (sqe, ACCEPT << 16 | listening_sock & 0xffff);
*/
    io_uring_submit(&ring);

    int new_sock;
    int sock;
    uint32_t bid;
    unsigned int head;
    int i;
    int closed = 0;
    while(1){
        io_uring_submit_and_wait(&ring, 1);
        
        i = 0;

        io_uring_for_each_cqe(&ring, head, cqe){
            i++;
            uint64_t u_data = cqe->user_data;
            int res = cqe->res;


            if(res < 0){
                errno = -res;
                perror("Error while processing SQE");
                exit(21);
            }

            switch(u_data >> 16){
                case ACCEPT:


                    new_sock = res;
                    printf("%d active connections!\n", ++closed);

                    if(new_sock < 0){
                        errno = -new_sock;
                        perror("Failed to accept new socket");
                        exit(21);
                    }


                    add_recv(&ring, new_sock, group_id, IOSQE_BUFFER_SELECT);
                    add_accept(&ring, u_data & 0xffff, server, &len);
                    break;

                case RECV:

                    //printf("Received message!\n");

                    if(res == -1){
                        perror("Failed to receive");
                        exit(23);
                    }

                    if(!res){
                        printf("%d connections left\n", --closed);
                        close(u_data & 0xffff);             
                        break;
                    }

                    if(cqe->flags & IORING_CQE_F_BUFFER){

                        bid = cqe->flags >> 16;

                    }else{
                        printf("Help, buffer wasnt provided... Flags: %d Bytes: %d\n", cqe->flags, cqe->res);
                        exit(25);
                    }

                    //printf("User Data: %llu\n", cqe->user_data);
                    add_send(&ring, u_data & 0xffff, bid, res);
                    add_recv(&ring, u_data & 0xffff, group_id, IOSQE_BUFFER_SELECT);
                    break;
                case SEND:

                    return_buf(&ring, u_data & 0xfff, group_id);
                    break;
                case BUF:
                    break;
                case CLOSE:
                    printf("Closed\n");
                    break;
                default:
                    printf("Weird...\n");
                    break;

            }
        }

        //printf("Count: %d\n", i);
    
        io_uring_cq_advance(&ring, i);

        //  io_uring_cqe_seen(&ring, cqe);
    }


    
}

void do_epoll(int listening_sock){

    char buffer[MSG_LEN];
    int len = sizeof(struct sockaddr_in);

    int epoll = epoll_create(MAX_EVENTS);

    if(epoll < 0){
        perror("Couldnt create epoll instance");
        exit(4);
    }

    struct epoll_event ev, events[MAX_EVENTS];

    ev.events = EPOLLIN;
    ev.data.fd = listening_sock;


    if(epoll_ctl(epoll, EPOLL_CTL_ADD, listening_sock, &ev) < 0){
        perror("Couldnt add listening socket to epoll");
        exit(5);
    }



    int num_events;

    int new_connection;
    struct sockaddr_in new_addr;

    int bytes;

    while(1){

        //get events
        num_events = epoll_wait(epoll, events, MAX_EVENTS, TIMEOUT);
        if(num_events < 0){
            perror("Error occured during epoll_wait()");
            exit(6);
        }

        //process events
        for(int i = 0; i < num_events; i++){
            if(events[i].data.fd == listening_sock){
                //do_accept
                new_connection = accept(listening_sock, (struct sockaddr *)&new_addr, &len);
                if(new_connection < 0){
                    perror("Could not open new connection");
                    exit(7);
                }
    
                
                ev.events = EPOLLIN | EPOLLET;
                ev.data.fd = new_connection;

                if(epoll_ctl(epoll, EPOLL_CTL_ADD, new_connection, &ev) < 0){
                    perror("Failed to add new connection to epoll");
                    exit(8);
                }


            }else{
                //do read and echo

                //read everything into buffer
                bytes = recv(events[i].data.fd, buffer, MSG_LEN, 0);
                if(bytes < 0){
                    epoll_ctl(epoll, EPOLL_CTL_DEL, events[i].data.fd, NULL);
                    shutdown(events[i].data.fd, SHUT_RDWR);
                    continue;
                }


                //write everything back to socket
                if( send(events[i].data.fd, buffer, bytes, 0) < 0 ){
                    epoll_ctl(epoll, EPOLL_CTL_DEL, events[i].data.fd, NULL);
                    shutdown(events[i].data.fd, SHUT_RDWR);
                    continue;
                }

            }

        }

    }

    close(epoll);

}

enum mode {EPOLL = 1, IO_URING = 2};

int main(int argc, char *argv[]){

    //Setup
    //source: https://mohsensy.github.io/programming/2019/09/25/echo-server-and-client-using-sockets-in-c.html 

    int listening_sock;
    struct sockaddr_in server;
    int len;
    int port = 1212;
    char buffer[MSG_LEN];

    if(argc < 2){
        printf("Specify Mode: 1 = EPOLL, 2 = IO_URING\nUsage: %s <mode>\n", argv[0]);
        exit(1);
    }


    listening_sock = socket(AF_INET, SOCK_STREAM, 0);


    enum mode m = atoi(argv[1]);

    if(listening_sock < 0){
        perror("Cannot create socket");
        exit(1);
    }

    server.sin_family = AF_INET;
    server.sin_addr.s_addr = INADDR_ANY;
    server.sin_port = htons(port);
    len = sizeof(server);

    if(bind(listening_sock, (struct sockaddr *)&server, len) < 0){
        perror("Cannot bind socket");
        exit(2);
    }

    if(listen(listening_sock, 10) < 0){
        perror("Listen error");
        exit(3);
    }

    switch(m){
        case EPOLL:
            do_epoll(listening_sock);
            break;
        case IO_URING:
            do_iou(listening_sock, (struct sockaddr*)&server);
            break;
        default:
            perror("Mode not implemented");
            exit(4);
    }

    close(listening_sock);


}
