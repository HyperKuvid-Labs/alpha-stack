import { Actor } from '../core/actor';
import { ActorContext } from '../core/actor-context';
import { JournalPlugin } from './journal/journal-plugin';
import { Logger } from '../utils/logger';

export abstract class PersistentActor<E, S> extends Actor<any> {
    public abstract readonly persistenceId: string;

    protected state: S;
    private sequenceNr: number;
    private _journal: JournalPlugin | undefined;
    private readonly logger = Logger;

    constructor(context: ActorContext<any>, initialState: S) {
        super(context);
        this.state = initialState;
        this.sequenceNr = 0;
    }

    public async preStart(): Promise<void> {
        await super.preStart();

        if (!this.persistenceId) {
            this.logger.error(`PersistentActor ${this.context.self.path} has no persistenceId defined. Persistence will be disabled.`);
            return;
        }

        const journal = (this.context.system as any).journalPlugin as JournalPlugin;

        if (!journal) {
            this.logger.error(`No JournalPlugin configured for ActorSystem. Persistence for ${this.persistenceId} will not work.`);
            return;
        }
        this._journal = journal;

        try {
            this.logger.info(`Recovering actor ${this.persistenceId} from sequence number ${this.sequenceNr}...`);
            const events = journal.replayEvents(this.persistenceId, this.sequenceNr + 1);

            for await (const event of events) {
                this.receiveRecover(event);
                this.sequenceNr++;
            }
            this.logger.info(`Actor ${this.persistenceId} recovered to sequence number ${this.sequenceNr}.`);
        } catch (error) {
            this.logger.error(`Error during recovery for ${this.persistenceId}: ${error instanceof Error ? error.message : String(error)}`);
            throw error;
        }
    }

    protected async persist(event: E): Promise<void> {
        if (!this._journal) {
            const errorMessage = `Cannot persist event for ${this.persistenceId}: JournalPlugin not initialized.`;
            this.logger.error(errorMessage);
            throw new Error(errorMessage);
        }

        try {
            await this._journal.writeEvents(this.persistenceId, [event]);
            this.sequenceNr++;
            this.receiveRecover(event);
            this.logger.info(`Event persisted and applied for ${this.persistenceId}, new sequenceNr: ${this.sequenceNr}`);
        } catch (error) {
            this.logger.error(`Error persisting event for ${this.persistenceId}: ${error instanceof Error ? error.message : String(error)}`);
            throw error;
        }
    }

    protected abstract receiveRecover(event: E): void;
}
