import { ActorRef } from './actor-ref';
import { Actor } from './actor'; // For ActorProps type definition
import { ActorAddress, ActorProps } from '../types/actor.types';
import { Worker, isMainThread } from 'worker_threads';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import os from 'os';

// A global registry for ActorSystems to allow ActorRef instances (which might live anywhere)
// to locate their target ActorSystem for message dispatch.
// In a more complex distributed setup, this might be a service locator or message bus.
export const globalActorSystemRegistry = new Map<string, ActorSystem>();

/**
 * Configuration options for creating an ActorSystem.
 */
export interface ActorSystemConfig {
    /**
     * The number of worker threads to use for executing actors.
     * Defaults to `os.cpus().length - 1` (all but one CPU core).
     */
    workerPoolSize?: number;
    /**
     * The host address for the actor system, primarily used for remote communication.
     * Defaults to '127.0.0.1'.
     */
    host?: string;
    /**
     * The port for the actor system, primarily used for remote communication.
     * Defaults to 0 (indicating no specific port for local systems or dynamically assigned).
     */
    port?: number;
}

/**
 * Internal structure to track an actor's location within the system, managed by the main thread.
 */
interface ManagedActorInfo {
    address: ActorAddress;
    workerId: number; // The index of the worker thread managing this actor
}

/**
 * The main entry point and container for actors, managing their lifecycle, threading, and configuration.
 * Every application using this framework will start by creating an ActorSystem. It's the root of the actor hierarchy.
 */
export class ActorSystem {
    public readonly name: string;
    private readonly config: ActorSystemConfig;
    private readonly systemAddress: ActorAddress;
    private readonly actorInfoRegistry: Map<string, ManagedActorInfo> = new Map(); // Maps actor path to its managed info
    private readonly workerPool: Worker[] = [];
    private nextWorkerIdx = 0;
    private isShuttingDown = false;

    private constructor(name: string, config: ActorSystemConfig) {
        this.name = name;
        this.config = config;
        this.systemAddress = {
            protocol: 'actor',
            system: this.name,
            host: config.host || '127.0.0.1',
            port: config.port || 0,
            path: '/'
        };
        globalActorSystemRegistry.set(this.name, this);
    }

    /**
     * Creates and initializes a new actor system. This method should only be called on the main thread.
     * @param name The unique name of the actor system.
     * @param config Optional configuration for the actor system, including worker pool size and network settings.
     * @returns A promise that resolves with the initialized ActorSystem instance.
     */
    public static async create(name: string, config: ActorSystemConfig = {}): Promise<ActorSystem> {
        if (!isMainThread) {
            throw new Error("ActorSystem.create can only be called on the main thread.");
        }

        const system = new ActorSystem(name, config);

        const defaultPoolSize = Math.max(1, os.cpus().length - 1); // Use all but one CPU core by default
        const actualPoolSize = config.workerPoolSize !== undefined ? config.workerPoolSize : defaultPoolSize;

        // Path to the worker bootstrapper file. Assumes it's compiled to JS in the same directory.
        const workerBootstrapperPath = path.resolve(__dirname, 'worker-bootstrapper.js');

        for (let i = 0; i < actualPoolSize; i++) {
            const worker = new Worker(workerBootstrapperPath, {
                workerData: {
                    systemName: name,
                    systemConfig: config,
                    workerId: i,
                    systemAddress: system.systemAddress
                }
            });
            system.workerPool.push(worker);

            worker.on('error', (err) => console.error(`[ActorSystem:${system.name}] Worker ${i} experienced an error:`, err));
            worker.on('exit', (code) => {
                if (code !== 0) {
                    console.error(`[ActorSystem:${system.name}] Worker ${i} exited with code ${code}.`);
                    // In a production system, here you might implement worker restart logic
                }
            });
        }
        return system;
    }

    /**
     * Creates a new top-level actor within the system.
     * @param props The properties defining the actor, including its class constructor and arguments.
     * @param name An optional unique name for the actor. If not provided, a UUID will be used.
     * @returns An `ActorRef` to the newly created actor.
     */
    public actorOf<TMessage>(props: ActorProps<TMessage>, name?: string): ActorRef<TMessage> {
        if (this.isShuttingDown) {
            throw new Error(`[ActorSystem:${this.name}] Cannot create actor, system is shutting down.`);
        }
        if (this.workerPool.length === 0) {
            throw new Error(`[ActorSystem:${this.name}] No worker threads available to create actor.`);
        }

        const actorName = name || uuidv4();
        const actorPath = path.posix.join(this.systemAddress.path, actorName); // Use posix for consistent paths
        const fullAddress: ActorAddress = { ...this.systemAddress, path: actorPath };

        if (this.actorInfoRegistry.has(fullAddress.path)) {
            throw new Error(`Actor with path ${fullAddress.path} already exists in system ${this.name}.`);
        }

        const assignedWorkerIdx = this.nextWorkerIdx;
        const worker = this.workerPool[assignedWorkerIdx];
        this.nextWorkerIdx = (this.nextWorkerIdx + 1) % this.workerPool.length;

        this.actorInfoRegistry.set(fullAddress.path, {
            address: fullAddress,
            workerId: assignedWorkerIdx
        });

        // Create the ActorRef instance. It relies on `globalActorSystemRegistry` to find this system for dispatching.
        const actorRef = new ActorRef<TMessage>(fullAddress, this.name);

        // Instruct the worker to instantiate the actor.
        // The worker will need to resolve `props.actorClass.name` to the actual class constructor.
        worker.postMessage({
            type: 'CREATE_ACTOR',
            actorPath: fullAddress.path,
            actorClassName: props.actorClass.name,
            args: props.args || [],
            context: {
                selfAddress: fullAddress,
                parentAddress: null, // Top-level actors have no parent
                systemName: this.name
            }
        });

        return actorRef;
    }

