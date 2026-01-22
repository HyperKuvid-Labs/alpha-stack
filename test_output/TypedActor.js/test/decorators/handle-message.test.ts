import { describe, it, expect } from 'bun:test';
import { handle, ACTOR_MESSAGE_HANDLERS } from './handle-message';

class MessageA {}
class MessageB {}
class MessageC {}

describe('handle decorator', () => {
    it('should add a single message handler mapping to the prototype', () => {
        class TestActor {
            @handle(MessageA)
            handleMessageA(msg: MessageA) {}
        }

        const handlers = (TestActor.prototype as any)[ACTOR_MESSAGE_HANDLERS];
        expect(handlers).toBeInstanceOf(Map);
        expect(handlers.size).toBe(1);
        expect(handlers.get(MessageA)).toBe('handleMessageA');
    });

    it('should add multiple message handler mappings to the prototype', () => {
        class TestActor {
            @handle(MessageA)
            handleMessageA(msg: MessageA) {}

            @handle(MessageB)
            handleMessageB(msg: MessageB) {}
        }

        const handlers = (TestActor.prototype as any)[ACTOR_MESSAGE_HANDLERS];
        expect(handlers).toBeInstanceOf(Map);
        expect(handlers.size).toBe(2);
        expect(handlers.get(MessageA)).toBe('handleMessageA');
        expect(handlers.get(MessageB)).toBe('handleMessageB');
    });

    it('should overwrite a handler mapping if the same message type is used twice', () => {
        class TestActor {
            @handle(MessageA)
            firstHandler(msg: MessageA) {}

            @handle(MessageA)
            secondHandler(msg: MessageA) {}
        }

        const handlers = (TestActor.prototype as any)[ACTOR_MESSAGE_HANDLERS];
        expect(handlers).toBeInstanceOf(Map);
        expect(handlers.size).toBe(1);
        expect(handlers.get(MessageA)).toBe('secondHandler');
    });

    it('should handle inheritance by copying parent handlers to a new map on the child', () => {
        class ParentActor {
            @handle(MessageA)
            handleA(msg: MessageA) {}
        }

        class ChildActor extends ParentActor {
            @handle(MessageB)
            handleB(msg: MessageB) {}
        }

        const parentHandlers = (ParentActor.prototype as any)[ACTOR_MESSAGE_HANDLERS];
        const childHandlers = (ChildActor.prototype as any)[ACTOR_MESSAGE_HANDLERS];

        expect(parentHandlers).toBeInstanceOf(Map);
        expect(parentHandlers.size).toBe(1);
        expect(parentHandlers.get(MessageA)).toBe('handleA');

        expect(childHandlers).toBeInstanceOf(Map);
        expect(childHandlers).not.toBe(parentHandlers);
        expect(childHandlers.size).toBe(2);
        expect(childHandlers.get(MessageA)).toBe('handleA');
        expect(childHandlers.get(MessageB)).toBe('handleB');
    });

    it('should allow a child actor to override a parent handler for the same message', () => {
        class ParentActor {
            @handle(MessageA)
            handleMessage(msg: MessageA) {}
        }

        class ChildActor extends ParentActor {
            @handle(MessageA)
            handleMessage(msg: MessageA) {}
        }

        const parentHandlers = (ParentActor.prototype as any)[ACTOR_MESSAGE_HANDLERS];
        const childHandlers = (ChildActor.prototype as any)[ACTOR_MESSAGE_HANDLERS];

        expect(childHandlers).toBeInstanceOf(Map);
        expect(childHandlers.size).toBe(1);
        expect(childHandlers.get(MessageA)).toBe('handleMessage');
        expect(childHandlers).not.toBe(parentHandlers);
    });

    it('should correctly handle a method with a symbol as its name', () => {
        const symbolHandler = Symbol('handler');

        class TestActor {
            @handle(MessageA)
            [symbolHandler](msg: MessageA) {}
        }

        const handlers = (TestActor.prototype as any)[ACTOR_MESSAGE_HANDLERS];
        expect(handlers).toBeInstanceOf(Map);
        expect(handlers.size).toBe(1);
        expect(handlers.get(MessageA)).toBe(symbolHandler);
    });

    it('should not add the handler map symbol to a class prototype if no methods are decorated', () => {
        class UnusedActor {}

        expect((UnusedActor.prototype as any)[ACTOR_MESSAGE_HANDLERS]).toBeUndefined();
    });

    it('should add handlers to the class constructor for static methods', () => {
        class StaticActor {
            @handle(MessageA)
            static handleStaticA(msg: MessageA) {}
        }

        const handlers = (StaticActor as any)[ACTOR_MESSAGE_HANDLERS];
        expect(handlers).toBeInstanceOf(Map);
        expect(handlers.size).toBe(1);
        expect(handlers.get(MessageA)).toBe('handleStaticA');
        expect((StaticActor.prototype as any)[ACTOR_MESSAGE_HANDLERS]).toBeUndefined();
    });

    it('should create a new handler map on a child even if the parent has none', () => {
        class ParentWithoutHandlers {}

        class ChildWithHandlers extends ParentWithoutHandlers {
            @handle(MessageA)
            handleA(msg: MessageA) {}
        }

        expect((ParentWithoutHandlers.prototype as any)[ACTOR_MESSAGE_HANDLERS]).toBeUndefined();

        const childHandlers = (ChildWithHandlers.prototype as any)[ACTOR_MESSAGE_HANDLERS];
        expect(childHandlers).toBeInstanceOf(Map);
        expect(childHandlers.size).toBe(1);
        expect(childHandlers.get(MessageA)).toBe('handleA');
    });

    it('should correctly handle multiple levels of inheritance', () => {
        class GrandparentActor {
            @handle(MessageA)
            handleA(msg: MessageA) {}
        }

        class ParentActor extends GrandparentActor {
            @handle(MessageB)
            handleB(msg: MessageB) {}
        }

        class ChildActor extends ParentActor {
            @handle(MessageC)
            handleC(msg: MessageC) {}
        }

        const childHandlers = (ChildActor.prototype as any)[ACTOR_MESSAGE_HANDLERS];
        expect(childHandlers).toBeInstanceOf(Map);
        expect(childHandlers.size).toBe(3);
        expect(childHandlers.get(MessageA)).toBe('handleA');
        expect(childHandlers.get(MessageB)).toBe('handleB');
        expect(childHandlers.get(MessageC)).toBe('handleC');
    });

    it('should throw a TypeError if applied to a class property', () => {
        expect(() => {
            class BadActor {
                // @ts-expect-error - Testing invalid application of a method decorator
                @handle(MessageA)
                property = 'not a method';
            }
        }).toThrow(TypeError);
    });
});
