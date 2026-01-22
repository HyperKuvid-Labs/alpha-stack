export abstract class JournalPlugin {
  public abstract writeEvents(
    persistenceId: string,
    events: any[],
  ): Promise<void>;

  public abstract replayEvents(
    persistenceId: string,
    fromSequenceNr: number,
  ): AsyncIterable<any>;
}
