BINARY=read_uring read_normal 



all: $(BINARY)
	
read_uring: read_uring.c
	gcc -g -o read_uring $^ -luring

read_normal: read_normal.c
	gcc -g -o read_normal $^

clean:
	rm $(BINARY)
