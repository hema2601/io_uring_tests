#include <stdio.h>
#include <stdlib.h>
#include <liburing.h>
#include <string.h>
#include <unistd.h>

#define TOTAL 1000000

int main(int argc, char *argv[]){
  
  int fd = open("./file_normal", O_WRONLY | O_APPEND | O_CLOEXEC | O_CREAT, 0666);
  
  char buffer[8] = "Hello\n";
  
  for(int i = 0; i < TOTAL; i++){
    write(fd, buffer, 6);
  }


  close(fd);

}
