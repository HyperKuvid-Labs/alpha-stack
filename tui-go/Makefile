.PHONY: build run vet test clean

BIN := ../bin/alphastack-tui

build:
	go build -o $(BIN) ./cmd/alphastack-tui

run: build
	$(BIN)

vet:
	go vet ./...

test:
	go test ./...

clean:
	rm -f $(BIN)
