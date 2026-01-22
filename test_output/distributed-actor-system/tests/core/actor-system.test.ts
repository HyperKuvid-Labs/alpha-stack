import { test, expect, describe, beforeEach, afterEach, mock } from 'bun:test';
import { ActorSystem } from '../../src/core/actor-system';
import { Actor } from '../../src/core/actor';
import { ActorRef } from '../../src/core/actor-ref';
import type { ActorPath, ActorProps, Envelope } from '../../src/types/actor.types';

let mockIsMainThread = true;
const mockWorkers: any[] = [];
const mockParentPort = {
  postMessage: mock(() => {}),
  on: mock(() => {}),
};

mock.module('worker_threads', () => ({
  get isMainThread() {
    return mockIsMainThread;
  },
  Worker: mock(function (this: any, path: string, options: any) {
    this.postMessage = mock(() => {});
    this.terminate = mock(() => Promise.resolve(0));
    this.on = mock(() => {});
    mockWorkers.push(this);
    return this;
  }),
  parentPort: mockParentPort,
  workerData: { systemName: 'test-system', systemId: 'mock-system-id', workerId: 'w1' },
}));

mock.module('os', () => ({
  cpus: mock(() => [{}, {}, {}, {}]), // Mock 4 cores
}));

mock.module('uuid', () => ({
  v4: mock(() => 'mock-uuid-1234'),
}));

// A concrete actor for testing purposes
class TestActor extends Actor<any> {
  receive(message: any): void | Promise<void> {}
}

const cleanup = async () => {
  const system = ActorSystem.get('test-system');
  if (system && !(system as any).isShutdown) {
    await system.shutdown();
  }
  // Clear registry for test isolation
  (ActorSystem as any).globalActorSystemRegistry.clear();
  mockWorkers.length = 0;
  (require('worker_threads').Worker as any).mockClear();
  (require('uuid').v4 as any).mockClear();
  mockParentPort.postMessage.mockClear();
};

