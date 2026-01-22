import { describe, it, expect } from 'bun:test';
import { Mailbox } from '../../src/core/mailbox';
import type { Message } from '../../src/types/message.types';

type TestMessage = Message<string | number>;

const tick = () => new Promise(resolve => setImmediate(resolve));

describe('Mailbox', () => {
  it('should be created with a given capacity', () => {
    const mailbox = new Mailbox<TestMessage>(10);
    expect(mailbox).toBeInstanceOf(Mailbox);
  });

  it('should send and receive a single message', async () => {
    const mailbox = new Mailbox<TestMessage>(10);
    const message: TestMessage = { payload: 'hello' };
    await mailbox.send(message);

    const iterator = mailbox[Symbol.asyncIterator]();
    const result = await iterator.next();

    expect(result.done).toBe(false);
    expect(result.value).toEqual(message);
  });

  it('should receive messages in FIFO order', async () => {
    const mailbox = new Mailbox<TestMessage>(10);
    const messages: TestMessage[] = [{ payload: 1 }, { payload: 2 }, { payload: 3 }];

    for (const msg of messages) {
      await mailbox.send(msg);
    }

    const received: TestMessage[] = [];
    const iterator = mailbox[Symbol.asyncIterator]();
    received.push((await iterator.next()).value);
    received.push((await iterator.next()).value);
    received.push((await iterator.next()).value);

    expect(received).toEqual(messages);
  });

  it('should handle a consumer waiting for a message', async () => {
    const mailbox = new Mailbox<TestMessage>(10);
    const message: TestMessage = { payload: 'wait' };

    const iterator = mailbox[Symbol.asyncIterator]();
    const receivePromise = iterator.next();

    await tick();

    await mailbox.send(message);
    const result = await receivePromise;

    expect(result.done).toBe(false);
    expect(result.value).toEqual(message);
  });

  it('should throw an error when sending to a closed mailbox', async () => {
    const mailbox = new Mailbox<TestMessage>(10);
    const message: TestMessage = { payload: 'fail' };

    mailbox.close();

    await expect(mailbox.send(message)).rejects.toThrow('Mailbox is closed');
  });

  it('should allow consuming remaining messages after being closed', async () => {
    const mailbox = new Mailbox<TestMessage>(10);
    const messages: TestMessage[] = [{ payload: 'one' }, { payload: 'two' }];
    await mailbox.send(messages[0]);
    await mailbox.send(messages[1]);

    mailbox.close();

    const received: TestMessage[] = [];
    for await (const msg of mailbox) {
      received.push(msg);
    }

    expect(received).toEqual(messages);
  });

  it('should terminate the async iterator when closed and empty', async () => {
    const mailbox = new Mailbox<TestMessage>(10);
    mailbox.close();

    const iterator = mailbox[Symbol.asyncIterator]();
    const result = await iterator.next();

    expect(result.done).toBe(true);
    expect(result.value).toBeUndefined();
  });

  it('should terminate a pending consumer when closed', async () => {
    const mailbox = new Mailbox<TestMessage>(10);
    const iterator = mailbox[Symbol.asyncIterator]();
    const receivePromise = iterator.next();

    await tick();

    mailbox.close();
    const result = await receivePromise;

    expect(result.done).toBe(true);
    expect(result.value).toBeUndefined();
  });

  describe('backpressure', () => {
    it('should not resolve send promise when capacity is full', async () => {
      const mailbox = new Mailbox<TestMessage>(1);
      let sendResolved = false;

      await mailbox.send({ payload: 1 });

      const blockedSendPromise = mailbox.send({ payload: 2 }).then(() => {
        sendResolved = true;
      });

      await tick();
      expect(sendResolved).toBe(false);

      const iterator = mailbox[Symbol.asyncIterator]();
      await iterator.next();
      await blockedSendPromise;
      expect(sendResolved).toBe(true);
    });

    it('should resolve a pending send when a message is consumed', async () => {
      const mailbox = new Mailbox<TestMessage>(2);
      let blockedSendResolved = false;

      await mailbox.send({ payload: 'A' });
      await mailbox.send({ payload: 'B' });

      const blockedSendPromise = mailbox.send({ payload: 'C' }).then(() => {
        blockedSendResolved = true;
      });

      await tick();
      expect(blockedSendResolved).toBe(false);

      const iterator = mailbox[Symbol.asyncIterator]();
      const result1 = await iterator.next();
      expect(result1.value).toEqual({ payload: 'A' });

      await blockedSendPromise;
      expect(blockedSendResolved).toBe(true);

      const result2 = await iterator.next();
      expect(result2.value).toEqual({ payload: 'B' });
      const result3 = await iterator.next();
      expect(result3.value).toEqual({ payload: 'C' });
    });

    it('should handle multiple pending sends and consumers correctly', async () => {
        const mailbox = new Mailbox<TestMessage>(1);
        const received: (string | number)[] = [];

        const consumePromise = (async () => {
            for await (const msg of mailbox) {
                received.push(msg.payload);
                await new Promise(r => setTimeout(r, 5));
            }
        })();

        const sendPromises = [
            mailbox.send({ payload: 'A' }),
            mailbox.send({ payload: 'B' }),
            mailbox.send({ payload: 'C' }),
            mailbox.send({ payload: 'D' })
        ];

        await Promise.all(sendPromises);
        mailbox.close();
        await consumePromise;

        expect(received).toEqual(['A', 'B', 'C', 'D']);
    });

    it('should not block if capacity is Infinity', async () => {
      const mailbox = new Mailbox<TestMessage>(Infinity);
      const sendPromises: Promise<void>[] = [];
      let resolvedCount = 0;

      for (let i = 0; i < 100; i++) {
        const p = mailbox.send({ payload: i }).then(() => {
          resolvedCount++;
        });
        sendPromises.push(p);
      }

      await Promise.all(sendPromises);
      expect(resolvedCount).toBe(100);

      let consumedCount = 0;
      const iterator = mailbox[Symbol.asyncIterator]();
      for (let i = 0; i < 100; i++) {
        const result = await iterator.next();
        expect(result.done).toBe(false);
        expect(result.value?.payload).toBe(i);
        consumedCount++;
      }
      expect(consumedCount).toBe(100);
    });
  });

  it('should be usable in a standard for-await-of loop', async () => {
    const mailbox = new Mailbox<TestMessage>(5);
    const messages: TestMessage[] = [
      { payload: 10 },
      { payload: 20 },
      { payload: 30 },
    ];

    const sendAndClose = async () => {
      for (const msg of messages) {
        await mailbox.send(msg);
      }
      mailbox.close();
    };

    const sendPromise = sendAndClose();

    const received: TestMessage[] = [];
    for await (const msg of mailbox) {
      received.push(msg);
    }

    await sendPromise;
    expect(received).toEqual(messages);
  });
});
