# TypedActor.js

A distributed actor system library for TypeScript on Bun/Node.js, inspired by Akka. It provides type-safe messaging, supervision hierarchies, persistence via event sourcing, and horizontal scaling through cluster sharding, leveraging worker threads for parallelism.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
  - [ActorSystem](#actorsystem)
  - [Actor](#actor)
  - [ActorRef](#actorref)
  - [ActorContext](#actorcontext)
  - [Messages](#messages)
  - [Supervision](#supervision)
  - [Persistence](#persistence)
  - [Cluster-Sharding)](#cluster-sharding)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

## Overview

TypedActor.js is a robust, type-safe, and distributed actor system designed for TypeScript environments running on Bun or Node.js. Inspired by Akka, it simplifies the development of concurrent and distributed applications by providing a powerful abstraction layer for managing state, concurrency, and fault tolerance.

Leveraging modern TypeScript features and Bun/Node.js worker threads, TypedActor.js allows developers to build systems that are inherently scalable, resilient, and easy to reason about.

## Features

TypedActor.js provides a robust and scalable foundation for building concurrent and distributed applications.

### Core Actor System
- Define actors using abstract classes with lifecycle hooks (`preStart`, `postStop`, `preRestart`, `postRestart`).
- Implement an actor context for creating child actors, self-referencing, and accessing system services.
- Use `readonly` tuples or objects to enforce immutable state management within actors.

### Type-Safe Messaging & Mailbox
- Utilize TypeScript generics to enforce strict message protocols between actors, preventing runtime type errors.
- Implement a message handler system using decorators (e.g., `@handle(MessageType)`) for clean, declarative message processing.
- Build a non-blocking mailbox for each actor using async iterators, providing natural backpressure handling.

### Supervision and Fault Tolerance
- Establish parent-child actor hierarchies where parents supervise their children.
- Define supervision strategies (e.g., Restart, Resume, Stop, Escalate) to automatically manage actor failures.
- Isolate failures to specific parts of the actor system to ensure overall resilience.

### Actor Persistence (Event Sourcing)
- Provide a `PersistentActor` base class that stores its state as a sequence of events.
- Actors recover their state by replaying the event journal upon startup or restart.
- Implement at-least-once message delivery guarantees for persistent actors to ensure reliability.

### Distributed Actors and Cluster Sharding
- Implement location-transparent actor references (`ActorRef`) that allow messaging between local and remote actors.
- Create a cluster membership module for nodes to discover and monitor each other.
- Introduce cluster sharding to distribute actors with unique IDs across the cluster, enabling horizontal scaling and load balancing.

## Installation

To get started with TypedActor.js, install it using your preferred package manager:

```bash
bun add typed-actor
# or
npm install typed-actor
# or
yarn add typed-actor
```

## Quick Start

This example demonstrates how to create an actor system, define an actor, send messages, and handle them using the `@handle` decorator.

First, define your message types. Messages should be immutable plain objects or classes. For actors to reply, messages often include the sender's `ActorRef`.

```typescript
// src/messages.ts
import { ActorRef } from 'typed-actor/core';

export class Ping {
  constructor(public readonly sender: ActorRef<any>) {}
}

export class Pong {
  constructor(public readonly sender: ActorRef<any>) {}
}
```

Next, create an actor that can send and receive these messages.
```typescript
// src/ping-actor.ts
import { Actor, ActorContext, ActorRef } from 'typed-actor/core';
import { handle } from 'typed-actor/decorators';
import { Ping, Pong } from './messages';

export class PingActor extends Actor<Ping | Pong> {
  constructor(context: ActorContext<Ping | Pong>) {
    super(context);
  }

  preStart() {
    console.log(`PingActor started at: ${this.context.self.path}`);
  }

  postStop() {
    console.log(`PingActor stopped.`);
  }

  @handle(Ping)
  private async onPing(message: Ping) {
    console.log(`${this.context.self.path} received Ping from ${message.sender.path}`);
    message.sender.tell(new Pong(this.context.self));
  }

  @handle(Pong)
  private async onPong(message: Pong) {
    console.log(`${this.context.self.path} received Pong from ${message.sender.path}`);
  }
}
```

Finally, create an `ActorSystem` and spawn your actors.
```typescript
// src/main.ts
import { ActorSystem } from 'typed-actor/core';
import { Ping } from './messages';
import { PingActor } from './ping-actor';

async function main() {
  const system = ActorSystem.create('MyActorSystem');

  const pingActorRef = system.spawn(PingActor, 'pingActor');
  const pongActorRef = system.spawn(PingActor, 'pongActor');

  pongActorRef.tell(new Ping(pongActorRef));

  await new Promise(resolve => setTimeout(resolve, 1000));

  await system.terminate();
  console.log("Actor system terminated.");
}

main();
```

## Core Concepts

TypedActor.js is built around several fundamental concepts that enable building resilient, scalable, and type-safe concurrent applications.

### ActorSystem
The `ActorSystem` (`src/core/actor-system.ts`) is the entry point for creating and managing actors. It's the root guardian of all actors and provides methods to `spawn` top-level actors and `terminate` the entire system. Typically, an application runs only one actor system.

### Actor
An `Actor` (`src/core/actor.ts`) is the fundamental building block. It's an object that encapsulates state and behavior, communicates exclusively through messages, and processes messages one at a time. Actors define lifecycle hooks (`preStart`, `postStop`, `preRestart`, `postRestart`) and message handling logic.

### ActorRef
An `ActorRef` (`src/core/actor-ref.ts`) is an immutable, location-transparent reference to an actor. It's the only way to communicate with an actor, decoupling the sender from the concrete actor instance. `ActorRef` provides `tell` for fire-and-forget messaging and `ask` for request-response patterns. Remote actors are accessed via `RemoteActorRef` (`src/cluster/remote/remote-actor-ref.ts`), which extends `ActorRef`.

### ActorContext
The `ActorContext` (`src/core/actor-context.ts`) provides an actor with its operational environment. It allows an actor to `spawn` child actors, `stop` them, access its own `ActorRef` (`self`), its `parent`'s `ActorRef`, and the `ActorSystem` itself. An instance of `ActorContext` is passed to the actor's constructor.

### Messages
Messages are the primary means of communication between actors. They are immutable data structures that are sent using `ActorRef.tell` or `ActorRef.ask`. Message handling within actors is typically done using the `@handle` decorator (`src/decorators/handle-message.ts`), which binds methods to specific message types, ensuring type safety.

### Supervision
Supervision (`src/supervision/strategy.ts`) is TypedActor.js's approach to fault tolerance. Actors are arranged in a hierarchy where parent actors supervise their children. When a child actor fails, its supervisor applies a defined `SupervisionStrategy` (e.g., `Restart`, `Resume`, `Stop`, `Escalate`) to handle the failure, isolating problems to specific components.

### Persistence
`PersistentActor` (`src/persistence/persistent-actor.ts`) extends the base `Actor` class to enable state recovery through event sourcing. It stores its state as a sequence of events in a `JournalPlugin` (`src/persistence/journal/journal-plugin.ts`). Upon startup or restart, the actor recovers its state by replaying these events via the `receiveRecover` method, ensuring data consistency and reliability.

### Cluster Sharding
`ClusterSharding` (`src/cluster/sharding/cluster-sharding.ts`) provides a way to distribute actors with unique identities across a cluster of nodes. This enables horizontal scaling and load balancing for entities that need to be addressable by a unique ID regardless of which node they reside on. It leverages a `MembershipProvider` (`src/cluster/membership/membership-provider.ts`) for node discovery.

## Project Structure

The project is organized into modular directories, each responsible for a specific aspect of the actor system:

```
TypedActor.js/
├── src/
│   ├── index.ts              # Main entry point for the library
│   ├── cluster/              # Distributed actor capabilities (membership, remote communication, sharding)
│   ├── core/                 # Fundamental actor system components (Actor, ActorSystem, ActorRef, Context, Mailbox)
│   ├── decorators/           # TypeScript decorators for declarative message handling
│   ├── persistence/          # Event sourcing and journal plugin interface
│   ├── supervision/          # Fault tolerance strategies
│   ├── types/                # Core type definitions and system messages
│   └── utils/                # Utility functions (e.g., logging)
├── package.json              # Project dependencies and scripts
├── tsconfig.json             # TypeScript compiler configuration
├── README.md                 # This documentation file
└── ... (other configuration and test files)
```

## Contributing

We welcome contributions! Please feel free to open issues for bugs or feature requests, and submit pull requests.

## License

This project is licensed under the MIT License.
