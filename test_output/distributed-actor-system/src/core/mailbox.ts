export class Mailbox<T> implements AsyncIterable<T> {
  private queue: T[] = [];
  private capacity: number;
  private isClosed: boolean = false;

  private pendingReads: ((value: IteratorResult<T>) => void)[] = [];
  private pendingWrites: (() => void)[] = [];

  constructor(capacity: number = Infinity) {
    if (capacity < 1) {
      throw new Error("Mailbox capacity must be at least 1.");
    }
    this.capacity = capacity;
  }

  async send(message: T): Promise<void> {
    if (this.isClosed) {
      throw new Error("Cannot send message to a closed mailbox.");
    }

    if (this.queue.length >= this.capacity) {
      await new Promise<void>(resolve => this.pendingWrites.push(resolve));
      if (this.isClosed) {
        throw new Error("Mailbox closed while waiting to send message.");
      }
    }

    this.queue.push(message);

    if (this.pendingReads.length > 0) {
      const resolveRead = this.pendingReads.shift()!;
      resolveRead({ value: this.queue.shift()!, done: false });
    }
  }

  close(): void {
    if (this.isClosed) {
      return;
    }
    this.isClosed = true;

    while (this.pendingReads.length > 0) {
      const resolveRead = this.pendingReads.shift()!;
      resolveRead({ value: undefined, done: true });
    }
  }

  async *[Symbol.asyncIterator](): AsyncGenerator<T, void, unknown> {
    while (true) {
      if (this.queue.length > 0) {
        const message = this.queue.shift()!;
        if (this.pendingWrites.length > 0) {
          const resolveWrite = this.pendingWrites.shift()!;
          resolveWrite();
        }
        yield message;
      } else if (this.isClosed) {
        break;
      } else {
        const result = await new Promise<IteratorResult<T>>(resolve => {
          this.pendingReads.push(resolve);
        });

        if (result.done) {
          break;
        } else {
          if (this.pendingWrites.length > 0) {
            const resolveWrite = this.pendingWrites.shift()!;
            resolveWrite();
          }
          yield result.value;
        }
      }
    }
  }
}