    /**
     * Terminates the actor system and all its actors.
     * This involves sending shutdown signals to all worker threads and waiting for their graceful exit.
     * @returns A promise that resolves when the shutdown process is complete.
     */
    public async shutdown(): Promise<void> {
        if (this.isShuttingDown) {
            console.warn(`[ActorSystem:${this.name}] Shutdown already in progress.`);
            return;
        }
        this.isShuttingDown = true;
        console.log(`[ActorSystem:${this.name}] Initiating shutdown.`);

        const workerShutdownPromises = this.workerPool.map((worker, idx) => {
            return new Promise<void>((resolve) => {
                const timeout = setTimeout(() => {
                    console.warn(`[ActorSystem:${this.name}] Worker ${idx} did not exit gracefully, terminating.`);
                    worker.terminate();
                    resolve();
                }, 5000); // 5 seconds grace period for worker to shut down

                worker.on('exit', (code) => {
                    clearTimeout(timeout);
                    if (code !== 0) {
                        console.error(`[ActorSystem:${this.name}] Worker ${idx} exited with non-zero code: ${code}`);
                    }
                    resolve();
                });
                worker.on('error', (err) => {
                    clearTimeout(timeout);
                    console.error(`[ActorSystem:${this.name}] Error in worker ${idx} during shutdown:`, err);
                    resolve();
                });

                worker.postMessage({ type: 'SHUTDOWN_WORKER' });
            });
        });

        await Promise.all(workerShutdownPromises);

        this.actorInfoRegistry.clear();
        this.workerPool.length = 0; // Clear the array
        globalActorSystemRegistry.delete(this.name);
        console.log(`[ActorSystem:${this.name}] Shutdown complete.`);
    }

    /**
     * Internal method used by `ActorRef` to dispatch messages. It routes the message to the correct worker thread.
     * @param recipientAddress The address of the target actor.
     * @param message The message to send.
     * @param sender An optional `ActorRef` representing the sender of the message.
     */
    public dispatchMessage<T>(recipientAddress: ActorAddress, message: T, sender?: ActorRef<any>): void {
        if (this.isShuttingDown) {
            console.warn(`[ActorSystem:${this.name}] Cannot dispatch message, system is shutting down. Message to ${recipientAddress.path}`);
            return;
        }

        const managedInfo = this.actorInfoRegistry.get(recipientAddress.path);
        if (!managedInfo) {
            console.warn(`[ActorSystem:${this.name}] Actor not found for address: ${recipientAddress.path}. Message discarded.`);
            // In a production system, this would typically go to a Dead Letter Office.
            return;
        }

        const worker = this.workerPool[managedInfo.workerId];
        if (!worker) {
            console.error(`[ActorSystem:${this.name}] Worker ${managedInfo.workerId} not found for actor ${recipientAddress.path}. Message discarded.`);
            return;
        }

        worker.postMessage({
            type: 'TELL_MESSAGE',
            recipientPath: recipientAddress.path,
            message: message,
            senderAddress: sender ? sender.address : null
        });
    }

    /**
     * Retrieves an `ActorRef` for a given `ActorAddress`.
     * This method is primarily for internal use, e.g., when constructing `ActorContext` in workers,
     * or when an actor needs to get a reference to another actor by its address.
     * @param address The `ActorAddress` of the target actor.
     * @returns An `ActorRef` for the specified address.
     */
    public getActorRef<TMessage>(address: ActorAddress): ActorRef<TMessage> {
        // Here, we simply construct a new ActorRef as the ref itself holds enough information
        // (address and systemName) to perform dispatch via the global registry.
        // In a remote-aware system, this might involve retrieving a cached reference or creating a RemoteActorRef.
        return new ActorRef<TMessage>(address, this.name);
    }

    /**
     * Sends a message to an actor without expecting a reply (fire-and-forget).
     * This is the primary way to interact with actors.
     * @param recipient The `ActorRef` or `ActorAddress` of the target actor.
     * @param message The message to send.
     * @param sender An optional `ActorRef` representing the sender of the message.
     */
    public tell<TMessage>(recipient: ActorRef<TMessage> | ActorAddress, message: TMessage, sender?: ActorRef<any>): void {
        const recipientAddress = recipient instanceof ActorRef ? recipient.address : recipient;
        this.dispatchMessage(recipientAddress, message, sender);
    }

