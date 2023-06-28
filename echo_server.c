#include <stdlib.h>
#include <sys/socket.h>
#include <stdio.h>
#include <netinet/in.h>
#include <sys/epoll.h>
#include <unistd.h>
#include <liburing.h>

#define MAX_EVENTS 512
#define TIMEOUT 5000
#define BATCH 10

void do_iou(int listening_sock, struct sockaddr *server){
    
    char buffer[1024];
    int len = sizeof(struct sockaddr_in);

    struct io_uring_sqe *sqe;
    struct io_uring_cqe *cqe;
    struct io_uring ring;

    io_uring_queue_init(BATCH, &ring, 0);

    sqe = io_uring_get_sqe(&ring);


    io_uring_prep_accept(sqe, listening_sock, server, &len, 0);   
    io_uring_sqe_set_data64 (sqe, listening_sock);

    io_uring_submit(&ring);

    int new_sock;
    int sock;
    while(1){

        if(io_uring_wait_cqe(&ring, &cqe) < 0){
            perror("Waiting for cqe failed");
            exit(22);
        }

        if(cqe->user_data == listening_sock){
            new_sock = cqe->res;
            printf("New Socket!\n");
            if(new_sock < 0){
                errno = -new_sock;
                perror("Failed to accept new socket");
                exit(21);
            }

            sqe = io_uring_get_sqe(&ring);
            io_uring_prep_accept(sqe, listening_sock, server, &len, 0);   
            io_uring_sqe_set_data64 (sqe, listening_sock);

            sqe = io_uring_get_sqe(&ring);
            io_uring_prep_recv(sqe, new_sock, buffer, 1024, 0);   
            io_uring_sqe_set_data64 (sqe, new_sock);

            io_uring_submit(&ring);

        }else if(cqe->user_data != 1){

            //printf("Received Message: %d!\n", cqe->res);
            
            if(cqe->res == -1){
                perror("Failed to receive");
                exit(23);
            }

            sqe = io_uring_get_sqe(&ring);
            io_uring_prep_send(sqe, cqe->user_data, buffer, cqe->res, 0);   
            io_uring_sqe_set_data64 (sqe, 1);

            sqe = io_uring_get_sqe(&ring);
            io_uring_prep_recv(sqe, new_sock, buffer, 1024, 0);   
            io_uring_sqe_set_data64 (sqe, cqe->user_data);

            io_uring_submit(&ring);

        }else{
           // printf("Msg was sent!\n");
        }

        io_uring_cqe_seen(&ring, cqe);
    }

 
    
}

void do_epoll(int listening_sock){

    char buffer[1024];
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
                bytes = recv(events[i].data.fd, buffer, 1024, 0);
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
    int port = 1234;
    char buffer[1024];

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
