# Distributed Actor System with Type-Safe Messaging

A TypeScript-based actor framework for Bun/Node.js, inspired by Akka. It provides type-safe message passing, supervision hierarchies, cluster sharding, and event-sourced persistence, leveraging worker threads for true parallelism.

## Table of Contents

- [Features](#features)
- [Core Concepts](#core-concepts)
- [Getting Started](#getting-started)
- [Usage Examples](#usage-examples)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Tech Stack](#tech-stack)
- [Contributing](#contributing)
- [License](#license)

## Features

### Type-Safe Actor Core & Supervision
Developers define actors by extending a generic abstract base class, specifying the protocol of messages it can receive. Message handlers are implemented as methods decorated with `@Receive(MessageType)`, ensuring compile-time type checking. Actor state is managed using immutable structures like `readonly` objects and tuples to prevent race conditions. Actors are created within a parent-child hierarchy, allowing parent actors to define supervision strategies (e.g., restart, stop, escalate) for failed children.

### Concurrent Mailbox with Backpressure
Each actor has a private mailbox that receives incoming messages. The mailbox is exposed internally as an async iterator, allowing the actor's run loop to process messages in a non-blocking, pull-based fashion. This pull-based model, combined with a configurable mailbox capacity, provides natural backpressure. Actors are executed within Bun/Node.js worker threads, ensuring CPU-bound work in one actor does not block others.

### Distributed Clustering and Sharding
Actors can be located and messaged transparently across a network of nodes using a namespaced address (e.g., `system@host:port/path/to/actor`). Cluster sharding distributes actors across available nodes based on a consistent hashing of an entity ID, enabling horizontal scalability. A gossip protocol manages cluster membership, ensuring nodes are aware of the system topology.

### Actor Persistence and Reliable Delivery
Persistent actors save their state by writing events to a durable journal (e.g., a database or log file). Upon restart or migration, an actor recovers its state by replaying all its journaled events. The framework provides primitives for at-least-once message delivery, where messages are buffered and retried until a confirmation is received from the target actor.

## Core Concepts

This framework is built around several fundamental concepts that enable building resilient, scalable, and distributed applications:

-   **ActorSystem (`src/core/actor-system.ts`)**: The main entry point and container for actors, managing their lifecycle, threading, and configuration. It's the root of the actor hierarchy.
-   **ActorRef (`src/core/actor-ref.ts`)**: An immutable, serializable, and location-transparent handle to an actor. This is the primary way to interact with actors, decoupling senders from concrete actor instances.
-   **Actor (`src/core/actor.ts`)**: The abstract base class that users must extend to implement their actor's behavior. It defines lifecycle hooks and provides access to the actor's `context`.
-   **@Receive Decorator (`src/core/decorators.ts`)**: A method decorator for declaratively defining type-safe message handlers in actor classes, ensuring strong typing for message processing.
-   **SupervisorStrategy (`src/core/supervision.ts`)**: Defines strategies (e.g., `Restart`, `Stop`, `Resume`, `Escalate`) for parent actors to handle failures in their children, creating fault-tolerant systems.
-   **Clustering**: Components like `NodeManager` (`src/cluster/node-manager.ts`), `GossipProtocol` (`src/cluster/gossip-protocol.ts`), and `ClusterSharding` (`src/cluster/sharding.ts`) facilitate transparent actor location, cluster membership management, and horizontal scalability across nodes.
-   **Persistence**: The `PersistentActor` (`src/persistence/persistent-actor.ts`) base class enables event-sourced state persistence, leveraging the `Journal` (`src/persistence/journal.ts`) interface for durable storage.
-   **Serialization (`src/remote/serialization.ts`)**: Defines the contract for serializing and deserializing messages for network transmission, crucial for remote communication.
-   **Key Types (`src/types/actor.types.ts`)**: Fundamental type definitions, including `ActorAddress` (a unique identifier for an actor), `ActorContext` (an actor's operational environment), and `ActorProps` (configuration for creating actor instances).

## Getting Started

To get started with the Distributed Actor System, ensure you have [Bun](https://bun.sh/) installed.

### Installation

```bash
bun add distributed-actor-system
# or
npm install distributed-actor-system
# or
yarn add distributed-actor-system
```

### Basic Usage

Here's a minimal example demonstrating how to create an actor system and a simple actor.

```typescript
// src/index.ts or your main application file
import { ActorSystem, Actor, Receive, ActorProps } from 'distributed-actor-system/core';

// 1. Define your message types
class GreetingMessage {
  constructor(public text: string) {}
}

class FarewellMessage {
  constructor(public text: string) {}
}

// 2. Define your actor
// It extends Actor and specifies the types of messages it can receive
class MyGreeterActor extends Actor<GreetingMessage | FarewellMessage> {

  preStart(): void {
    console.log(`[${this.context.self.address.path}] started.`);
  }

  // Use the @Receive decorator to link message types to handler methods
  @Receive(GreetingMessage)
  onGreeting(message: GreetingMessage): void {
    console.log(`[${this.context.self.address.path}] received greeting: "${message.text}"`);
  }

  @Receive(FarewellMessage)
  onFarewell(message: FarewellMessage): void {
    console.log(`[${this.context.self.address.path}] received farewell: "${message.text}"`);
  }

  postStop(): void {
    console.log(`[${this.context.self.address.path}] stopped.`);
  }
}

// 3. Create an ActorSystem and actors
async function main() {
  // Create an actor system instance
  const system = await ActorSystem.create("MyDistributedSystem");
  console.log(`Actor System "${system.name}" started.`);

  // Create a top-level actor
  const greeterActorRef = system.actorOf(new ActorProps(MyGreeterActor), "greeter");
  console.log(`Greeter Actor created at: ${greeterActorRef.address.toString()}`);

  // Send messages to the actor
  greeterActorRef.tell(new GreetingMessage("Hello from main!"));
  greeterActorRef.tell(new FarewellMessage("Goodbye for now!"));

  // Wait a bit for messages to process (in a real app, this would be managed by the system lifecycle)
  await new Promise(resolve => setTimeout(resolve, 100));

  // Shut down the actor system
  await system.shutdown();
  console.log(`Actor System "${system.name}" shut down.`);
}

main().catch(console.error);
```

To run this example:
1.  Save the code as `src/main.ts`.
2.  Compile and run with Bun:
    ```bash
    bun run src/main.ts
    ```

## Project Structure

```
distributed-actor-system/
├── .env.example
├── .gitignore
├── README.md
├── bun.lockb
├── package.json
├── tsconfig.json
└── src/
    ├── index.ts                     # Main entry point for the library
    ├── cluster/                     # Distributed clustering and sharding
    │   ├── index.ts
    │   ├── gossip-protocol.ts       # Manages cluster state dissemination
    │   ├── node-manager.ts          # Handles node lifecycle (join/leave/fail)
    │   └── sharding.ts              # Distributes actors across nodes
    ├── core/                        # Core actor model implementation
    │   ├── actor-ref.ts             # Location-transparent actor handle
    │   ├── actor-system.ts          # Main actor container and manager
    │   ├── actor.ts                 # Base class for all actors
    │   ├── decorators.ts            # @Receive decorator for message handlers
    │   ├── index.ts
    │   ├── mailbox.ts               # Actor's message queue with backpressure
    │   └── supervision.ts           # Strategies for handling child actor failures
    ├── persistence/                 # Event-sourced persistence for actors
    │   ├── index.ts
    │   ├── journal.ts               # Abstract interface for durable event storage
    │   ├── persistent-actor.ts      # Base class for actors with persistent state
    │   └── reliable-delivery.ts     # Primitives for at-least-once message delivery
    ├── remote/                      # Remote actor communication
    │   ├── index.ts
    │   ├── remote-proxy.ts          # Proxies for remote actor interaction
    │   ├── serialization.ts         # Handles message serialization/deserialization
    │   └── transport.ts             # Network communication layer
    └── types/                       # Shared TypeScript type definitions
        ├── index.ts
        ├── actor.types.ts           # Core actor model types (ActorAddress, ActorContext, etc.)
        ├── cluster.types.ts
        └── message.types.ts
```

## API Reference

Detailed API documentation generated by TypeDoc will be available [here](https://your-docs-url.com) (or generated locally).

To generate locally:
```bash
bun add -D typedoc
bun typedoc
```

## Tech Stack

**Backend:**
-   **Primary Language/Framework**: TypeScript / Bun
-   **API Design**: Library/Framework API
-   **Caching**: In-Memory Actor State
-   **Task Queues**: Actor Mailbox (Async Iterator based)

**Additional Considerations:**
-   **API Documentation**: TypeDoc
-   **Testing Frameworks**: Bun Test

## Contributing

We welcome contributions! Please see our `CONTRIBUTING.md` for guidelines on how to submit issues, features, or pull requests.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
