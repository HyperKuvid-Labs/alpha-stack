typescript
import 'reflect-metadata';
import { describe, test, expect } from 'bun:test';
import { Receive, MESSAGE_HANDLERS_METADATA_KEY } from '../../src/core/decorators';

describe('Receive Decorator', () => {
    class TestMessage1 {}
    class TestMessage2 {}
    class AnotherMessage {}

    test('should register a single message handler metadata on a class constructor', () => {
        class SingleHandlerActor {
            @Receive(TestMessage1)
            handleTestMessage1(msg: TestMessage1) {
                // handler logic
            }
        }

        const handlers = Reflect.getMetadata(MESSAGE_HANDLERS_METADATA_KEY, SingleHandlerActor);

        expect(handlers).toBeInstanceOf(Array);
        expect(handlers.length).toBe(1);
        expect(handlers[0]).toEqual({ messageType: TestMessage1, methodName: 'handleTestMessage1' });
    });

    test('should register multiple message handlers on a class constructor', () => {
        class MultiHandlerActor {
            @Receive(TestMessage1)
            handler1(msg: TestMessage1) {}

            @Receive(TestMessage2)
            handler2(msg: TestMessage2) {}

            @Receive(AnotherMessage)
            anotherHandler(msg: AnotherMessage) {}
        }

        const handlers = Reflect.getMetadata(MESSAGE_HANDLERS_METADATA_KEY, MultiHandlerActor);

        expect(handlers).toBeInstanceOf(Array);
        expect(handlers.length).toBe(3);
        expect(handlers).toEqual(
            expect.arrayContaining([
                { messageType: TestMessage1, methodName: 'handler1' },
                { messageType: TestMessage2, methodName: 'handler2' },
                { messageType: AnotherMessage, methodName: 'anotherHandler' },
            ])
        );
        expect(handlers.find(h => h.messageType === TestMessage1 && h.methodName === 'handler1')).toBeDefined();
        expect(handlers.find(h => h.messageType === TestMessage2 && h.methodName === 'handler2')).toBeDefined();
        expect(handlers.find(h => h.messageType === AnotherMessage && h.methodName === 'anotherHandler')).toBeDefined();
    });

    test('should allow multiple handlers for the same message type if no duplicate check is performed by decorator', () => {
        class DuplicateHandlerActor {
            @Receive(TestMessage1)
            handlerA(msg: TestMessage1) {}

            @Receive(TestMessage1)
            handlerB(msg: TestMessage1) {}
        }
        const handlers = Reflect.getMetadata(MESSAGE_HANDLERS_METADATA_KEY, DuplicateHandlerActor);
        expect(handlers).toBeInstanceOf(Array);
        expect(handlers.length).toBe(2);
        expect(handlers).toEqual(
            expect.arrayContaining([
                { messageType: TestMessage1, methodName: 'handlerA' },
                { messageType: TestMessage1, methodName: 'handlerB' },
            ])
        );
    });

    test('should not have any message handler metadata if no decorators are used', () => {
        class NoHandlerActor {
            doSomething() {}
        }

        const handlers = Reflect.getMetadata(MESSAGE_HANDLERS_METADATA_KEY, NoHandlerActor);

        expect(handlers).toBeUndefined();
    });

    test('should handle inheritance correctly, only adding metadata to the decorated class', () => {
        class ParentActor {
            @Receive(TestMessage1)
            handleParentMessage(msg: TestMessage1) {}
        }

        class ChildActor extends ParentActor {
            @Receive(TestMessage2)
            handleChildMessage(msg: TestMessage2) {}
        }

        const parentHandlers = Reflect.getMetadata(MESSAGE_HANDLERS_METADATA_KEY, ParentActor);
        const childHandlers = Reflect.getMetadata(MESSAGE_HANDLERS_METADATA_KEY, ChildActor);

        // Verify parent metadata
        expect(parentHandlers).toBeInstanceOf(Array);
        expect(parentHandlers.length).toBe(1);
        expect(parentHandlers[0]).toEqual({ messageType: TestMessage1, methodName: 'handleParentMessage' });
        expect(parentHandlers.find(h => h.messageType === TestMessage2)).toBeUndefined();

        // Verify child metadata is separate and does not include parent's
        // The actor system's dispatcher would be responsible for walking the prototype chain
        expect(childHandlers).toBeInstanceOf(Array);
        expect(childHandlers.length).toBe(1);
        expect(childHandlers[0]).toEqual({ messageType: TestMessage2, methodName: 'handleChildMessage' });
        expect(childHandlers.find(h => h.messageType === TestMessage1)).toBeUndefined();
    });

    test('should work with message classes that have constructors and properties', () => {
        class ComplexMessage {
            constructor(public readonly payload: string) {}
        }

        class ActorWithComplexMessage {
            @Receive(ComplexMessage)
            handle(msg: ComplexMessage) {}
        }

        const handlers = Reflect.getMetadata(MESSAGE_HANDLERS_METADATA_KEY, ActorWithComplexMessage);

        expect(handlers).toBeInstanceOf(Array);
        expect(handlers.length).toBe(1);
        expect(handlers[0]).toEqual({ messageType: ComplexMessage, methodName: 'handle' });
    });

    test('should allow different actors to handle the same message type', () => {
        class SharedMessage {}

        class ActorA {
            @Receive(SharedMessage)
            handleMessage(msg: SharedMessage) {}
        }

        class ActorB {
            @Receive(SharedMessage)
            processMessage(msg: SharedMessage) {}
        }

        const handlersA = Reflect.getMetadata(MESSAGE_HANDLERS_METADATA_KEY, ActorA);
        const handlersB = Reflect.getMetadata(MESSAGE_HANDLERS_METADATA_KEY, ActorB);

        expect(handlersA).toBeInstanceOf(Array);
        expect(handlersA.length).toBe(1);
        expect(handlersA[0]).toEqual({ messageType: SharedMessage, methodName: 'handleMessage' });
        
        expect(handlersB).toBeInstanceOf(Array);
        expect(handlersB.length).toBe(1);
        expect(handlersB[0]).toEqual({ messageType: SharedMessage, methodName: 'processMessage' });
        
        expect(handlersA).not.toBe(handlersB);
    });
});
