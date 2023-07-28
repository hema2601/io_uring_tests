BINARY=write_uring write_normal write_uringv



all: $(BINARY)
	
write_uring: write_uring.c
	gcc -g -o write_uring $^ -luring

write_uringv: write_uringv.c
	gcc -g -o write_uringv $^ -luring

write_normal: write_normal.c
	gcc -g -o write_normal $^

clean:
	rm $(BINARY) && rm file_*
