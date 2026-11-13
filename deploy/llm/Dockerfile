# llama.cpp's llama-server, built for the CPU it is built on (-march=native). Build it on the machine
# that runs it (e.g. the Raspberry Pi 5): a generic arm64 build is slower. Used by docker-compose.withllm.yml.
FROM debian:bookworm-slim AS build
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential cmake git ca-certificates \
 && rm -rf /var/lib/apt/lists/*
# A llama.cpp release tag: b10075 is the first one after the build the Raspberry Pi 5 MTP benchmarks used
# (docs/local-model.md). Every flag in docker-compose.withllm.yml exists in it.
ARG LLAMA_CPP_REF=b10075
RUN git clone --depth 1 --branch "${LLAMA_CPP_REF}" https://github.com/ggml-org/llama.cpp /src
WORKDIR /src
# Models are fetched by the llm-download service, so no HTTPS download support (OpenSSL) is needed.
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DBUILD_SHARED_LIBS=OFF -DLLAMA_OPENSSL=OFF \
      -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF \
 && cmake --build build -j"$(nproc)" --target llama-server

FROM debian:bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/build/bin/llama-server /usr/local/bin/llama-server
USER 10002:10002
EXPOSE 8080
ENTRYPOINT ["llama-server"]
