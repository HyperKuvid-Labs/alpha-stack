export { EventEnvelope } from '../types/message.types';

export abstract class Journal {
  abstract writeEvents(events: EventEnvelope[]): Promise<void>;
  abstract replayEvents(persistenceId: string, fromSequenceNr: number): AsyncIterable<EventEnvelope>;
}
