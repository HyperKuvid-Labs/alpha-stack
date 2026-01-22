import { ActorContext } from './actor-context';
import { ActorRef } from './actor-ref';

export abstract class Actor<T> {
  protected readonly context: ActorContext<T>;

  constructor(context: ActorContext<T>) {
    this.context = context;
  }

  public preStart(): void {}
  public postStop(): void {}
  public preRestart(): void {}
  public postRestart(): void {}

  public abstract receive(message: T): Promise<void>;
}