describe('ActorSystem', () => {
  beforeEach(() => {
    mockIsMainThread = true;
  });

  afterEach(async () => {
    await cleanup();
  });

  describe('create', () => {
    it('should create and initialize an ActorSystem', async () => {
      const system = await ActorSystem.create('test-system');
      expect(system).toBeInstanceOf(ActorSystem);
      expect(system.name).toBe('test-system');
      expect(require('worker_threads').Worker).toHaveBeenCalledTimes(4); // from os.cpus mock
    });

    it('should use the specified workerPoolSize', async () => {
      await ActorSystem.create('test-system', { workerPoolSize: 2 });
      expect(require('worker_threads').Worker).toHaveBeenCalledTimes(2);
    });

    it('should register the system in the global registry', async () => {
      const system = await ActorSystem.create('test-system');
      const retrievedSystem = ActorSystem.get('test-system');
      expect(retrievedSystem).toBe(system);
    });

    it('should throw an error if a system with the same name already exists', async () => {
      await ActorSystem.create('test-system');
      await expect(ActorSystem.create('test-system')).rejects.toThrow(
        "ActorSystem with name 'test-system' already exists.",
      );
    });

    it('should throw an error for invalid workerPoolSize', async () => {
      await expect(ActorSystem.create('test-system', { workerPoolSize: 0 })).rejects.toThrow(
        'workerPoolSize must be a positive integer.',
      );
      await expect(ActorSystem.create('test-system-2', { workerPoolSize: -1 })).rejects.toThrow(
        'workerPoolSize must be a positive integer.',
      );
    });

    it('should post initialization message to each worker', async () => {
      await ActorSystem.create('test-system', { workerPoolSize: 2 });
      expect(mockWorkers.length).toBe(2);

      const expectedInitMessage = {
        type: 'system:init',
        systemName: 'test-system',
        systemId: expect.any(String),
        workerId: expect.any(String),
      };

      expect(mockWorkers[0].postMessage).toHaveBeenCalledWith(expectedInitMessage);
      expect(mockWorkers[1].postMessage).toHaveBeenCalledWith(expectedInitMessage);
    });
  });

  describe('shutdown', () => {
    it('should terminate all workers', async () => {
      const system = await ActorSystem.create('test-system', { workerPoolSize: 2 });
      await system.shutdown();
      expect(mockWorkers[0].terminate).toHaveBeenCalled();
      expect(mockWorkers[1].terminate).toHaveBeenCalled();
    });

    it('should remove the system from the global registry', async () => {
      const system = await ActorSystem.create('test-system');
      await system.shutdown();
      const retrievedSystem = ActorSystem.get('test-system');
      expect(retrievedSystem).toBeUndefined();
    });

    it('should be idempotent', async () => {
      const system = await ActorSystem.create('test-system');
      await system.shutdown();
      await expect(system.shutdown()).toResolve();
    });
  });

  describe('actorOf', () => {
    let system: ActorSystem;

    beforeEach(async () => {
      system = await ActorSystem.create('test-system', { workerPoolSize: 2 });
    });

    it('should create an actor and return a valid ActorRef', () => {
      const actorRef = system.actorOf({ type: TestActor }, 'my-actor');
      expect(actorRef).toBeInstanceOf(ActorRef);
      expect(actorRef.path.toString()).toBe('test-system@main/user/my-actor');
    });

    it('should generate a unique name if none is provided', () => {
      const { v4 } = require('uuid');
      (v4 as any).mockReturnValueOnce('generated-actor-name');
      const actorRef = system.actorOf({ type: TestActor });
      expect(actorRef.path.name).toBe('generated-actor-name');
      expect(v4).toHaveBeenCalled();
    });

    it('should throw an error if an actor name is already in use', () => {
      system.actorOf({ type: TestActor }, 'duplicate-actor');
      expect(() => system.actorOf({ type: TestActor }, 'duplicate-actor')).toThrow(
        "Actor with name 'duplicate-actor' already exists in system 'test-system'.",
      );
    });

    it('should distribute actors across workers in a round-robin fashion', () => {
      system.actorOf({ type: TestActor }, 'actor1');
      system.actorOf({ type: TestActor }, 'actor2');
      system.actorOf({ type: TestActor }, 'actor3');

      expect(mockWorkers[0].postMessage).toHaveBeenCalledWith({
        type: 'actor:create',
        props: { type: TestActor },
        name: 'actor1',
        address: expect.stringContaining('/user/actor1'),
      });

      expect(mockWorkers[1].postMessage).toHaveBeenCalledWith({
        type: 'actor:create',
        props: { type: TestActor },
        name: 'actor2',
        address: expect.stringContaining('/user/actor2'),
      });

      expect(mockWorkers[0].postMessage).toHaveBeenCalledWith({
        type: 'actor:create',
        props: { type: TestActor },
        name: 'actor3',
        address: expect.stringContaining('/user/actor3'),
      });
    });

    it('should not be callable on a shutdown system', async () => {
      await system.shutdown();
      expect(() => system.actorOf({ type: TestActor }, 'late-actor')).toThrow(
        'ActorSystem has been shut down.',
      );
    });
  });

  describe('dispatchMessage', () => {
    let system: ActorSystem;
    let actorRef: ActorRef<TestActor>;

    beforeEach(async () => {
      system = await ActorSystem.create('test-system', { workerPoolSize: 2 });
      actorRef = system.actorOf({ type: TestActor }, 'receiver-actor'); // Goes to worker 0
    });

    it('should dispatch a message to the correct worker', () => {
      const message = { type: 'test-message', payload: 'hello' };
      const envelope: Envelope<any> = {
        target: actorRef.path,
        payload: message,
        sender: undefined,
      };
      system.dispatchMessage(envelope);

      expect(mockWorkers[0].postMessage).toHaveBeenCalledWith({
        type: 'actor:dispatch',
        envelope: envelope,
      });

      const dispatchCallsToWorker1 = mockWorkers[1].postMessage.mock.calls.filter(
        (call: any[]) => call[0].type === 'actor:dispatch',
      );
      expect(dispatchCallsToWorker1.length).toBe(0);
    });

    it('should not throw if the target actor does not exist', () => {
      const deadActorPath = actorRef.path.withName('non-existent-actor');
      const envelope: Envelope<any> = {
        target: deadActorPath,
        payload: { type: 'test', payload: 'lost' },
        sender: undefined,
      };

      expect(() => system.dispatchMessage(envelope)).not.toThrow();
    });

    it('should not dispatch if the system is shut down', async () => {
      const envelope: Envelope<any> = {
        target: actorRef.path,
        payload: { type: 'test', payload: 'late' },
        sender: undefined,
      };

      await system.shutdown();
      system.dispatchMessage(envelope);

      const dispatchCalls = mockWorkers[0].postMessage.mock.calls.filter(
        (call: any[]) => call[0].type === 'actor:dispatch',
      );
      expect(dispatchCalls.length).toBe(0);
    });
  });
});
