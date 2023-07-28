BINARY=echo_server



all: $(BINARY)
	
$(BINARY): echo_server.c
	gcc -g -o $(BINARY) $^ -luring

clean:
	rm $(BINARY)
