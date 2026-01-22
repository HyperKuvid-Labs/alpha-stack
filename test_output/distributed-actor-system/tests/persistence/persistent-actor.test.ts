import { describe, test, expect, jest, beforeEach, afterEach } from 'bun:test';
import { ActorSystem } from '../../src/core/actor-system';
import { Actor, ActorContext } from '../../src/core/actor';
import { Receive } from '../../src/core/decorators';
import { PersistentActor } from '../../src/persistence/persistent-actor';
import { Journal, EventEnvelope } from '../../src/persistence/journal';
import { ActorRef } from '../../src/core/actor-ref';

type CounterState = {
    count: number;
};

type CounterEvent = { type: 'incremented' } | { type: 'decremented' };

class Increment {}
class Decrement {}
class GetState {
    constructor(public readonly replyTo: ActorRef<CounterState>) {}
}

class MockJournal extends Journal {
    private storage: Map<string, EventEnvelope<any>[]> = new Map();
    public writeSpy = jest.fn(this._write.bind(this));
    public replaySpy = jest.fn(this._replay.bind(this));

    private async _write(
        persistenceId: string,
        sequenceNr: number,
        payload: any
    ): Promise<void> {
        if (!this.storage.has(persistenceId)) {
            this.storage.set(persistenceId, []);
        }
        const events = this.storage.get(persistenceId)!;
        if (events.some((e) => e.sequenceNr === sequenceNr)) {
            throw new Error(`Duplicate sequenceNr: ${sequenceNr}`);
        }
        events.push({ persistenceId, sequenceNr, payload, timestamp: Date.now() });
        events.sort((a, b) => a.sequenceNr - b.sequenceNr);
    }

    private async *_replay(
        persistenceId: string,
        fromSequenceNr: number
    ): AsyncIterable<any> {
        const events = this.storage.get(persistenceId) ?? [];
        for (const event of events) {
            if (event.sequenceNr >= fromSequenceNr) {
                yield event.payload;
            }
        }
    }

    async writeEvents(events: EventEnvelope<any>[]): Promise<void> {
        for (const event of events) {
            await this.writeSpy(event.persistenceId, event.sequenceNr, event.payload);
        }
    }

    async *replayEvents(persistenceId: string, fromSequenceNr: number): AsyncIterable<EventEnvelope<any>> {
        const events = this.storage.get(persistenceId) ?? [];
        for (const event of events) {
            if (event.sequenceNr >= fromSequenceNr) {
                yield event; // Yield the full EventEnvelope
            }
        }
    }

    preload(persistenceId: string, events: EventEnvelope<any>[]) {
        this.storage.set(persistenceId, events);
    }
}

class CounterActor extends PersistentActor<CounterState, CounterEvent> {
    constructor(context: ActorContext, persistenceId: string) {
        super(context, persistenceId);
        this.state = { count: 0 };
    }

    receiveRecover(event: CounterEvent, sequenceNr: number): void {
        switch (event.type) {
            case 'incremented':
                this.state.count++;
                break;
            case 'decremented':
                this.state.count--;
                break;
        }
    }

    @Receive(Increment)
    async handleIncrement(_msg: Increment) {
        await this.persist({ type: 'incremented' });
    }

    @Receive(Decrement)
    async handleDecrement(_msg: Decrement) {
        await this.persist({ type: 'decremented' });
    }

    @Receive(GetState)
    handleGetState(msg: GetState) {
        msg.replyTo.tell(this.state);
    }
}

class TestProbe extends Actor<any> {
    private resolve: ((value: any) => void) | null = null;
    private promise: Promise<any> | null = null;

    constructor(context: ActorContext) {
        super(context);
        this.reset();
    }

    reset() {
        this.promise = new Promise((resolve) => {
            this.resolve = resolve;
        });
    }

    @Receive(Object)
    handle(message: any) {
        if(this.resolve) {
            this.resolve(message);
        }
        this.reset();
    }

