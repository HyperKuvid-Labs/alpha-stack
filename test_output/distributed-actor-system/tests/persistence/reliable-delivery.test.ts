import { test, expect, describe, beforeEach, afterEach, vi } from 'bun:test';
import {
    ReliableDelivery,
    ReliableEnvelope,
    DeliveryConfirmation,
    OutboundMessageSentEvent,
    MessageConfirmedEvent,
    ReliableDeliveryConfirmationActor,
    OutboundMessageState,
} from '../../src/persistence/reliable-delivery';
import type { ActorSystem } from '../../src/core/actor-system';
import type { Journal } from '../../src/persistence/journal';
import type { ActorRef } from '../../src/core/actor-ref';
import type { Message, EventEnvelope, Event } from '../../src/types/message.types';
import type { ActorAddress, ActorPath } from '../../src/types/actor.types'; // Added ActorPath

const createMockActorAddress = (pathStr: string): ActorAddress => ({
    protocol: 'akka',
    systemName: 'system',
    host: 'localhost',
    port: 2552,
    path: pathStr,
    toString: () => `akka://system@localhost:2552/${pathStr}`,
    equals: vi.fn((other: any) => other && other.path === pathStr),
});

const createMockActorRef = (address: ActorAddress): ActorRef<any> => ({
    address: address,
    tell: vi.fn(),
    ask: vi.fn().mockResolvedValue(undefined), // Mock ask to return a promise
} as unknown as ActorRef<any>); // Cast to ActorRef<any> as some properties like path are getters and not direct fields in the mock

const mockTargetActorAddress = createMockActorAddress('user/target');
const mockSenderActorAddress = createMockActorAddress('user/sender');
const mockConfirmationActorAddress = createMockActorAddress('user/rd-confirm');

const mockActorRef = createMockActorRef(mockTargetActorAddress);
const mockSenderRef = createMockActorRef(mockSenderActorAddress);
const mockConfirmationActorRef = createMockActorRef(mockConfirmationActorAddress);

const mockJournal = {
    writeEvents: vi.fn<[EventEnvelope<ReliableDeliveryEvent>[]], Promise<void>>(),
    replayEvents: vi.fn<[string, number], AsyncIterable<EventEnvelope<ReliableDeliveryEvent>>>(),
};

const mockActorSystem = {
    actorOf: vi.fn().mockReturnValue(mockConfirmationActorRef),
    actorSelection: vi.fn((address: ActorAddress | string) => {
        // actorSelection can take ActorAddress or string path
        const addressPath = typeof address === 'string' ? address : address.path;

        if (addressPath === mockTargetActorAddress.path) return mockActorRef;
        if (addressPath === mockSenderActorAddress.path) return mockSenderRef;
        if (addressPath === mockConfirmationActorAddress.path) return mockConfirmationActorRef;
        if (addressPath.startsWith('path/target')) {
            return createMockActorRef(createMockActorAddress(addressPath));
        }
        // Return a mock for dead letters or other default if needed
        return createMockActorRef(createMockActorAddress('dead/letters'));
    }),
    generateUniqueId: vi.fn(),
    eventStream: { publish: vi.fn() },
    log: {
        warn: vi.fn(),
    },
    deadLetters: createMockActorRef(createMockActorAddress('dead/letters')) // Add deadLetters mock
} as unknown as ActorSystem;

