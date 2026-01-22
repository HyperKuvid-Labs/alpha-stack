import { ActorContext } from '../types/actor.types';

export abstract class Actor<TMessage> {
  public readonly context: ActorContext;

  protected constructor(context: ActorContext) {
    this.context = context;
  }

  protected preStart(): void {}

  protected postStop(): void {}
}