    async expectMessage(timeout = 1000): Promise<any> {
       return Promise.race([
            this.promise,
            new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout waiting for message')), timeout))
        ]);
    }
}


describe('PersistentActor', () => {
    let system: ActorSystem;
    let mockJournal: MockJournal;
    let testProbe: ActorRef<any>;

    beforeEach(() => {
        mockJournal = new MockJournal();
        system = new ActorSystem();
        system.journalFactory = () => mockJournal;
        testProbe = system.actorOf(TestProbe, 'probe');
    });

    afterEach(async () => {
        await system.shutdown();
    });

    describe('Recovery', () => {
        test('should recover state from journal on start', async () => {
            const persistenceId = 'actor-1';
            mockJournal.preload(persistenceId, [
                { persistenceId, sequenceNr: 1, payload: { type: 'incremented' }, timestamp: 0 },
                { persistenceId, sequenceNr: 2, payload: { type: 'incremented' }, timestamp: 0 },
                { persistenceId, sequenceNr: 3, payload: { type: 'decremented' }, timestamp: 0 },
            ]);

            const actor = system.actorOf(CounterActor, 'counter', persistenceId);
            await new Promise(resolve => setTimeout(resolve, 50));

            actor.tell(new GetState(testProbe));
            const state = await testProbe.expectMessage();
            
            expect(state.count).toBe(1);
            expect(mockJournal.replaySpy).toHaveBeenCalledWith(persistenceId, 1);
        });

        test('should start with initial state if journal is empty', async () => {
            const persistenceId = 'actor-2';
            const actor = system.actorOf(CounterActor, 'counter', persistenceId);
            await new Promise(resolve => setTimeout(resolve, 50));

            actor.tell(new GetState(testProbe));
            const state = await testProbe.expectMessage();
            
            expect(state.count).toBe(0);
            expect(mockJournal.replaySpy).toHaveBeenCalledWith(persistenceId, 1);
        });

        test('should have correct lastSequenceNr after recovery', async () => {
             const persistenceId = 'actor-3';
             mockJournal.preload(persistenceId, [
                { persistenceId, sequenceNr: 1, payload: { type: 'incremented' }, timestamp: 0 },
                { persistenceId, sequenceNr: 2, payload: { type: 'incremented' }, timestamp: 0 },
            ]);
            
            let recoveredSeqNr = -1;
            class SeqNrInspector extends CounterActor {
                 async preStart() {
                    await super.preStart();
                    recoveredSeqNr = this.lastSequenceNr;
                }
            }
            
            system.actorOf(SeqNrInspector, 'inspector', persistenceId);
            await new Promise(resolve => setTimeout(resolve, 50));
            
            expect(recoveredSeqNr).toBe(2);
        });

        test('should handle journal replay errors during startup', async () => {
            const persistenceId = 'actor-4';
            const error = new Error("Journal is down");
            mockJournal.replaySpy.mockImplementationOnce(async function*() {
                yield { type: 'incremented' };
                throw error;
            });

            const actor = system.actorOf(CounterActor, 'counter', persistenceId);
            await new Promise(resolve => setTimeout(resolve, 50));
            actor.tell(new GetState(testProbe));
            const state = await testProbe.expectMessage();

            expect(state.count).toBe(1);
        });
    });

    describe('Persistence', () => {
        test('should persist an event and update state', async () => {
            const persistenceId = 'actor-5';
            const actor = system.actorOf(CounterActor, 'counter', persistenceId);

            actor.tell(new Increment());
            await new Promise(resolve => setTimeout(resolve, 50));
            
            actor.tell(new GetState(testProbe));
            const state = await testProbe.expectMessage();

            expect(state.count).toBe(1);
            expect(mockJournal.writeSpy).toHaveBeenCalledWith(persistenceId, 1, { type: 'incremented' });
        });

        test('should increment sequence number on each persist', async () => {
            const persistenceId = 'actor-6';
            const actor = system.actorOf(CounterActor, 'counter', persistenceId);
            
            actor.tell(new Increment());
            actor.tell(new Increment());
            actor.tell(new Decrement());

            await new Promise(resolve => setTimeout(resolve, 100));

            actor.tell(new GetState(testProbe));
            const state = await testProbe.expectMessage();

            expect(state.count).toBe(1);
            expect(mockJournal.writeSpy).toHaveBeenCalledTimes(3);
            expect(mockJournal.writeSpy).toHaveBeenCalledWith(persistenceId, 1, { type: 'incremented' });
            expect(mockJournal.writeSpy).toHaveBeenCalledWith(persistenceId, 2, { type: 'incremented' });
            expect(mockJournal.writeSpy).toHaveBeenCalledWith(persistenceId, 3, { type: 'decremented' });
        });

        test('should not update state if persistence fails', async () => {
            const persistenceId = 'actor-7';
            const writeError = new Error("Disk full");
            mockJournal.writeSpy.mockRejectedValueOnce(writeError);

            const actor = system.actorOf(CounterActor, 'counter', persistenceId);
            actor.tell(new Increment());
            
            await new Promise(resolve => setTimeout(resolve, 50));
            
            actor.tell(new GetState(testProbe));
            const state = await testProbe.expectMessage();

            expect(state.count).toBe(0);
        });

        test('should handle multiple persist calls sequentially', async () => {
            const persistenceId = 'actor-8';
            const actor = system.actorOf(CounterActor, 'counter', persistenceId);
            
            actor.tell(new Increment());
            actor.tell(new Increment());
            actor.tell(new Increment());

            await new Promise(resolve => setTimeout(resolve, 100));

            const calls = mockJournal.writeSpy.mock.calls;
            expect(calls.length).toBe(3);
            expect(calls[0][1]).toBe(1);
            expect(calls[1][1]).toBe(2);
            expect(calls[2][1]).toBe(3);

            actor.tell(new GetState(testProbe));
            const state = await testProbe.expectMessage();
            expect(state.count).toBe(3);
        });
    });

    describe('Lifecycle and Interaction', () => {
        test('should process messages after recovery is complete', async () => {
            const persistenceId = 'actor-9';
            mockJournal.preload(persistenceId, [
                { persistenceId, sequenceNr: 1, payload: { type: 'incremented' }, timestamp: 0 },
                { persistenceId, sequenceNr: 2, payload: { type: 'incremented' }, timestamp: 0 },
            ]);

            const actor = system.actorOf(CounterActor, 'counter', persistenceId);
            actor.tell(new Decrement());

            await new Promise(resolve => setTimeout(resolve, 100));

            actor.tell(new GetState(testProbe));
            const state = await testProbe.expectMessage();

            expect(state.count).toBe(1);
            expect(mockJournal.writeSpy).toHaveBeenCalledWith(persistenceId, 3, { type: 'decremented' });
        });

        test('a restarted actor should recover its state and continue', async () => {
            const persistenceId = 'actor-10';
            const actor = system.actorOf(CounterActor, 'counter', persistenceId);

            actor.tell(new Increment());
            actor.tell(new Increment());
            await new Promise(resolve => setTimeout(resolve, 50));

            system.stop(actor);
            await new Promise(resolve => setTimeout(resolve, 50));

            const restartedActor = system.actorOf(CounterActor, 'counter', persistenceId);
            await new Promise(resolve => setTimeout(resolve, 50));

            restartedActor.tell(new GetState(testProbe));
            const state1 = await testProbe.expectMessage();
            expect(state1.count).toBe(2);

            restartedActor.tell(new Decrement());
            await new Promise(resolve => setTimeout(resolve, 50));

            restartedActor.tell(new GetState(testProbe));
            const state2 = await testProbe.expectMessage();
            expect(state2.count).toBe(1);
            expect(mockJournal.writeSpy).toHaveBeenCalledWith(persistenceId, 3, { type: 'decremented' });
        });
    });
});
