#include <stdio.h>
#include <stdlib.h>
#include <liburing.h>
#include <string.h>
#include <unistd.h>

#define TOTAL 8000000

int main(int argc, char *argv[]){
  
  int fd = open("./file", 0);
  
  char buffer[8];
  
  for(int i = 0; i < TOTAL; i++){
    int ret = read(fd, buffer, 6);

    if(ret < 0){
        perror("Read Problem");
    }
    

  }


  close(fd);

}