    /**
     * Sends a message to an actor. Alias for `tell`.
     * @param recipient The `ActorRef` or `ActorAddress` of the target actor.
     * @param message The message to send.
     * @param sender An optional `ActorRef` representing the sender of the message.
     */
    public dispatch<TMessage>(recipient: ActorRef<TMessage> | ActorAddress, message: TMessage, sender?: ActorRef<any>): void {
        this.tell(recipient, message, sender);
    }

    /**
     * Sends a message to an actor without expecting a reply (fire-and-forget).
     * This method is used by ActorRef to send messages through the system.
     * @param recipientAddress The address of the target actor.
     * @param message The message to send.
     * @param sender An optional `ActorRef` representing the sender of the message.
     */
    public sendMessage<T>(recipientAddress: ActorAddress, message: T, sender?: ActorRef<any>): void {
        this.dispatchMessage(recipientAddress, message, sender);
    }

    /**
     * Sends a message to a remote actor. This method is typically called by the remote transport
     * when an incoming message is destined for a local actor.
     * @param recipientAddress The address of the target actor.
     * @param message The message to send.
     * @param senderAddress An optional `ActorAddress` representing the sender of the message.
     */
    public deliverRemote(recipientAddress: ActorAddress, message: any, senderAddress?: ActorAddress): void {
        if (this.isShuttingDown) {
            console.warn(`[ActorSystem:${this.name}] Cannot deliver remote message, system is shutting down. Message to ${recipientAddress.path}`);
            return;
        }

        // Check if the recipient is indeed local to this system
        if (recipientAddress.system === this.name &&
            (this.config.host === undefined || recipientAddress.host === this.config.host) &&
            (this.config.port === undefined || recipientAddress.port === this.config.port)) {

            const senderRef = senderAddress ? this.getActorRef(senderAddress) : undefined;
            this.dispatchMessage(recipientAddress, message, senderRef);
        } else {
            console.warn(`[ActorSystem:${this.name}] Received remote message for non-local actor: ${JSON.stringify(recipientAddress)}. Message discarded.`);
            // In a real distributed system, this might indicate a routing error or a message
            // intended for another node. For now, we discard it if it's not strictly local.
        }
    }


    /**
     * Sends a message to an actor and expects a reply, returning a Promise.
     * This method is a placeholder and requires a full implementation for request-response messaging.
     * @param recipient The `ActorRef` or `ActorAddress` of the target actor.
     * @param message The message to send.
     * @param timeoutMs The maximum time to wait for a reply in milliseconds.
     * @returns A Promise that resolves with the reply or rejects on timeout/error.
     */
    public ask<TMessage, TResponse>(recipient: ActorRef<TMessage> | ActorAddress, message: TMessage, timeoutMs: number = 5000): Promise<TResponse> {
        console.warn(`[ActorSystem:${this.name}] 'ask' method is a placeholder and not fully implemented. Message to ${JSON.stringify(recipient)}`);
        return Promise.reject(new Error(`[ActorSystem:${this.name}] 'ask' not fully implemented or timed out after ${timeoutMs}ms.`));
    }

    /**
     * Sends a message to an actor and expects a reply, returning a Promise.
     * This method is used by ActorRef for the 'ask' pattern.
     * @param recipientAddress The address of the target actor.
     * @param message The message to send.
     * @param timeoutMs The maximum time to wait for a reply in milliseconds.
     * @returns A Promise that resolves with the reply or rejects on timeout/error.
     */
    public requestMessage<TMessage, TResponse>(recipientAddress: ActorAddress, message: TMessage, timeoutMs: number = 5000): Promise<TResponse> {
        return this.ask(this.getActorRef(recipientAddress), message, timeoutMs);
    }

    /**
     * Registers a locally managed actor's information with the system.
     * This is primarily for internal use, such as by supervision strategies to re-register actors.
     * @param actorAddress The address of the actor to register.
     * @param workerId The ID of the worker thread managing this actor.
     */
    public register(actorAddress: ActorAddress, workerId: number): void {
        if (this.isShuttingDown) {
            console.warn(`[ActorSystem:${this.name}] Cannot register actor, system is shutting down.`);
            return;
        }
        if (workerId < 0 || workerId >= this.workerPool.length) {
            throw new Error(`[ActorSystem:${this.name}] Invalid workerId ${workerId} for actor ${actorAddress.path}.`);
        }
        this.actorInfoRegistry.set(actorAddress.path, {
            address: actorAddress,
            workerId: workerId
        });
        console.log(`[ActorSystem:${this.name}] Registered actor: ${actorAddress.path} on worker ${workerId}.`);
    }

    /**
     * Returns an `ActorRef` for an actor given its path relative to the actor system's root.
     * @param actorPath The relative path of the actor (e.g., 'user/myActor').
     * @returns An `ActorRef` for the specified actor path.
     */
    public path<TMessage>(actorPath: string): ActorRef<TMessage> {
        if (actorPath.startsWith('/')) {
            actorPath = actorPath.substring(1);
        }
        const fullPath = path.posix.join(this.systemAddress.path, actorPath);
        const fullAddress: ActorAddress = { ...this.systemAddress, path: fullPath };
        return this.getActorRef(fullAddress);
    }
}
