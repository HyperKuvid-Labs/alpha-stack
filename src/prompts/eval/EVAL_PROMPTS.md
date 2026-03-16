# Alpha Stack — Evaluation Prompt Suite

This document provides a detailed explanation of every problem statement in the Evaluation Suite. These 40 prompts (10 per language, across 4 languages) are used to benchmark Alpha Stack's code generation pipeline. They are organized by **language** and then by **difficulty tier**, with full explanations of each problem's purpose, the concepts it exercises, and design decisions behind including it.

---

## Philosophy of the Eval Suite

The evaluation suite is intentionally designed to test the *full surface area* of each language, not just trivial "hello world" scenarios. Every problem is:

1. **Self-contained** — Generates a complete, runnable project, not just a snippet.
2. **Testable** — Every problem requires a test suite the agent must make pass inside Docker.
3. **Representative** — Each problem reflects patterns that appear in real production codebases.
4. **Difficulty-stratified** — Problems progress from "beginner" to "expert" in four tiers so that the evaluation captures both base capability and ceiling.

---

## Language 1: Rust — Systems Programming

> **Domain:** Memory-safe systems programming with zero-cost abstractions.

Rust problems test the model's understanding of Rust's unique ownership and type systems — concepts that have no equivalent in most other languages. A model that can generate correct, idiomatic Rust has genuinely internalized how memory and concurrency work at a deep level.

---

### Tier 1 — Language Fundamentals & Ownership

#### Problem 1: Custom Range Iterator (`first.j2`)
**Difficulty:** Beginner

**What it is:** Implement a `StepRange<T>` struct that acts as a generic iterator over numeric ranges with a configurable step size.

**Why it's here:** The `Iterator` trait is the backbone of Rust's standard library. If a model can correctly implement it generically (with trait bounds like `T: Add + PartialOrd + Copy`) and handle edge cases like zero-step and overflow, it demonstrates genuine language fluency, not just surface-level copying.

