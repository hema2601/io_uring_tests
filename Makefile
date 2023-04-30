BINARY=echo_server



all: $(BINARY)
	
$(BINARY): echo_server.c
	gcc -o $(BINARY) $^ -luring
