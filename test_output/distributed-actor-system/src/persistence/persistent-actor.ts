import { Actor, ActorContext } from '../core/actor';
import { Journal, EventEnvelope } from './journal';

export abstract class PersistentActor<S, E> extends Actor<any> {
  public readonly persistenceId: string;
  protected state: S;
  private journal: Journal;
  private lastSequenceNr: number = 0;

  protected constructor(persistenceId: string, initialState: S, journal: Journal, context: ActorContext) {
    super(context);
    this.persistenceId = persistenceId;
    this.state = initialState;
    this.journal = journal;
  }

  public async preStart(): Promise<void> {
    await super.preStart();

    const events = this.journal.replayEvents(this.persistenceId, 0);
    for await (const envelope of events) {
      this.state = this.receiveRecover(envelope.event as E, envelope.sequenceNr);
      this.lastSequenceNr = Math.max(this.lastSequenceNr, envelope.sequenceNr);
    }
  }

  protected async persist(event: E): Promise<E> {
    const nextSequenceNr = this.lastSequenceNr + 1;

    const envelope: EventEnvelope = {
      persistenceId: this.persistenceId,
      sequenceNr: nextSequenceNr,
      timestamp: Date.now(),
      event: event,
      eventType: (event as any).constructor.name,
    };

    await this.journal.writeEvents([envelope]);

    this.state = this.receiveRecover(event, nextSequenceNr);
    this.lastSequenceNr = nextSequenceNr;
    return event;
  }

  protected abstract receiveRecover(event: E, sequenceNr: number): S;
}
