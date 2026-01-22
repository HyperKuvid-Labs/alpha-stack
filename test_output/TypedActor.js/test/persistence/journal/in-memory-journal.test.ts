import { describe, it, expect, beforeEach } from 'bun:test';
import { InMemoryJournal } from './in-memory-journal';
import type { JournalPlugin } from './journal-plugin';

async function collectAsyncIterable<T>(iterable: AsyncIterable<T>): Promise<T[]> {
	const results: T[] = [];
	for await (const value of iterable) {
		results.push(value);
	}
	return results;
}

describe('InMemoryJournal', () => {
	let journal: JournalPlugin;

	beforeEach(() => {
		journal = new InMemoryJournal();
	});

	describe('writeEvents', () => {
		it('should write events for a new persistenceId', async () => {
			const persistenceId = 'pid-1';
			const events = [{ type: 'A' }, { type: 'B' }];
			await journal.writeEvents(persistenceId, events);
			const highestSeqNr = await journal.readHighestSequenceNr(persistenceId);
			expect(highestSeqNr).toBe(2);
		});

		it('should append events to an existing persistenceId', async () => {
			const persistenceId = 'pid-2';
			await journal.writeEvents(persistenceId, [{ type: 'A' }]);
			expect(await journal.readHighestSequenceNr(persistenceId)).toBe(1);

			await journal.writeEvents(persistenceId, [{ type: 'B' }, { type: 'C' }]);
			expect(await journal.readHighestSequenceNr(persistenceId)).toBe(3);
		});

		it('should not change the sequence number when writing an empty array of events', async () => {
			const persistenceId = 'pid-3';
			await journal.writeEvents(persistenceId, [{ type: 'A' }]);
			expect(await journal.readHighestSequenceNr(persistenceId)).toBe(1);

			await journal.writeEvents(persistenceId, []);
			expect(await journal.readHighestSequenceNr(persistenceId)).toBe(1);
		});
	});

	describe('readHighestSequenceNr', () => {
		it('should return 0 for a non-existent persistenceId', async () => {
			const highestSeqNr = await journal.readHighestSequenceNr('non-existent-pid');
			expect(highestSeqNr).toBe(0);
		});

		it('should return the correct number of events for an existing persistenceId', async () => {
			const persistenceId = 'pid-4';
			const events = ['e1', 'e2', 'e3'];
			await journal.writeEvents(persistenceId, events);
			const highestSeqNr = await journal.readHighestSequenceNr(persistenceId);
			expect(highestSeqNr).toBe(3);
		});

		it('should reflect the updated count after more events are written', async () => {
			const persistenceId = 'pid-5';
			await journal.writeEvents(persistenceId, ['e1', 'e2']);
			expect(await journal.readHighestSequenceNr(persistenceId)).toBe(2);
			await journal.writeEvents(persistenceId, ['e3', 'e4', 'e5']);
			expect(await journal.readHighestSequenceNr(persistenceId)).toBe(5);
		});
	});

	describe('replayEvents', () => {
		const persistenceId = 'pid-6';
		const events = ['event-1', 'event-2', 'event-3', 'event-4', 'event-5'];

		beforeEach(async () => {
			await journal.writeEvents(persistenceId, events);
		});

		it('should replay all events when fromSequenceNr is 1 and toSequenceNr is high', async () => {
			const replayed = await collectAsyncIterable(
				journal.replayEvents(persistenceId, 1, Number.MAX_SAFE_INTEGER),
			);
			expect(replayed).toEqual(events);
		});

		it('should replay events from a specific starting sequence number', async () => {
			const replayed = await collectAsyncIterable(
				journal.replayEvents(persistenceId, 3, Number.MAX_SAFE_INTEGER),
			);
			expect(replayed).toEqual(['event-3', 'event-4', 'event-5']);
		});

		it('should replay a bounded subset of events', async () => {
			const replayed = await collectAsyncIterable(journal.replayEvents(persistenceId, 2, 4));
			expect(replayed).toEqual(['event-2', 'event-3', 'event-4']);
		});

		it('should replay a single event', async () => {
			const replayed = await collectAsyncIterable(journal.replayEvents(persistenceId, 3, 3));
			expect(replayed).toEqual(['event-3']);
		});

		it('should yield no events for a non-existent persistenceId', async () => {
			const replayed = await collectAsyncIterable(
				journal.replayEvents('non-existent-pid', 1, 100),
			);
			expect(replayed).toEqual([]);
		});

		it('should yield no events if fromSequenceNr is greater than the highest sequence number', async () => {
			const replayed = await collectAsyncIterable(
				journal.replayEvents(persistenceId, 6, 100),
			);
			expect(replayed).toEqual([]);
		});

		it('should replay up to the last event if toSequenceNr is greater than the highest sequence number', async () => {
			const replayed = await collectAsyncIterable(journal.replayEvents(persistenceId, 4, 100));
			expect(replayed).toEqual(['event-4', 'event-5']);
		});

		it('should yield no events if fromSequenceNr is greater than toSequenceNr', async () => {
			const replayed = await collectAsyncIterable(journal.replayEvents(persistenceId, 4, 2));
			expect(replayed).toEqual([]);
		});
	});

	describe('isolation', () => {
		it('should keep events for different persistenceIds separate', async () => {
			const pid1 = 'iso-pid-1';
			const pid2 = 'iso-pid-2';
			const events1 = [{ id: 1 }, { id: 2 }];
			const events2 = [{ name: 'A' }, { name: 'B' }, { name: 'C' }];

			await journal.writeEvents(pid1, events1);
			await journal.writeEvents(pid2, events2);

			expect(await journal.readHighestSequenceNr(pid1)).toBe(2);
			expect(await journal.readHighestSequenceNr(pid2)).toBe(3);

			const replayed1 = await collectAsyncIterable(
				journal.replayEvents(pid1, 1, Number.MAX_SAFE_INTEGER),
			);
			const replayed2 = await collectAsyncIterable(
				journal.replayEvents(pid2, 1, Number.MAX_SAFE_INTEGER),
			);

			expect(replayed1).toEqual(events1);
			expect(replayed2).toEqual(events2);

			await journal.writeEvents(pid1, [{ id: 3 }]);
			expect(await journal.readHighestSequenceNr(pid1)).toBe(3);
			expect(await journal.readHighestSequenceNr(pid2)).toBe(3);

			const replayed1AfterWrite = await collectAsyncIterable(
				journal.replayEvents(pid1, 1, Number.MAX_SAFE_INTEGER),
			);
			expect(replayed1AfterWrite).toEqual([...events1, { id: 3 }]);
		});
	});
});
