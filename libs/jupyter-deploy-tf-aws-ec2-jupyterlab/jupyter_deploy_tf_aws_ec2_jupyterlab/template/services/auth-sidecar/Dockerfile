# Build stage
FROM golang:1.26 AS builder
ARG TARGETOS
ARG TARGETARCH

# Set working directory
WORKDIR /workspace

# Copy go.mod first to leverage Docker cache. No go.sum: the shim is stdlib-only.
COPY go.mod go.mod
RUN go mod download

# Copy the source code
COPY main.go main.go

# Build
# GOARCH is left without a default so the binary is built for the host platform (the EC2
# instance builds this via docker-compose), matching the container it ships in.
RUN CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH} go build -a -trimpath -o auth-sidecar .

# Use distroless as minimal base image to package the binary
FROM gcr.io/distroless/static:nonroot
WORKDIR /
COPY --from=builder /workspace/auth-sidecar /auth-sidecar
USER 65532:65532

# ForwardAuth endpoint
EXPOSE 4181

ENTRYPOINT ["/auth-sidecar"]