**Key concepts tested:**
- Generic type parameters with compound trait bounds
- `Iterator` trait with associated types (`type Item`)
- Lazy evaluation (iterators don't compute eagerly)
- Composition with standard library adaptors (`.filter()`, `.collect()`)

---

#### Problem 2: Reference-Counted Smart Pointer (`second.j2`)
**Difficulty:** Beginner-Intermediate

**What it is:** Build a single-threaded `MyRc<T>` that mimics the standard library's `std::rc::Rc`. This means heap allocating the value with `Box`, using `Cell<usize>` for interior mutability of the reference count, and implementing `Clone`, `Drop`, and `Deref`.

**Why it's here:** Smart pointers are one of Rust's flagship features. This problem directly tests whether the model understands *interior mutability* (the difference between `Cell` vs `RefCell` vs `Mutex`) and the implications for `Send`/`Sync` — two critical safety bounds. A correct implementation proves the model understands why `Rc` is intentionally not thread-safe.

**Key concepts tested:**
- `Box<T>` for heap allocation
- `Cell<usize>` for interior mutability without runtime borrow checking
- Implementing `Clone`, `Drop`, `Deref` traits together in a coherent way
- Documenting why `MyRc<T>` must not implement `Send` or `Sync`

---

#### Problem 3: Binary Search Tree (`third.j2`)
**Difficulty:** Intermediate

**What it is:** Implement a generic `BinaryTree<T: Ord>` with `insert()`, `contains()`, and an in-order traversal `iter()` using a lifetime-correct borrowed iterator.

**Why it's here:** Recursive data structures in Rust are non-trivial because the compiler must know the size of every type at compile time. Using `Box<Node<T>>` for heap indirection is the idiomatic solution. The iterator is additionally complex because it must borrow the tree for its lifetime without owning it — a common pattern in Rust that trips up even experienced developers.

**Key concepts tested:**
- Recursive types using `Box` for heap indirection
- Generic types with `Ord` bounds
- Lifetime annotations in iterator implementations
- Stack-based in-order traversal to avoid recursive iterators (which Rust doesn't support directly)

---

### Tier 2 — Module Architecture & Advanced Traits

#### Problem 4: HTTP Request Parser (`fourth.j2`)
**Difficulty:** Intermediate

**What it is:** Build an incremental HTTP/1.1 parser using a state machine (RequestLine → Headers → Body → Complete). The parser must handle streaming data via a `feed(&mut self, &[u8])` method and return `Result<Option<Request>, ParseError>` where `None` means "not enough data yet".

**Why it's here:** This problem forces the model to split code across multiple modules (`parser`, `types`, `error`), design a custom error type implementing `Display + Error`, and use zero-copy parsing with lifetimes. It's a realistic, production-grade problem that mirrors how things like `hyper` or `httparse` are built.

**Key concepts tested:**
- State machine implementation
- Zero-copy design using lifetime-bound references into the input buffer
- Custom error types with `Display` and `std::error::Error` trait implementations
- Result-wrapped Option return types (`Result<Option<T>, E>`)
- Multi-module project organization

---

#### Problem 5: Single-Threaded Async Executor (`fifth.j2`)
**Difficulty:** Intermediate-Advanced

**What it is:** Build a minimal async task executor from scratch — no Tokio or async-std. It must include an `Executor` with a `VecDeque` task queue, a custom `Waker` that re-enqueues woken tasks, and a `block_on()` function. A `TimerFuture` must demonstrate delayed completion.

**Why it's here:** Most models learn async/await by using it, not implementing it. This problem forces understanding of the underlying `Future` trait, `Poll`, `Context`, and `Waker` mechanics. It separates models that truly understand async from those that just know the syntax.

**Key concepts tested:**
- `std::task::{Future, Poll, Context, Waker, Wake, RawWaker}`
- Cooperative multitasking (tasks yield by returning `Poll::Pending`)
- How wakers re-schedule tasks without OS threads
- Multiple concurrent futures running on a single thread

---

#### Problem 6: Lock-Free Ring Buffer (`sixth.j2`)
**Difficulty:** Intermediate-Advanced

**What it is:** Implement a bounded Single-Producer Single-Consumer (SPSC) queue using atomics — no `Mutex`. The API must be `try_push()` and `try_pop()` (non-blocking). Storage uses `UnsafeCell` or `MaybeUninit`. Head and tail indices use `AtomicUsize` with correct `Acquire`/`Release` memory ordering.

**Why it's here:** This is one of the hardest correct-by-default problems in Rust. Incorrect memory orderings lead to subtle bugs that only appear under specific hardware architectures or with high concurrency. It directly tests whether the model understands the x86/ARM memory model and Rust's `unsafe` system.

**Key concepts tested:**
- `AtomicUsize` with `Ordering::Acquire` and `Ordering::Release`
- `UnsafeCell` or `MaybeUninit<T>` for uninitialized storage
- `unsafe` blocks with documented safety invariants
- `Send + Sync` implementation for a custom type
- Multi-threaded correctness under producer/consumer stress testing

---

### Tier 3 — Macros & Advanced Type System

#### Problem 7: Validation Derive Macro (`seventh.j2`)
**Difficulty:** Advanced

**What it is:** Create a `#[derive(Validate)]` procedural macro using the `syn` and `quote` crates. It generates a `validate(&self) -> Result<(), Vec<String>>` method from field attributes like `#[validate(range(min=0, max=100))]`, `#[validate(length(min=2))]`, and `#[validate(email)]`.

**Why it's here:** Procedural macros are Rust's meta-programming system and require knowledge of a completely separate compilation phase. Using `syn` to parse the token stream and `quote!` to emit new code tests expertise that goes far beyond normal application development.

**Key concepts tested:**
- Procedural macro authoring (`proc-macro` crate type)
- `syn` for parsing Rust token streams
- `quote!` for code generation
- Attribute macro parsing
- Collecting and reporting multiple validation errors (not just first)

---

#### Problem 8: Typestate HTTP Builder (`eigth.j2`)
**Difficulty:** Advanced

**What it is:** Implement a builder for HTTP requests where **illegal states are a compile error**. States (`NoUrl`, `HasUrl`, `Ready`) are encoded as phantom type parameters. Calling `.send()` without first calling `.url()` produces a compiler error, not a runtime panic.

**Why it's here:** The typestate pattern demonstrates one of Rust's most powerful (and underused) capabilities: encoding business logic into the type system for zero-runtime-cost safety guarantees. This is how libraries like `reqwests` and `builder` pattern APIs in serious Rust code are structured.

**Key concepts tested:**
- `PhantomData<T>` for zero-cost type-level state tracking
- Generic struct parameters for encoding state
- Method chaining that consumes and transforms `self` between states
- Proving zero overhead via `std::mem::size_of` checks

---

#### Problem 9: JSON Serializer (`ninth.j2`)
**Difficulty:** Advanced

**What it is:** Build a custom JSON serialization library (a mini `serde_json`) with a `Serialize` trait that primitives, `String`, `Vec<T>`, `Option<T>`, and user-defined structs all implement. Supports nested/recursive structures and optional derive macros.

**Why it's here:** Designing a trait for serialization that is generic, extensible, and handles recursive structures is deeply non-trivial. It mirrors exactly the design choices that went into `serde`, which is one of the most sophisticated Rust libraries ever written. The round-trip validation via actual `serde_json` keeps it honest.

**Key concepts tested:**
- Trait design for complex, generic operations
- Blanket implementations (`impl<T: Serialize> Serialize for Vec<T>`)
- Recursive serialization of nested types
- Optional derive macro integration

---

### Tier 4 — Unsafe Rust & Systems Programming

#### Problem 10: Bump Allocator (`tenth.j2`)
**Difficulty:** Expert

**What it is:** Implement a bump (arena) allocator that becomes the program's **global memory allocator** via `#[global_allocator]`. It uses a fixed-size buffer and a simple pointer-increment strategy. Alignment must be correctly calculated and padded. `Vec` and `String` must be able to use it.

**Why it's here:** This is the pinnacle of Rust systems programming. It forces raw pointer arithmetic in `unsafe`, understanding of alignment and padding, and the `GlobalAlloc` trait — a low level interface that almost no application developer ever touches. A correct implementation demonstrates that the model genuinely understands how memory allocation works at the hardware level.

**Key concepts tested:**
- `unsafe` raw pointer arithmetic
- Memory alignment calculation (`align_up(ptr, align)`)
- `GlobalAlloc` trait (`alloc`, `dealloc` methods)
- `#[global_allocator]` static registration
- Panic on OOM, statistics tracking

---

## Language 2: CUDA — GPU Computing

> **Domain:** Parallel computing and GPU acceleration.

CUDA problems test the model's understanding of massively parallel execution on GPU hardware. These problems have no room for surface-level answers — correct CUDA code requires understanding of GPU thread hierarchies, memory hierarchies, and the specific optimizations that make GPUs fast.

---

### Tier 1 — Kernel Fundamentals & Memory Basics

#### Problem 1: Vector Operations (`first.j2`)
**Difficulty:** Beginner

**What it is:** Implement GPU kernels for element-wise vector addition, multiplication, and dot product on vectors of 10^7 elements. Test with three kernel launch configurations: 64, 256, and 1024 threads per block.

**Why it's here:** This is the canonical "Hello World" of GPU programming. It tests whether the model understands 1D thread indexing (`threadIdx.x + blockIdx.x * blockDim.x`), memory coalescing, and how to pick launch parameters. The CPU validation step catches silent computational errors.

**Key concepts tested:** 1D thread/block indexing, memory coalescing, launch parameter tuning, CPU result validation.

---

#### Problem 2: Matrix Transpose (`second.j2`)
**Difficulty:** Beginner-Intermediate

**What it is:** Transpose a 4096×4096 matrix, comparing a naive global-memory implementation against a shared-memory tiled implementation with 32×32 tiles. Profile and compare bandwidth utilization.

**Why it's here:** Matrix transpose is the canonical shared memory optimization benchmark. The naive version has poor performance due to strided writes to global memory. The tiled version uses shared memory to convert strided accesses to coalesced ones, typically achieving near-peak bandwidth. Understanding *why* matters more than just writing it.

**Key concepts tested:** 2D thread indexing, shared memory tiling, bank conflict avoidance, bandwidth profiling.

---

#### Problem 10: Separable Convolution (`tenth.j2`)
**Difficulty:** Intermediate

**What it is:** Perform 2D Gaussian convolution on a 512×512 image by separating it into two sequential 1D passes (horizontal then vertical), each using shared memory with halo (border) regions.

**Why it's here:** Convolution is the backbone of image processing and deep learning. Separable convolution reduces the computational complexity from O(k²) to O(2k) per pixel. This problem tests the understanding that some 2D operations can be decomposed for massive speedups.

**Key concepts tested:** 2D-to-1D decomposition, shared memory with halo regions, variable kernel sizes.

---

### Tier 2 — Multi-Kernel Coordination & Shared Memory

#### Problem 3: Image Processing Pipeline (`third.j2`)
**Difficulty:** Intermediate

**What it is:** Build a three-stage GPU pipeline: Gaussian blur → Sobel edge detection → Histogram equalization. Each stage is a separate `.cu` file. Compare multi-kernel vs. fused kernel approaches and measure launch overhead.

**Why it's here:** Real GPU applications are never single-kernel. This problem tests the ability to coordinate multiple kernels with data flowing between them, which requires understanding device synchronization and memory management between kernel launches.

**Key concepts tested:** Multi-kernel coordination, separate `.cu`/`.h` file organization, inter-kernel synchronization, kernel fusion tradeoffs.

---

#### Problem 4: Multi-Stage Reduction (`fourth.j2`)
**Difficulty:** Intermediate

**What it is:** Compute reduction operations (sum, mean, standard deviation) on 10^8 elements. Three optimization levels: basic divergent-branch reduction → warp shuffle instructions → sequential addressing to avoid bank conflicts. Chain kernels to compute mean and stddev in a single pass.

**Why it's here:** Parallel reduction is the most fundamental non-trivial GPU algorithm. Almost every numerical application requires it. The three-level optimization hierarchy teaches why specific GPU hardware design decisions (like warp-level divergence) force specific coding patterns.

**Key concepts tested:** Parallel reduction, `__shfl_down_sync()` warp shuffle, sequential addressing, chained kernel pipelines.

---

#### Problem 9: Spatial Partitioning System (`ninth.j2`)
**Difficulty:** Intermediate-Advanced

**What it is:** Simulate 10,000 2D particles with short-range forces using a 32×32 uniform spatial grid. Three-kernel architecture: (1) assign particles to grid cells, (2) compute forces using neighbor queries, (3) update positions.

**Why it's here:** This problem demonstrates why GPU architecture often forces you to restructure algorithms that would be "simple" on CPU. The naive O(n²) all-pairs approach is impractical; the spatial hash grid demonstrates domain-specific GPU optimization.

**Key concepts tested:** Spatial hashing, multi-kernel pipelines with data dependencies, shared memory for neighbor queries, 100x speedup demonstration.

---

### Tier 3 — Advanced Algorithms & Data Structures

#### Problem 5: Sparse Matrix Operations (`fifth.j2`)
**Difficulty:** Advanced

**What it is:** Implement Sparse Matrix-Vector Multiplication (SpMV) in CSR (Compressed Sparse Row) format on matrices with >10^6 non-zero entries. Three parallelization strategies based on row length: one thread per row (short), warp per row (medium), block per row (long).

**Why it's here:** Sparse linear algebra is one of the most challenging GPU programming domains. Row lengths in real matrices vary wildly, creating severe load imbalance. The three-strategy automatic selection directly tests understanding of GPU load balancing and dynamic workload distribution.

**Key concepts tested:** CSR sparse format, irregular parallelism, adaptive load balancing, GFLOPS and bandwidth reporting.

---

#### Problem 6: Parallel Radix Sort (`sixth.j2`)
**Difficulty:** Advanced

**What it is:** Sort 10^7 32-bit integers using radix sort with 4-bit or 8-bit radix passes. Each pass has three phases: histogram computation → prefix sum (scan) → element redistribution. Compare against CUDA Thrust.

**Why it's here:** Parallel radix sort requires implementing one of the hardest GPU primitives: parallel prefix sum (scan). Radix sort is also the fastest known sorting algorithm for GPU hardware at scale. This directly tests whether the model can implement multi-pass, multi-phase coordination at scale.

**Key concepts tested:** Parallel prefix sum, multi-pass algorithm coordination, shared memory histograms, comparison against optimized library (Thrust).

---

#### Problem 8: Mandelbrot Set Visualization (`eigth.j2`)
**Difficulty:** Intermediate-Advanced

**What it is:** Generate a 1920×1080 Mandelbrot visualization with per-pixel escape-time computation. Uses CUDA dynamic parallelism to adaptively refine regions with high iteration counts. Supports interactive zoom/pan.

**Why it's here:** Mandelbrot generation is embarrassingly parallel (each pixel is independent), making it perfect for GPUs. The dynamic parallelism aspect — where a parent kernel launches child kernels for complex regions — tests an advanced GPU feature that requires careful understanding of device-side launch overhead.

**Key concepts tested:** Per-pixel embarrassingly parallel workloads, CUDA dynamic parallelism, adaptive refinement, color mapping.

---

### Tier 4 — Complete GPU Applications

#### Problem 7: Ray Tracing Engine (`seventh.j2`)
**Difficulty:** Expert

**What it is:** Build a complete GPU path tracer rendering scenes of 100+ spheres at 1920×1080. CPU builds a Bounding Volume Hierarchy (BVH), which GPU traverses during rendering. Supports diffuse and reflective materials with recursive ray bouncing to depth 5. BVH stored in texture memory for cache optimization.

**Why it's here:** Ray tracing is the most demanding real-world GPU application category and the benchmark for GPU architecture. Implementing BVH traversal, material shading, and recursive bouncing on GPU tests every aspect of GPU programming simultaneously. This is as hard as GPU problems get.

**Key concepts tested:** BVH construction (CPU) and traversal (GPU), texture memory caching, recursive algorithms on GPU, performance metrics (rays/second), complete production application.

---

## Language 3: Go — Concurrent Systems

> **Domain:** Distributed systems, concurrency, and service architecture.

Go problems test idiomatic use of goroutines, channels, and the standard library patterns that distinguish expert Go code from beginner Go code that could have been written in any language.

---

### Tier 1 — Concurrency Primitives

#### Problem 1: Concurrent URL Fetcher (`first.j2`)
**Difficulty:** Beginner

**What it is:** Build a CLI tool that fetches a list of URLs concurrently using a bounded worker pool, tracking latency statistics (min/avg/max) and supporting context-based cancellation.

**Why it's here:** The bounded worker pool is the most fundamental Go concurrency pattern. The `context.Context` cancellation chain is how every production Go service manages request lifecycles. Getting this wrong (unbounded goroutines, goroutine leaks) is one of the most common Go mistakes in production.

**Key concepts tested:** Worker pool pattern, `sync.WaitGroup`, `context.Context` cancellation, `sync.Mutex` for statistics, channel-based job distribution.

---

#### Problem 2: Token Bucket Rate Limiter (`second.j2`)
**Difficulty:** Beginner-Intermediate

**What it is:** Implement an in-process token bucket rate limiter with both non-blocking `Allow()` and blocking `Wait()` methods. A background goroutine using `time.Ticker` refills tokens at rate R/second.

**Why it's here:** Rate limiting is a core component of any production API client or server. The token bucket algorithm is the industry standard. This problem tests goroutine lifecycle management (starting and stopping the background ticker), channel buffering, and context-based cancellation of blocking calls.

**Key concepts tested:** Token bucket algorithm, `time.Ticker`, background goroutine cleanup, blocking vs. non-blocking API design, context cancellation.

---

#### Problem 3: Concurrent LRU Cache (`third.j2`)
**Difficulty:** Intermediate

**What it is:** Build an in-memory LRU cache with concurrent access via `sync.RWMutex`, an internal doubly linked list, optional per-key TTL expiration with a background eviction goroutine, and benchmarks comparing single vs. multi-goroutine performance.

**Why it's here:** Thread-safe data structures in Go require subtle choice between `Mutex` and `RWMutex`. (The latter allows concurrent reads but exclusive writes — a critical performance distinction for read-heavy caches.) The TTL expiction goroutine also tests proper lifecycle management and resource cleanup via `Close()`.

**Key concepts tested:** `sync.RWMutex`, `container/list` doubly linked list, background goroutine for TTL expiration, proper `Close()` and resource cleanup, benchmarking.

---

### Tier 2 — Multi-Package Architecture

#### Problem 4: Task Manager REST API (`fourth.j2`)
**Difficulty:** Intermediate

**What it is:** Build a REST API with clean architecture across 4+ packages: `api/handlers` (HTTP handlers), `domain` (entity + interface), `storage/memory` (concrete implementation), and `middleware` (logging, request ID). Wired together via dependency injection.

**Why it's here:** This problem tests Go's idiomatic approach to architecture. Go favors interfaces over inheritance, and the separation between `domain.Storage` interface and `storage/memory.MemoryStorage` implementation is the Go way of achieving testability and replaceability. Many Go developers write monolithic files; this forces proper modularization.

**Key concepts tested:** Package organization, interface-based dependency injection, testability via fake/mock implementations, HTTP middleware patterns, `internal` package boundaries.

---

#### Problem 5: Job Queue System (`fifth.j2`)
**Difficulty:** Intermediate-Advanced

**What it is:** A job queue HTTP service with enqueue/poll/done/failed endpoints, dual storage backends (in-memory and file-backed via JSON log), worker lease management, background retry goroutines, and worker wakeup via `sync.Cond` or channels.

**Why it's here:** Job queues are one of the most common distributed system components, and implementing one correctly in Go requires coordinating multiple concurrent concerns: HTTP serving, background workers, storage abstraction, and lease management. `sync.Cond` is also frequently misunderstood and this tests it directly.

**Key concepts tested:** `sync.Cond` for efficient worker wakeup, dual storage abstraction, JSON persistence, lease/timeout management, multi-package coordination.

---

#### Problem 6: WebSocket Chat Server (`sixth.j2`)
**Difficulty:** Intermediate-Advanced

**What it is:** A multi-room WebSocket server using the hub pattern: a central `Hub` goroutine owns all state and communicates via channels for register, unregister, and broadcast actions. Per-client goroutines handle read/write loops.

**Why it's here:** The hub pattern is the canonical Go solution for managing shared state without locks — by funneling all mutations through a single goroutine that owns the state. This is a critically important Go architecture pattern that beginners often replace with mutexes (leading to complex, error-prone code).

**Key concepts tested:** Hub pattern (goroutine owns state, channels for communication), per-client goroutine pairs (read/write), room-based routing, transport-agnostic design.

---

### Tier 3 — Protocol & Algorithm Implementation

#### Problem 7: Custom RPC Framework (`seventh.j2`)
**Difficulty:** Advanced

**What it is:** A TCP-based RPC framework with custom binary framing (`[uint32 length][payload]`), JSON request/response format with correlation IDs, concurrent server-side dispatch, and client-side multiplexing with pending request maps and context-based timeouts.

**Why it's here:** Building a custom RPC protocol from scratch tests every layer of Go networking: TCP framing, protocol design, concurrent request/response matching, and error propagation. This is exactly what gRPC, Twirp, and similar production RPC systems are built on.

**Key concepts tested:** TCP binary framing, concurrent RPC dispatch, response correlation IDs, client-side pending request maps, context-based timeout and cancellation, partial frame handling.

---

#### Problem 8: Consistent Hashing Library (`eight.j2`)
**Difficulty:** Advanced

**What it is:** Implement consistent hashing with virtual nodes: `AddNode()`, `RemoveNode()`, `GetNode(key)`. Uses a sorted hash ring with `sort.Search` for O(log n) lookups. Pluggable hash function interface. Distributes 10,000 keys and measures rebalancing impact.

**Why it's here:** Consistent hashing is the algorithm that makes systems like DynamoDB, Cassandra, and Redis Cluster scalable without complete reshuffling on topology changes. Implementing it correctly requires understanding the virtual node trick and its role in load distribution.

**Key concepts tested:** Virtual node consistent hashing, sorted ring data structure, `sort.Search` binary search, pluggable hash interfaces, rebalancing metrics.

---

#### Problem 9: Load Balancer with Health Checks (`ninth.j2`)
**Difficulty:** Advanced

**What it is:** An HTTP reverse proxy load balancer supporting round-robin and consistent-hash routing strategies. Background goroutines perform periodic health checks, automatically removing and restoring backends. JSON/YAML config, per-backend metrics.

**Why it's here:** Load balancers are production infrastructure, and building one tests HTTP proxying, background health monitoring, dynamic topology changes, and metric collection all at once. The configurable strategy backend is also an idiomatic Go interface design exercise.

**Key concepts tested:** `httputil.ReverseProxy`, background health check goroutines, atomic backend state, pluggable load balancing strategies, per-backend metrics.

---

### Tier 4 — Distributed Systems

#### Problem 10: Raft Consensus Implementation (`tenth.j2`)
**Difficulty:** Expert

**What it is:** A simplified Raft consensus algorithm covering leader election and log replication (no snapshots). Three states: follower, candidate, leader. Communication via goroutines + channels or loopback TCP. Election timeout and heartbeats via `time.Timer`. Demo showing leader failure, re-election, and continued replication.

**Why it's here:** Raft is the go-to consensus algorithm for understanding distributed systems — it's the foundation of etcd, CockroachDB, and TiKV. Implementing it correctly requires handling every state machine transition, timer race condition, and vote-counting edge case. It is the most difficult Go problem because distributed systems bugs are subtle and timing-dependent.

**Key concepts tested:** Consensus protocol state machine, election timeouts, heartbeat timers, vote counting and quorum, log replication, leader failure and recovery, persistent state (term, votedFor, log).

---

## Language 4: TypeScript — Type-Safe Applications

> **Domain:** Advanced type system usage and API design.

TypeScript problems test the model's mastery of TypeScript's type system as a programming language in its own right — not just "JavaScript with type annotations." The highest-tier problems involve type-level computation that most TypeScript developers never encounter.

---

### Tier 1 — Type Foundations & Generics

#### Problem 1: Typed Event Emitter (`first.j2`)
**Difficulty:** Beginner

**What it is:** Build a strongly-typed event emitter where the relationship between event names and their payload types is enforced at compile time. Passing a wrong payload for an event produces a compiler error.

**Why it's here:** Event emitters are ubiquitous in JavaScript. The typed version directly tests understanding of generic constraints (`K extends keyof Events`), mapped types, and the `keyof` operator. It's a perfect introductory TypeScript problem because it has a clear correctness criterion (wrong payloads don't compile) and a clear ergonomics goal.

**Key concepts tested:** Generic type parameters, `keyof`, `EventMap` mapped types, compile-time enforcement of event payload types.

---

#### Problem 2: Schema Validation with Type Inference (`second.j2`)
**Difficulty:** Beginner-Intermediate

**What it is:** Create a validation library like Zod with chainable validators (`.string()`, `.number()`, `.object()`, `.array()`) and refinements (`.min()`, `.email()`, `.optional()`). The key feature: TypeScript infers the output type from the schema definition automatically.

**Why it's here:** Type inference from schema definitions is one of TypeScript's most powerful (and underused) features. It tests the `infer` keyword, conditional types, and the builder pattern — all fundamental to library design in TypeScript. Understanding this problem is essentially understanding how Zod and tRPC work internally.

**Key concepts tested:** `infer` keyword, conditional types for type extraction, builder pattern with type accumulation, result types with discriminated unions.

---

#### Problem 3: Result and Option Monads (`third.j2`)
**Difficulty:** Intermediate

**What it is:** Implement `Result<T, E>` and `Option<T>` types as discriminated unions (not classes). Include `.map()`, `.andThen()`, `.mapErr()`, and `.unwrap()` methods, plus type-guard `.isOk()`/`.isSome()` methods that narrow the type in conditional branches.

**Why it's here:** Functional error handling via monad types is a popular alternative to thrown exceptions. Implementing these types correctly without runtime classes (using `{ kind: 'ok', value: T }` discriminated unions) tests deep understanding of TypeScript's structural typing and type narrowing machinery.

**Key concepts tested:** Discriminated unions, type guards and narrowing, functional `.map()`/`.andThen()` chaining, `Option` and `Result` semantic correctness.

---

### Tier 2 — Advanced Generics & Component Patterns

#### Problem 4: Type-Safe Router (`fourth.j2`)
**Difficulty:** Intermediate

**What it is:** Build a router where path patterns like `/users/:userId/posts/:postId` are parsed at the type level to extract parameter names into a typed object `{ userId: string, postId: string }`. Invalid paths produce compiler errors.

**Why it's here:** Template literal types are one of TypeScript 4.1's most powerful additions. Parsing strings at the type level unlocks an entire class of ergonomic, type-safe APIs. This problem tests whether the model can manipulate string types programmatically — a skill that separates intermediate from expert TypeScript developers.

**Key concepts tested:** Template literal types, type-level string parsing, extracting union members from strings, compile-time path validation.

---

#### Problem 5: Typed Component Library (`fifth.j2`)
**Difficulty:** Intermediate

**What it is:** Create React components with strict prop typing: a generic `Button<T>` component for typed `onClick` events, a `Select<Option>` with typed `onChange`, and a `Form<Schema>` with typed field names. Invalid props produce immediate compiler errors.

**Why it's here:** React is the dominant TypeScript frontend framework, and generic React components are where TypeScript's complexity really shows. This problem tests the model's ability to design ergonomic component APIs that are as strictly typed as they are easy to use — a difficult balance.

**Key concepts tested:** Generic React components, typed event handlers, discriminated union variants (`'primary' | 'secondary'`), `@ts-expect-error` for negative testing.

---

#### Problem 6: Type-Safe State Machine (`sixth.j2`)
**Difficulty:** Intermediate-Advanced

**What it is:** Implement a finite state machine where the valid transitions are checked at the type level. Calling `.transition('INVALID_EVENT')` on a particular state produces a compiler error — not a runtime error.

**Why it's here:** State machines encoded in the type system prevent an entire class of bugs (invalid transitions) at compile time. This is the TypeScript equivalent of Rust's typestate pattern. It tests complex discriminated unions, mapped types, and conditional types working together to enforce invariants.

**Key concepts tested:** Type-level state transition validation, complex discriminated union design, mapped types for transition tables, compile-time prevention of invalid state changes.

---

### Tier 3 — Type-Level Programming & Advanced Patterns

#### Problem 7: Type-Safe Query Builder (`seventh.j2`)
**Difficulty:** Advanced

**What it is:** Build a query builder where calling `.fields('name', 'age')` narrows the return type to `{ name: string, age: number }`, removing all other fields. Schema is defined with `as const` for literal inference, and joins have type-safe foreign key validation.

**Why it's here:** Type-accumulating builder patterns are one of the most sophisticated TypeScript design patterns. Every method call transforms the accumulated type state, and the final return type is precisely typed based on the chain of calls. This tests `Mapped Types`, `Pick`, `Omit`, and how to thread types through a fluent API.

**Key concepts tested:** `as const` schema inference, field selection narrowing via `Pick`, type accumulation through builder chain, join type safety via foreign key constraints.

---

#### Problem 8: Dependency Injection Container (`eigth.j2`)
**Difficulty:** Advanced

**What it is:** Build a DI container where `.resolve('serviceName')` returns the statically correct type for each registered service, with type-level validation that all dependencies are registered and circular dependencies are detected at the type level.

**Why it's here:** Type-level dependency graphs require recursive conditional types, which are one of TypeScript's most advanced features. This is how Angular's and InversifyJS's DI containers work. A correct implementation requires understanding TypeScript's type recursion limits and how to use `infer` to extract dependency parameters.

**Key concepts tested:** Recursive conditional types, type-level dependency graphs, `infer` for parameter extraction, singleton vs transient lifetimes, circular dependency detection.

---

#### Problem 9: Deep Path Type Safety (`ninth.j2`)
**Difficulty:** Advanced

**What it is:** Create a form library where field paths like `"user.address.city"` are fully type-checked. The `Path<T>` helper generates all valid dot-notation paths as a union type. `PathValue<T, P>` extracts the value type at a given path. Supports nested arrays with index access.

**Why it's here:** Deep path types using recursive template literals are one of the hardest things in TypeScript's type system. This is the exact technology behind React Hook Form's type-safe `register()`. It tests recursion depth limits, template literal string manipulation, and conditional type branching simultaneously.

**Key concepts tested:** Recursive template literal types, `PathValue<T, P>` path extraction, array index path support, extreme type-level recursion.

---

### Tier 4 — Full-Stack Type Safety & Meta-Programming

#### Problem 10: Full-Stack Type-Safe RPC (`tenth.j2`)
**Difficulty:** Expert

**What it is:** Build a complete end-to-end RPC system (like tRPC) where the server procedure definitions automatically propagate their input and output types to the client proxy object. Changing a server handler immediately causes type errors on the client without any manual type sharing.

**Why it's here:** This is the pinnacle of TypeScript programming. This problem requires everything learned in Problems 1–9: type inference (P2), result types (P3), template literals (P4), recursive types (P8), and deep paths (P9). It tests whether the model can design a system that truly achieves end-to-end type safety — a capability that is the defining value proposition of TypeScript for full-stack teams.

**Key concepts tested:** Server-to-client type propagation via inference, Proxy types, schema-based input validation integration, transport abstraction, query vs. mutation distinction.

---

## Summary Table

| Language | Total Problems | Tier 1 | Tier 2 | Tier 3 | Tier 4 | Primary Theme |
|----------|---------------|--------|--------|--------|--------|---------------|
| Rust | 10 | Ownership, Iterators, Smart Pointers | HTTP Parser, Async Executor, Lock-Free DS | Macros, Typestate, Serializer | Unsafe, Custom Allocator | Memory Safety |
| CUDA | 10 | Vector Ops, Matrix Transpose, Convolution | Image Pipeline, Reduction, Particle Sim | Sparse Matrix, Radix Sort, Mandelbrot | Ray Tracer | Parallelism |
| Go | 10 | Worker Pool, Rate Limiter, LRU Cache | REST API, Job Queue, WebSocket | RPC, Consistent Hash, Load Balancer | Raft Consensus | Concurrency |
| TypeScript | 10 | Event Emitter, Schema Validator, Monads | Router, Component Library, State Machine | Query Builder, DI Container, Deep Paths | Full-Stack RPC | Type System |
