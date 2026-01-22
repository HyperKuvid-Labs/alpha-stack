import { JournalPlugin } from './journal-plugin';

export class InMemoryJournal implements JournalPlugin {
  private events: Map<string, any[]> = new Map();

  async writeEvents(persistenceId: string, events: any[]): Promise<void> {
    const currentEvents = this.events.get(persistenceId) || [];
    this.events.set(persistenceId, [...currentEvents, ...events]);
  }

  async *replayEvents(
    persistenceId: string,
    fromSequenceNr: number,
  ): AsyncIterable<any> {
    const storedEvents = this.events.get(persistenceId) || [];
    for (let i = Math.max(0, fromSequenceNr - 1); i < storedEvents.length; i++) {
      yield storedEvents[i];
    }
  }
}
