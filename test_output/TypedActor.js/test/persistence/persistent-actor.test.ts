import { describe, it, expect, beforeEach, afterEach, mock } from 'bun:test';
import { PersistentActor } from '../../src/persistence/persistent-actor';
import { ActorSystem } from '../../src/core/actor-system';
import type { JournalPlugin } from '../../src/persistence/journal/journal-plugin';
import type { ActorContext } from '../../src/core/actor-context';
import type { ActorRef } from '../../src/core/actor-ref';
import { SystemMessage, UserMessage } from '../../src/types/messages';

// --- Test Setup ---

type CounterState = {
    value: number;
    history: string[];
};

type CounterEvent =
    | { type: 'incremented' }
    | { type: 'added'; amount: number }
    | { type: 'reset' }
    | { type: 'logged'; message: string };

type CounterCommand =
    | { command: 'increment' }
    | { command: 'add'; amount: number }
    | { command: 'reset' }
    | { command: 'log'; message: string };

type CounterQuery = { query: 'get_value' } | { query: 'get_history' };

class TestCounterActor extends PersistentActor<CounterEvent, CounterState> {
    public persistenceId: string;
    protected state: CounterState = { value: 0, history: [] };

    constructor(context: ActorContext, persistenceId: string) {
        super(context);
        this.persistenceId = persistenceId;
    }

    receiveRecover(event: CounterEvent): void {
        switch (event.type) {
            case 'incremented':
                this.state.value += 1;
                break;
            case 'added':
                this.state.value += event.amount;
                break;
            case 'reset':
                this.state = { value: 0, history: [] };
                break;
            case 'logged':
                this.state.history.push(event.message);
                break;
        }
    }

    async receiveMessage(
        message: CounterCommand | CounterQuery | SystemMessage,
        sender: ActorRef<any> | undefined
    ): Promise<void> {
        if (typeof message !== 'object' || message === null) return;
        
        if ('command' in message) {
            switch (message.command) {
                case 'increment':
                    await this.persist({ type: 'incremented' });
                    sender?.tell(this.state);
                    break;
                case 'add':
                    await this.persist({ type: 'added', amount: message.amount });
                    sender?.tell(this.state);
                    break;
                case 'reset':
                    await this.persist({ type: 'reset' });
                    sender?.tell(this.state);
                    break;
                case 'log':
                    // This command does not update the value, only history
                    await this.persist({ type: 'logged', message: message.message });
                    sender?.tell(this.state);
                    break;
            }
        } else if ('query' in message) {
            switch (message.query) {
                case 'get_value':
                    sender?.tell(this.state.value);
                    break;
                case 'get_history':
                    sender?.tell(this.state.history);
                    break;
            }
        }
    }
}

class InMemoryJournal implements JournalPlugin {
    private storage = new Map<string, { event: any; sequenceNr: number }[]>();

    async writeEvents(persistenceId: string, events: any[]): Promise<void> {
        if (!this.storage.has(persistenceId)) {
            this.storage.set(persistenceId, []);
        }
        const journal = this.storage.get(persistenceId)!;
        let lastSeqNr = journal.length > 0 ? journal[journal.length - 1].sequenceNr : 0;
        for (const event of events) {
            journal.push({ event, sequenceNr: ++lastSeqNr });
        }
    }

    async *readEvents(
        persistenceId: string,
        fromSequenceNr: number,
        toSequenceNr: number
    ): AsyncGenerator<any, void, unknown> {
        const journal = this.storage.get(persistenceId) || [];
        for (const entry of journal) {
            if (entry.sequenceNr >= fromSequenceNr && entry.sequenceNr <= toSequenceNr) {
                yield entry.event;
            }
        }
    }

    async readHighestSequenceNr(persistenceId: string): Promise<number> {
        const journal = this.storage.get(persistenceId) || [];
        return journal.length > 0 ? journal[journal.length - 1].sequenceNr : 0;
    }
}

// --- Tests ---

