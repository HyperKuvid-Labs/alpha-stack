import { describe, it, expect, test } from 'bun:test';
import { Mailbox } from './mailbox';

describe('Mailbox<T>', () => {
    it('should be created in an empty state', async () => {
        const mailbox = new Mailbox<number>();
        const promise = mailbox.next();
        const winner = await Promise.race([
            promise,
            new Promise(resolve => setTimeout(() => resolve('timeout'), 10)),
        ]);
        expect(winner).toBe('timeout');
    });

    it('should enqueue and dequeue a single message', async () => {
        const mailbox = new Mailbox<string>();
        mailbox.enqueue('hello');
        const result = await mailbox.next();
        expect(result).toEqual({ done: false, value: 'hello' });
    });

    it('should process messages in FIFO order', async () => {
        const mailbox = new Mailbox<number>();
        mailbox.enqueue(1);
        mailbox.enqueue(2);
        mailbox.enqueue(3);

        expect(await mailbox.next()).toEqual({ done: false, value: 1 });
        expect(await mailbox.next()).toEqual({ done: false, value: 2 });
        expect(await mailbox.next()).toEqual({ done: false, value: 3 });
    });

    it('should resolve a pending next() call when a message is enqueued', async () => {
        const mailbox = new Mailbox<boolean>();
        const pendingNext = mailbox.next();
        mailbox.enqueue(true);
        const result = await pendingNext;
        expect(result).toEqual({ done: false, value: true });
    });

    it('should handle multiple pending next() calls', async () => {
        const mailbox = new Mailbox<string>();
        const promise1 = mailbox.next();
        const promise2 = mailbox.next();

        mailbox.enqueue('first');
        mailbox.enqueue('second');

        const result1 = await promise1;
        const result2 = await promise2;

        expect(result1).toEqual({ done: false, value: 'first' });
        expect(result2).toEqual({ done: false, value: 'second' });
    });

    describe('close()', () => {
        it('should immediately mark an empty mailbox as done when closed', async () => {
            const mailbox = new Mailbox<any>();
            mailbox.close();
            const result = await mailbox.next();
            expect(result).toEqual({ done: true, value: undefined });
        });

        it('should allow consuming remaining messages before marking as done', async () => {
            const mailbox = new Mailbox<number>();
            mailbox.enqueue(100);
            mailbox.enqueue(200);
            mailbox.close();

            expect(await mailbox.next()).toEqual({ done: false, value: 100 });
            expect(await mailbox.next()).toEqual({ done: false, value: 200 });
            expect(await mailbox.next()).toEqual({ done: true, value: undefined });
        });

        it('should resolve a pending next() call with done: true when closed', async () => {
            const mailbox = new Mailbox<string>();
            const pendingNext = mailbox.next();
            mailbox.close();
            const result = await pendingNext;
            expect(result).toEqual({ done: true, value: undefined });
        });

        it('should ignore messages enqueued after closing', async () => {
            const mailbox = new Mailbox<number>();
            mailbox.enqueue(1);
            mailbox.close();
            mailbox.enqueue(2); // This should be ignored

            expect(await mailbox.next()).toEqual({ done: false, value: 1 });
            expect(await mailbox.next()).toEqual({ done: true, value: undefined });
        });

        test('calling close() multiple times should be idempotent', async () => {
            const mailbox = new Mailbox<any>();
            mailbox.close();
            mailbox.close(); // Second call
            const result = await mailbox.next();
            expect(result).toEqual({ done: true, value: undefined });
        });
    });

    describe('Async Iterator Protocol', () => {
        it('should work correctly with a for-await-of loop', async () => {
            const mailbox = new Mailbox<number>();
            const received: number[] = [];

            const consumer = (async () => {
                for await (const msg of mailbox) {
                    received.push(msg);
                }
            })();

            mailbox.enqueue(1);
            mailbox.enqueue(2);

            await new Promise(resolve => setTimeout(resolve, 0));

            mailbox.enqueue(3);
            mailbox.close();

            await consumer;

            expect(received).toEqual([1, 2, 3]);
        });

        it('should terminate an empty for-await-of loop when closed', async () => {
            const mailbox = new Mailbox<number>();
            const received: number[] = [];
            let loopFinished = false;

            const consumer = (async () => {
                for await (const msg of mailbox) {
                    received.push(msg);
                }
                loopFinished = true;
            })();

            mailbox.close();
            await consumer;

            expect(received).toEqual([]);
            expect(loopFinished).toBe(true);
        });
    });

    describe('Edge Cases', () => {
        it('should handle enqueueing null and undefined values', async () => {
            const mailbox = new Mailbox<string | null | undefined>();
            mailbox.enqueue(null);
            mailbox.enqueue(undefined);
            mailbox.enqueue('a value');

            expect(await mailbox.next()).toEqual({ done: false, value: null });
            expect(await mailbox.next()).toEqual({ done: false, value: undefined });
            expect(await mailbox.next()).toEqual({ done: false, value: 'a value' });
        });

        it('should consistently return done: true after the iterator is finished', async () => {
            const mailbox = new Mailbox<number>();
            mailbox.enqueue(1);
            mailbox.close();

            expect(await mailbox.next()).toEqual({ done: false, value: 1 });
            expect(await mailbox.next()).toEqual({ done: true, value: undefined });
            expect(await mailbox.next()).toEqual({ done: true, value: undefined });
        });
    });
});