describe('ReliableDelivery', () => {
    let rd: ReliableDelivery;

    beforeEach(() => {
        vi.resetAllMocks();
        mockJournal.writeEvents.mockResolvedValue(undefined);
        mockJournal.replayEvents.mockReturnValue((async function* () {})());
        mockActorSystem.generateUniqueId.mockReturnValue('mock-uuid-1');
        rd = new ReliableDelivery(mockActorSystem, mockJournal as unknown as Journal, { retryIntervalMs: 5000, maxRetries: 3 });
        // The actual ReliableDelivery.create is async and would initialize the confirmation actor,
        // but for unit tests, we directly pass the mocks.
    });

    afterEach(async () => {
        await rd.stop();
        vi.useRealTimers();
    });

    describe('Construction and Initialization', () => {
        test('should create a confirmation actor on construction (mocked)', () => {
            // With the direct constructor call, the actorOf isn't called unless the static create method is used.
            // For this test, we assume the confirmation actor is set up.
            // We can add a test for the static create method if needed, but for now,
            // we'll remove this assertion as it won't pass with the current setup.
            // A more accurate test would be:
            const sys = { ...mockActorSystem, actorOf: vi.fn() };
            const journal = mockJournal as unknown as Journal;
            const config = { retryIntervalMs: 5000, maxRetries: 3 };
            sys.actorOf.mockReturnValue(createMockActorRef(createMockActorAddress('user/rd-confirm-temp')));
            sys.actorOf.mock.results[0].value.ask.mockResolvedValue(undefined); // Mock ask for SetReliableDeliveryRef
            ReliableDelivery.create(sys as unknown as ActorSystem, journal, config);
            expect(sys.actorOf).toHaveBeenCalledWith(
                expect.objectContaining({ actorClass: ReliableDeliveryConfirmationActor }),
                'reliable-delivery-confirmation-actor',
            );
        });

        test('start should recover state from the journal', async () => {
            // Note: The `start` method is internal now, `create` method handles recovery.
            // For current test structure, let's assume `rd.start()` is still called.
            // If ReliableDelivery.create is used, then await ReliableDelivery.create(...);
            await rd['recoverOutbox'](); // Accessing internal method for testing purposes
            expect(mockJournal.replayEvents).toHaveBeenCalledTimes(1);
        });
    });

    describe('Sending Messages', () => {
        test('send should persist an OutboundMessageSentEvent', async () => {
            const message: Message = { type: 'test' };
            await rd.send(mockActorRef, message, mockSenderRef);

            expect(mockJournal.writeEvents).toHaveBeenCalledTimes(1);
            const persistedEvent = mockJournal.writeEvents.mock.calls[0][0][0].event;
            expect(persistedEvent).toBeInstanceOf(OutboundMessageSentEvent);
            expect(persistedEvent.state.deliveryId).toBe('mock-uuid-1');
            expect(persistedEvent.state.message).toEqual(message);
            expect(persistedEvent.state.recipient.toString()).toBe(mockActorRef.address.toString());
            expect(persistedEvent.state.sender?.address.toString()).toBe(mockSenderRef.address.toString());
        });

        test('send should attempt delivery immediately', async () => {
            const message: Message = { type: 'test' };
            await rd.send(mockActorRef, message);

            expect(mockActorRef.tell).toHaveBeenCalledTimes(1);
            const sentEnvelope = mockActorRef.tell.mock.calls[0][0];
            expect(sentEnvelope).toBeInstanceOf(Object); // It's ReliableEnvelope interface, not a class
            expect(sentEnvelope.__isReliableDelivery).toBe(true);
            expect(sentEnvelope.deliveryId).toBe('mock-uuid-1');
            expect(sentEnvelope.originalMessage).toEqual(message);
            // The replyTo is implicit in the ReliableDelivery's internal logic, not a field on ReliableEnvelope.
            // We check if the tell was called with the correct sender, which is the confirmation actor itself.
            const senderArg = mockActorRef.tell.mock.calls[0][1];
            expect(senderArg).toBe(mockConfirmationActorRef);
        });
    });

    describe('Confirming Messages', () => {
        test('confirmMessage should persist a MessageConfirmedEvent for a known message', async () => {
            await rd.send(mockActorRef, { type: 'test' });
            await rd.confirmMessage('mock-uuid-1', mockActorRef.address);

            expect(mockJournal.writeEvents).toHaveBeenCalledTimes(2);
            const confirmationEvent = mockJournal.writeEvents.mock.calls[1][0][0].event;
            expect(confirmationEvent).toBeInstanceOf(MessageConfirmedEvent);
            expect(confirmationEvent.deliveryId).toBe('mock-uuid-1');
            expect(confirmationEvent.recipientAddress.toString()).toBe(mockActorRef.address.toString());
        });

        test('confirmMessage should do nothing for an unknown deliveryId', async () => {
            await rd.confirmMessage('unknown-id', mockActorRef.address);
            expect(mockJournal.writeEvents).not.toHaveBeenCalled();
        });
    });

    describe('State Recovery', () => {
        test('recover should rebuild outbox state from journal events', async () => {
            const mockTarget1Addr = createMockActorAddress('path/target1');
            const mockTarget2Addr = createMockActorAddress('path/target2');

            const events: EventEnvelope<ReliableDeliveryEvent>[] = [
                {
                    persistenceId: 'reliable-delivery-outbox',
                    sequenceNr: 1,
                    timestamp: Date.now(),
                    event: new OutboundMessageSentEvent(new OutboundMessageState('id-1', mockTarget1Addr, { type: 'msg1' }, null, Date.now())),
                },
                {
                    persistenceId: 'reliable-delivery-outbox',
                    sequenceNr: 2,
                    timestamp: Date.now(),
                    event: new OutboundMessageSentEvent(new OutboundMessageState('id-2', mockTarget2Addr, { type: 'msg2' }, null, Date.now())),
                },
                {
                    persistenceId: 'reliable-delivery-outbox',
                    sequenceNr: 3,
                    timestamp: Date.now(),
                    event: new MessageConfirmedEvent('id-1', mockTarget1Addr),
                },
            ];

            mockJournal.replayEvents.mockReturnValue(
                (async function* () {
                    for (const envelope of events) {
                        yield envelope;
                    }
                })(),
            );

            vi.useFakeTimers();
            await rd['recoverOutbox'](); // Accessing internal method for testing purposes
            rd['startRetries'](); // Manually start retries after recovery

            mockActorSystem.actorSelection
                .mockImplementationOnce((addr: ActorAddress | string) => { // Mock for 'path/target1'
                    expect(addr.toString()).toBe(mockTarget1Addr.toString());
                    return createMockActorRef(mockTarget1Addr);
                })
                .mockImplementationOnce((addr: ActorAddress | string) => { // Mock for 'path/target2'
                    expect(addr.toString()).toBe(mockTarget2Addr.toString());
                    return createMockActorRef(mockTarget2Addr);
                });

            await vi.advanceTimersByTimeAsync(5000); // Advance time to trigger retry

            // 'id-1' should be confirmed and not retried. 'id-2' should be retried.
            // actorSelection is called inside processOutbox via sendOnce.
            // The first call should be for 'id-2' as 'id-1' is confirmed.
            const unconfirmedTargetRef = mockActorSystem.actorSelection.mock.results[0].value;
            expect(unconfirmedTargetRef.tell).toHaveBeenCalledTimes(1);
            const retriedEnvelope = unconfirmedTargetRef.tell.mock.calls[0][0];
            expect(retriedEnvelope.deliveryId).toBe('id-2');
        });

        test('recover should handle an empty journal', async () => {
            mockJournal.replayEvents.mockReturnValue((async function* () {})());
            await rd['recoverOutbox'](); // Accessing internal method for testing purposes
            // No assertions needed, just testing it doesn't throw
        });
    });

    describe('Retry Mechanism', () => {
        test('should retry unconfirmed messages at specified interval', async () => {
            vi.useFakeTimers();
            const customRd = new ReliableDelivery(mockActorSystem, mockJournal as unknown as Journal, {
                retryIntervalMs: 1000,
                maxRetries: 2,
            });
            await customRd['recoverOutbox'](); // Recover state
            customRd['startRetries'](); // Start retry timer

            await customRd.send(mockActorRef, { type: 'retry-test' });
            expect(mockActorRef.tell).toHaveBeenCalledTimes(1);

            await vi.advanceTimersByTimeAsync(1000);
            expect(mockActorRef.tell).toHaveBeenCalledTimes(2); // First retry

            await vi.advanceTimersByTimeAsync(1000);
            expect(mockActorRef.tell).toHaveBeenCalledTimes(3); // Second retry

            await vi.advanceTimersByTimeAsync(1000); // Beyond max retries
            expect(mockActorRef.tell).toHaveBeenCalledTimes(3); // No more tells
            expect(mockActorSystem.log.warn).toHaveBeenCalledWith(
                `Reliable delivery failed for message mock-uuid-1 after 3 retries to ${mockActorRef.address.path}.`, // Check the exact log message
            );
            await customRd.stop();
        });

        test('should not retry a confirmed message', async () => {
            vi.useFakeTimers();
            await rd['recoverOutbox'](); // Recover state
            rd['startRetries'](); // Start retry timer

            await rd.send(mockActorRef, { type: 'confirm-test' });
            expect(mockActorRef.tell).toHaveBeenCalledTimes(1);

            await rd.confirmMessage('mock-uuid-1', mockActorRef.address);

            await vi.advanceTimersByTimeAsync(5000); // Retry interval
            expect(mockActorRef.tell).toHaveBeenCalledTimes(1); // Still only one call
        });

        test('stop should clear the retry timer', async () => {
            vi.useFakeTimers();
            await rd['recoverOutbox'](); // Recover state
            rd['startRetries'](); // Start retry timer

            await rd.send(mockActorRef, { type: 'stop-test' });
            expect(mockActorRef.tell).toHaveBeenCalledTimes(1);

            await rd.stop();

            await vi.advanceTimersByTimeAsync(5000);
            expect(mockActorRef.tell).toHaveBeenCalledTimes(1);
        });
    });

    describe('Stop', () => {
        test('should stop the confirmation actor', async () => {
            // Need to set up the RD instance using the static create method
            // to ensure `confirmationActorRef` is correctly initialized.
            vi.resetAllMocks();
            mockJournal.writeEvents.mockResolvedValue(undefined);
            mockJournal.replayEvents.mockReturnValue((async function* () {})());
            mockActorSystem.generateUniqueId.mockReturnValue('mock-uuid-1');
            mockConfirmationActorRef.ask.mockResolvedValue(undefined); // Mock ask for StopConfirmationActor

            const rdInstance = await ReliableDelivery.create(mockActorSystem, mockJournal as unknown as Journal, { retryIntervalMs: 5000, maxRetries: 3 });

            await rdInstance.stop();
            // The `stop` method for ReliableDeliveryConfirmationActor is now handled via an `ask`
            expect(mockConfirmationActorRef.ask).toHaveBeenCalledWith(expect.objectContaining({ __isSystemMessage: true }));
        });
    });
});

