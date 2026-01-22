import type { ActorSystem } from './actor-system';
import { v4 as uuidv4 } from 'uuid';

export type ActorPath = string;

export class AskEnvelope {
  constructor(
    public readonly message: unknown,
    public readonly senderRef: ActorRef<any>,
    public readonly correlationId: string,
    public readonly timeout: number | undefined,
  ) {}
}

export class AskReplyEnvelope {
  constructor(
    public readonly reply: unknown,
    public readonly correlationId: string,
  ) {}
}

export class AskTimeoutError extends Error {
  constructor(correlationId: string, timeout: number) {
    super(`Ask timed out for correlation ID ${correlationId} after ${timeout}ms.`);
    this.name = 'AskTimeoutError';
  }
}

export abstract class ActorRef<T> {
  public readonly path: ActorPath;
  protected readonly system: ActorSystem;

  constructor(path: ActorPath, system: ActorSystem) {
    this.path = path;
    this.system = system;
  }

  public abstract tell(message: T): void;

  public abstract _sendSystemMessage(message: AskEnvelope | AskReplyEnvelope): void;

  public ask<TReply>(message: unknown, timeout?: number): Promise<TReply> {
    const correlationId = uuidv4();

    return new Promise<TReply>((resolve, reject) => {
      this.system._registerAskPromise(correlationId, resolve, reject, timeout);

      const askEnvelope = new AskEnvelope(message, this as ActorRef<any>, correlationId, timeout);
      this._sendSystemMessage(askEnvelope);
    });
  }
}
