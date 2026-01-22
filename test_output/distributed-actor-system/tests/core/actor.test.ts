import { describe, it, expect, beforeEach } from 'bun:test';
import { Actor } from '../../src/core/actor';
import type { ActorContext, ActorRef, ActorSystem } from '../../src/types/actor.types';

// Helper to create a mock ActorContext for testing
const createMockContext = (): ActorContext => ({
    self: {} as ActorRef<any>,
    parent: null,
    system: {} as ActorSystem,
    children: new Map<string, ActorRef<any>>(),
    name: 'test-actor'
});

// A concrete actor implementation for testing lifecycle hooks
class LifecycleTestActor extends Actor<any> {
    public preStartCalled = false;
    public postStopCalled = false;

    constructor(context: ActorContext) {
        super(context);
    }

    // Override lifecycle hooks
    protected preStart(): void {
        this.preStartCalled = true;
    }

    protected postStop(): void {
        this.postStopCalled = true;
    }

    // Public test-only methods to invoke protected lifecycle hooks
    public testInvokePreStart(): void {
        this.preStart();
    }

    public testInvokePostStop(): void {
        this.postStop();
    }
}

// A minimal actor implementation to test base class behavior
class MinimalActor extends Actor<any> {
    constructor(context: ActorContext) {
        super(context);
    }

    // Public test-only methods to invoke base protected methods
    public testInvokePreStart(): void {
        this.preStart();
    }

    public testInvokePostStop(): void {
        this.postStop();
    }
}

describe('Actor', () => {
    let mockContext: ActorContext;

    beforeEach(() => {
        mockContext = createMockContext();
    });

    it('should store the provided ActorContext upon construction', () => {
        const actor = new MinimalActor(mockContext);
        expect(actor.context).toBe(mockContext);
        expect(actor.context.name).toBe('test-actor');
    });

    it('should have a readonly context property', () => {
        const actor = new MinimalActor(mockContext);
        // This is a compile-time check, but we can try to reassign it
        // to ensure it throws in JavaScript environments that enforce it.
        // @ts-expect-error Testing readonly property
        expect(() => { actor.context = createMockContext(); }).toThrow();
    });

    describe('Lifecycle Hooks', () => {
        it('should allow subclasses to override the preStart() method', () => {
            const actor = new LifecycleTestActor(mockContext);
            expect(actor.preStartCalled).toBe(false);
            actor.testInvokePreStart();
            expect(actor.preStartCalled).toBe(true);
        });

        it('should allow subclasses to override the postStop() method', () => {
            const actor = new LifecycleTestActor(mockContext);
            expect(actor.postStopCalled).toBe(false);
            actor.testInvokePostStop();
            expect(actor.postStopCalled).toBe(true);
        });

        it('should have a default preStart() method that does nothing and does not throw', () => {
            const actor = new MinimalActor(mockContext);
            expect(() => actor.testInvokePreStart()).not.toThrow();
        });

        it('should have a default postStop() method that does nothing and does not throw', () => {
            const actor = new MinimalActor(mockContext);
            expect(() => actor.testInvokePostStop()).not.toThrow();
        });
    });

    it('should be an abstract class that cannot be instantiated directly', () => {
        // This is a compile-time check, but we can test the runtime behavior
        expect(() => {
            // @ts-expect-error Testing abstract class instantiation
            new Actor(mockContext);
        }).toThrow(TypeError); // Or a similar error indicating it's not a constructor
    });
});
