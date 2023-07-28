BINARY=write_uring write_normal



all: $(BINARY)
	
write_uring: write_uring.c
	gcc -g -o write_uring $^ -luring

write_normal: write_normal.c
	gcc -g -o write_normal $^

clean:
	rm $(BINARY) && rm file_*