describe('PersistentActor', () => {
    let system: ActorSystem;
    let journal: InMemoryJournal;

    beforeEach(() => {
        journal = new InMemoryJournal();
        system = new ActorSystem('TestSystem', { journalPlugin: journal });
    });

    afterEach(async () => {
        await system.shutdown();
    });

    it('should recover its state from the journal on start', async () => {
        const persistenceId = 'actor-1';
        await journal.writeEvents(persistenceId, [
            { type: 'added', amount: 5 },
            { type: 'incremented' },
            { type: 'incremented' },
        ]);

        const actor = await system.actorOf(TestCounterActor, [persistenceId]);
        const finalValue = await actor.ask({ query: 'get_value' });

        expect(finalValue).toBe(7);
    });

    it('should start with initial state if the journal is empty for its persistenceId', async () => {
        const persistenceId = 'actor-2';
        const actor = await system.actorOf(TestCounterActor, [persistenceId]);
        const initialValue = await actor.ask({ query: 'get_value' });
        expect(initialValue).toBe(0);
    });

    it('should persist events and update its state accordingly', async () => {
        const persistenceId = 'actor-3';
        const actor = await system.actorOf(TestCounterActor, [persistenceId]);

        await actor.ask({ command: 'add', amount: 10 });
        const valueAfterAdd = await actor.ask({ query: 'get_value' });
        expect(valueAfterAdd).toBe(10);

        await actor.ask({ command: 'increment' });
        const valueAfterIncrement = await actor.ask({ query: 'get_value' });
        expect(valueAfterIncrement).toBe(11);

        const highestSeqNr = await journal.readHighestSequenceNr(persistenceId);
        expect(highestSeqNr).toBe(2);
    });

    it('should correctly recover and then continue persisting new events', async () => {
        const persistenceId = 'actor-4';
        await journal.writeEvents(persistenceId, [{ type: 'added', amount: 100 }]);

        const actor = await system.actorOf(TestCounterActor, [persistenceId]);
        const recoveredValue = await actor.ask({ query: 'get_value' });
        expect(recoveredValue).toBe(100);

        await actor.ask({ command: 'add', amount: 20 });
        const newValue = await actor.ask({ query: 'get_value' });
        expect(newValue).toBe(120);

        const events: any[] = [];
        for await (const event of journal.readEvents(persistenceId, 1, 100)) {
            events.push(event);
        }
        expect(events).toEqual([{ type: 'added', amount: 100 }, { type: 'added', amount: 20 }]);
    });
    
    it('should handle non-state-changing events correctly', async () => {
        const persistenceId = 'actor-5';
        const actor = await system.actorOf(TestCounterActor, [persistenceId]);

        await actor.ask({ command: 'log', message: 'first message' });
        await actor.ask({ command: 'add', amount: 5 });
        await actor.ask({ command: 'log', message: 'second message' });

        const history = await actor.ask({ query: 'get_history' });
        const value = await actor.ask({ query: 'get_value' });

        expect(value).toBe(5);
        expect(history).toEqual(['first message', 'second message']);
    });

    it('should stop itself if recovery from journal fails', async () => {
        const persistenceId = 'actor-6';
        await journal.writeEvents(persistenceId, [{ type: 'added', amount: 10 }]);

        const failingJournal = new InMemoryJournal();
        failingJournal.readEvents = async function*() {
            throw new Error('Journal read failure');
        };

        const failingSystem = new ActorSystem('FailingSystem', { journalPlugin: failingJournal });
        
        await expect(failingSystem.actorOf(TestCounterActor, [persistenceId])).toThrow('Failed to start actor');

        await failingSystem.shutdown();
    });

    it('should not update state if persistence fails', async () => {
        const persistenceId = 'actor-7';
        
        const failingJournal = new InMemoryJournal();
        failingJournal.writeEvents = mock(async () => {
            throw new Error('Journal write failure');
        });
        
        const failingSystem = new ActorSystem('FailingSystem', { journalPlugin: failingJournal });
        const actor = await failingSystem.actorOf(TestCounterActor, [persistenceId]);

        const initialValue = await actor.ask({ query: 'get_value' });
        expect(initialValue).toBe(0);

        await expect(actor.ask({ command: 'add', amount: 10 })).rejects.toThrow('Journal write failure');

        const valueAfterFailure = await actor.ask({ query: 'get_value' });
        expect(valueAfterFailure).toBe(0);
        
        await failingSystem.shutdown();
    });

    it('should handle queries without persisting any events', async () => {
        const persistenceId = 'actor-8';
        const actor = await system.actorOf(TestCounterActor, [persistenceId]);
        
        const writeSpy = mock.spyOn(journal, 'writeEvents');

        await actor.ask({ command: 'add', amount: 25 });
        expect(writeSpy).toHaveBeenCalledTimes(1);
        
        const value = await actor.ask({ query: 'get_value' });
        expect(value).toBe(25);
        expect(writeSpy).toHaveBeenCalledTimes(1);

        const history = await actor.ask({ query: 'get_history' });
        expect(history).toEqual([]);
        expect(writeSpy).toHaveBeenCalledTimes(1);
    });

    it('should be able to reset its state by persisting a reset event', async () => {
        const persistenceId = 'actor-9';
        await journal.writeEvents(persistenceId, [
            { type: 'added', amount: 50 },
            { type: 'incremented' },
        ]);

        const actor = await system.actorOf(TestCounterActor, [persistenceId]);
        
        const recoveredValue = await actor.ask({ query: 'get_value' });
        expect(recoveredValue).toBe(51);

        await actor.ask({ command: 'reset' });

        const valueAfterReset = await actor.ask({ query: 'get_value' });
        expect(valueAfterReset).toBe(0);

        // Verify that a new actor with the same ID recovers to the reset state
        await system.stop(actor);
        const newActorInstance = await system.actorOf(TestCounterActor, [persistenceId]);
        const finalValue = await newActorInstance.ask({ query: 'get_value' });
        expect(finalValue).toBe(0);
    });
});
