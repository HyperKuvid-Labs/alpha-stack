export class Mailbox<T> implements AsyncIterableIterator<T> {
  private queue: T[] = [];
  private resolvers: Array<(value: IteratorResult<T, undefined>) => void> = [];
  private isClosed: boolean = false;

  enqueue(message: T): void {
    if (this.isClosed) {
      return;
    }

    if (this.resolvers.length > 0) {
      const resolve = this.resolvers.shift();
      resolve!({ value: message, done: false });
    } else {
      this.queue.push(message);
    }
  }

  close(): void {
    this.isClosed = true;
    while (this.resolvers.length > 0) {
      const resolve = this.resolvers.shift();
      resolve!({ value: undefined, done: true });
    }
  }

  async next(): Promise<IteratorResult<T, undefined>> {
    if (this.queue.length > 0) {
      return { value: this.queue.shift()!, done: false };
    }

    if (this.isClosed) {
      return { value: undefined, done: true };
    }

    return new Promise<IteratorResult<T, undefined>>((resolve) => {
      this.resolvers.push(resolve);
    });
  }

  [Symbol.asyncIterator](): AsyncIterableIterator<T> {
    return this;
  }
}
