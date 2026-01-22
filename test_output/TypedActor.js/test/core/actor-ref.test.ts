import { describe, it, expect, vi, beforeEach } from 'bun:test';
import {
    ActorRef,
    ActorPath,
    AskTimeoutError,
    AskEnvelope,
    AskReplyEnvelope,
} from './actor-ref';
import type { ActorSystem } from './actor-system';
import type { Message } from '../types/messages';

vi.mock('uuid', () => ({
    v4: () => 'test-correlation-id',
}));

const mockActorSystem = {
    registerAskPromise: vi.fn(),
    unregisterAskPromise: vi.fn(),
    settings: {
        askTimeout: 5000,
    },
} as unknown as ActorSystem;

class TestActorRef<T extends Message> extends ActorRef<T> {
    public tell = vi.fn((message: T | AskEnvelope<T>): void => {});

    constructor(path: ActorPath, system: ActorSystem) {
        super(path, system);
    }
}

describe('actor-ref', () => {
    describe('AskTimeoutError', () => {
        it('should be an instance of Error', () => {
            const error = new AskTimeoutError('test-path', 'test-id', 100);
            expect(error).toBeInstanceOf(Error);
        });

        it('should have the name "AskTimeoutError"', () => {
            const error = new AskTimeoutError('test-path', 'test-id', 100);
            expect(error.name).toBe('AskTimeoutError');
        });

        it('should construct the correct message', () => {
            const error = new AskTimeoutError('test-path', 'test-id', 100);
            const expectedMessage = `Ask operation with correlationId 'test-id' to actor 'test-path' timed out after 100ms.`;
            expect(error.message).toBe(expectedMessage);
        });
    });

    describe('AskEnvelope', () => {
        it('should store payload, correlationId, and replyTo', () => {
            const payload = { type: 'test' };
            const replyTo = new TestActorRef('/user/reply', mockActorSystem);
            const envelope = new AskEnvelope(payload, 'test-id-123', replyTo);

            expect(envelope.payload).toBe(payload);
            expect(envelope.correlationId).toBe('test-id-123');
            expect(envelope.replyTo).toBe(replyTo);
        });
    });

    describe('AskReplyEnvelope', () => {
        it('should store a success payload and correlationId', () => {
            const payload = { result: 'ok' };
            const envelope = new AskReplyEnvelope(payload, 'test-id-456');

            expect(envelope.payload).toBe(payload);
            expect(envelope.correlationId).toBe('test-id-456');
            expect(envelope.error).toBeUndefined();
        });

        it('should store an error and correlationId', () => {
            const error = new Error('Something went wrong');
            const envelope = new AskReplyEnvelope(null, 'test-id-789', error);

            expect(envelope.payload).toBeNull();
            expect(envelope.correlationId).toBe('test-id-789');
            expect(envelope.error).toBe(error);
        });
    });

    describe('ActorRef', () => {
        let testActorRef: TestActorRef<Message>;
        let promiseCallbacks: { resolve: (value: any) => void; reject: (reason?: any) => void; };

        beforeEach(() => {
            vi.clearAllMocks();
            vi.useRealTimers();

            (mockActorSystem.registerAskPromise as any).mockImplementation(
                (correlationId: string, callbacks: any) => {
                    promiseCallbacks = callbacks;
                },
            );

            testActorRef = new TestActorRef('/user/test', mockActorSystem);
        });

        describe('ask', () => {
            it('should send an AskEnvelope using the tell method', async () => {
                const message = { type: 'ping' };
                const askPromise = testActorRef.ask(message);

                expect(testActorRef.tell).toHaveBeenCalledTimes(1);
                const sentMessage = testActorRef.tell.mock.calls[0][0];
                expect(sentMessage).toBeInstanceOf(AskEnvelope);
                expect(sentMessage.payload).toBe(message);
                expect(sentMessage.correlationId).toBe('test-correlation-id');

                promiseCallbacks.resolve(new AskReplyEnvelope({ result: 'pong' }, 'test-correlation-id'));
                await askPromise;
            });

            it('should resolve with the payload when a success reply is received', async () => {
                const askPromise = testActorRef.ask({ type: 'query' });
                const replyPayload = { data: 'some-data' };

                expect(mockActorSystem.registerAskPromise).toHaveBeenCalled();

                const replyEnvelope = new AskReplyEnvelope(replyPayload, 'test-correlation-id');
                promiseCallbacks.resolve(replyEnvelope);

                await expect(askPromise).resolves.toBe(replyPayload);
                expect(mockActorSystem.unregisterAskPromise).toHaveBeenCalledWith('test-correlation-id');
            });

            it('should reject with the error when an error reply is received', async () => {
                const askPromise = testActorRef.ask({ type: 'query' });
                const error = new Error('Operation failed');

                expect(mockActorSystem.registerAskPromise).toHaveBeenCalled();

                const replyEnvelope = new AskReplyEnvelope(null, 'test-correlation-id', error);
                promiseCallbacks.resolve(replyEnvelope);

                await expect(askPromise).rejects.toThrow('Operation failed');
                expect(mockActorSystem.unregisterAskPromise).toHaveBeenCalledWith('test-correlation-id');
            });

            it('should reject with AskTimeoutError on timeout', async () => {
                vi.useFakeTimers();
                const askPromise = testActorRef.ask({ type: 'long-query' }, 100);

                vi.advanceTimersByTime(101);

                await expect(askPromise).rejects.toThrow(AskTimeoutError);
                await expect(askPromise).rejects.toThrow(
                    "Ask operation with correlationId 'test-correlation-id' to actor '/user/test' timed out after 100ms.",
                );

                expect(mockActorSystem.unregisterAskPromise).toHaveBeenCalledWith('test-correlation-id');
                vi.useRealTimers();
            });

            it('should use default timeout from actor system if none is provided', async () => {
                vi.useFakeTimers();
                const setTimeoutSpy = vi.spyOn(global, 'setTimeout');

                const askPromise = testActorRef.ask({ type: 'query' });

                expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), mockActorSystem.settings.askTimeout);

                promiseCallbacks.resolve(new AskReplyEnvelope({}, 'test-correlation-id'));
                await askPromise;
                setTimeoutSpy.mockRestore();
                vi.useRealTimers();
            });

            it('should clean up the timeout timer on successful resolution', async () => {
                vi.useFakeTimers();
                const clearTimeoutSpy = vi.spyOn(global, 'clearTimeout');

                const askPromise = testActorRef.ask({ type: 'query' });

                expect(clearTimeoutSpy).not.toHaveBeenCalled();

                promiseCallbacks.resolve(new AskReplyEnvelope({ result: 'ok' }, 'test-correlation-id'));

                await expect(askPromise).resolves.toEqual({ result: 'ok' });

                expect(clearTimeoutSpy).toHaveBeenCalledTimes(1);

                clearTimeoutSpy.mockRestore();
                vi.useRealTimers();
            });

            it('should clean up the timeout timer on rejection from an error reply', async () => {
                vi.useFakeTimers();
                const clearTimeoutSpy = vi.spyOn(global, 'clearTimeout');

                const askPromise = testActorRef.ask({ type: 'query' });

                expect(clearTimeoutSpy).not.toHaveBeenCalled();

                const error = new Error('Failed');
                promiseCallbacks.resolve(new AskReplyEnvelope(null, 'test-correlation-id', error));

                await expect(askPromise).rejects.toThrow('Failed');

                expect(clearTimeoutSpy).toHaveBeenCalledTimes(1);

                clearTimeoutSpy.mockRestore();
                vi.useRealTimers();
            });
        });
    });
});