describe('ReliableDeliveryConfirmationActor', () => {
    test('should call reliableDelivery.confirmMessage on receiving DeliveryConfirmation', async () => {
        const mockReliableDelivery = {
            confirmMessage: vi.fn().mockResolvedValue(undefined),
        } as unknown as ReliableDelivery;

        const mockContext: any = { self: {} }; // Minimal mock context
        const actor = new ReliableDeliveryConfirmationActor(mockContext);
        actor['reliableDelivery'] = mockReliableDelivery; // Manually set the reliableDelivery instance

        const confirmation = new DeliveryConfirmation('delivery-id-abc', createMockActorAddress('user/recipient'));

        await actor['onDeliveryConfirmation'](confirmation); // Call the receive method directly

        expect(mockReliableDelivery.confirmMessage).toHaveBeenCalledWith('delivery-id-abc', confirmation.recipientAddress);
    });
});

describe('Data Structures', () => {
    test('Message and Event classes should construct correctly', () => {
        const envelope: ReliableEnvelope<any> = {
            __isReliableDelivery: true,
            deliveryId: 'd-1',
            originalMessage: { type: 'a' },
            senderAddress: mockActorRef.address,
        };
        expect(envelope.deliveryId).toBe('d-1');
        expect(envelope.originalMessage).toEqual({ type: 'a' });
        expect(envelope.senderAddress).toBe(mockActorRef.address);
        expect(envelope.__isReliableDelivery).toBe(true);

        const confirmation = new DeliveryConfirmation('d-2', mockActorRef.address);
        expect(confirmation.deliveryId).toBe('d-2');
        expect(confirmation.recipientAddress).toBe(mockActorRef.address);
        expect(confirmation.__isSystemMessage).toBe(true);

        const state = new OutboundMessageState('d-3', createMockActorAddress('path/to/target'), { type: 'b' }, mockSenderRef, Date.now());
        const sentEvent = new OutboundMessageSentEvent(state);
        expect(sentEvent.event.state.deliveryId).toBe('d-3');
        expect(sentEvent.event.state.recipient.toString()).toBe('akka://system@localhost:2552/path/to/target');
        expect(sentEvent.event.state.sender?.address.toString()).toBe(mockSenderRef.address.toString());
        expect(sentEvent.event.state.message).toEqual({ type: 'b' });

        const confirmedEvent = new MessageConfirmedEvent('d-4', createMockActorAddress('path/to/target-confirmed'));
        expect(confirmedEvent.deliveryId).toBe('d-4');
        expect(confirmedEvent.recipientAddress.toString()).toBe('akka://system@localhost:2552/path/to/target-confirmed');
    });
});
